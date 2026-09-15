"""Shared analysis-job queue, backed by Postgres.

This is the seam between the two machines. The Render web service calls
`enqueue()` and `get()`; the GPU worker (backend/jobs/worker.py) calls
`claim_next()`, `update()`, `heartbeat()`, `finish()` and
`requeue_stale()`. Both talk to the same Render Postgres, which is the
only thing they share — see docs/WORKER_SETUP_BRIEF.md.

The API response shape is deliberately unchanged from the previous
storage/jobs/*.json implementation: `as_dict()` emits exactly the keys the
frontend's AnalysisJob type already expects (frontend/src/api/types.ts),
so moving the queue into Postgres is invisible to the UI.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sql_delete, select, update as sql_update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import orm

# A claimed job whose worker stopped heartbeating for this long is assumed
# dead and returned to the queue. Generously longer than the worker's own
# heartbeat interval so a slow frame-extraction pass is never mistaken for
# a crash.
STALE_AFTER = timedelta(minutes=10)

# Terminal states — nothing reclaims or retries these.
_TERMINAL = frozenset({"completed", "failed"})

# How many times a job may be handed to a worker before it is treated as
# the cause rather than the victim.
#
# A job that kills its worker *hard* — an OOM kill on an oversized film, a
# segfault, the machine rebooting — never reaches the handler that would
# mark it failed. The process simply dies, requeue_stale() returns the job
# to the queue, and the next worker dies the same way. Because claiming
# takes the oldest job first, one poisonous upload would otherwise stall
# processing for everyone, indefinitely and silently.
MAX_ATTEMPTS = int(os.getenv("JOB_MAX_ATTEMPTS", "3"))


def as_dict(job: orm.AnalysisJob) -> dict:
    """The exact payload GET /api/analysis/status/{job_id} has always
    returned. Keys the UI doesn't set yet are still emitted (as null)
    rather than omitted, so the response shape is stable."""
    return {
        "job_id": str(job.job_id),
        "video_id": str(job.video_id),
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
        "frame_count": job.frame_count,
        "detection_frames": job.detection_frames,
        "track_count": job.track_count,
        "biomechanics": job.biomechanics,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


async def enqueue(
    db: AsyncSession,
    video_id: str,
    *,
    job_type: str = "analysis",
    payload: dict | None = None,
    message: str = "Analysis queued.",
) -> orm.AnalysisJob:
    """Queue work for a video. Returns immediately — no work is done in
    this process; a worker picks it up."""
    job = orm.AnalysisJob(
        video_id=uuid.UUID(str(video_id)),
        job_type=job_type,
        status="queued",
        progress=0,
        message=message,
        payload=payload,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def latest_for_video(db: AsyncSession, video_id: str, job_type: str) -> orm.AnalysisJob | None:
    """The most recent job of a kind for a video — how the identity status
    endpoint finds the run it should report on."""
    try:
        key = uuid.UUID(str(video_id))
    except (ValueError, AttributeError, TypeError):
        return None
    return await db.scalar(
        select(orm.AnalysisJob)
        .where(orm.AnalysisJob.video_id == key, orm.AnalysisJob.job_type == job_type)
        .order_by(orm.AnalysisJob.created_at.desc())
        .limit(1)
    )


async def get(db: AsyncSession, job_id: str) -> orm.AnalysisJob | None:
    try:
        key = uuid.UUID(str(job_id))
    except (ValueError, AttributeError, TypeError):
        return None  # a malformed id is "not found", not a 500
    return await db.scalar(select(orm.AnalysisJob).where(orm.AnalysisJob.job_id == key))


async def claim_next(db: AsyncSession, worker_id: str) -> orm.AnalysisJob | None:
    """Atomically take the oldest queued job, or return None if the queue
    is empty.

    FOR UPDATE SKIP LOCKED is what makes this safe with more than one
    worker: concurrent claimers skip rows already locked by another
    transaction instead of blocking on them or handing out the same job
    twice.
    """
    now = datetime.now(timezone.utc)
    row = await db.execute(
        select(orm.AnalysisJob)
        .where(orm.AnalysisJob.status == "queued")
        .order_by(orm.AnalysisJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = row.scalar_one_or_none()
    if job is None:
        await db.rollback()  # release the (empty) transaction promptly
        return None
    job.status = "claimed"
    job.claimed_by = worker_id
    job.claimed_at = now
    job.heartbeat_at = now
    job.attempts = (job.attempts or 0) + 1
    job.message = "Claimed by an analysis worker."
    job.updated_at = now
    await db.commit()
    await db.refresh(job)
    return job


async def update(db: AsyncSession, job_id: str, **fields) -> None:
    """Patch progress/status/counters mid-run. Also refreshes the
    heartbeat, since any progress at all proves the worker is alive."""
    now = datetime.now(timezone.utc)
    fields.setdefault("heartbeat_at", now)
    fields["updated_at"] = now
    await db.execute(
        sql_update(orm.AnalysisJob)
        .where(orm.AnalysisJob.job_id == uuid.UUID(str(job_id)))
        .values(**fields)
    )
    await db.commit()


async def heartbeat(db: AsyncSession, job_id: str) -> None:
    """Prove the worker is still alive during a long stage that reports no
    progress of its own."""
    await update(db, job_id)


async def finish(db: AsyncSession, job_id: str, **fields) -> None:
    """Terminal update — clears the claim so a completed/failed job is
    never mistaken for one held by a live worker."""
    await update(db, job_id, claimed_by=None, claimed_at=None, **fields)


async def requeue_stale(db: AsyncSession, stale_after: timedelta = STALE_AFTER) -> int:
    """Return jobs whose worker died back to the queue, and report how
    many were recovered.

    Without this, a worker crashing (or the V2 box rebooting) mid-job
    leaves that job claimed forever and the member watching a progress bar
    that never moves.
    """
    cutoff = datetime.now(timezone.utc) - stale_after
    now = datetime.now(timezone.utc)
    stalled = (
        orm.AnalysisJob.status.not_in(_TERMINAL),
        orm.AnalysisJob.status != "queued",
        orm.AnalysisJob.heartbeat_at.is_not(None),
        orm.AnalysisJob.heartbeat_at < cutoff,
    )

    # Give up on a job that has already taken down MAX_ATTEMPTS workers.
    # Failing it honestly is strictly better than retrying forever: the
    # member is told, and the rest of the queue moves again.
    exhausted = await db.execute(
        sql_update(orm.AnalysisJob)
        .where(*stalled, orm.AnalysisJob.attempts >= MAX_ATTEMPTS)
        .values(
            status="failed",
            claimed_by=None,
            claimed_at=None,
            message="Analysis stopped after repeated failures.",
            error=(
                f"Gave up after {MAX_ATTEMPTS} attempts — each worker stopped responding "
                f"while processing this job. The film may be too large for the worker "
                f"machine, or corrupt."
            ),
            updated_at=now,
        )
    )

    result = await db.execute(
        sql_update(orm.AnalysisJob)
        .where(*stalled, orm.AnalysisJob.attempts < MAX_ATTEMPTS)
        .values(
            status="queued",
            claimed_by=None,
            claimed_at=None,
            heartbeat_at=None,
            message="Previous worker stopped responding; returned to the queue.",
            updated_at=now,
        )
    )
    await db.commit()
    return (result.rowcount or 0) + (exhausted.rowcount or 0)


# ---------------------------------------------------------------------
# Worker liveness
#
# Separate from a job's heartbeat: that tracks one job's progress, this
# answers "is anything processing film at all?". Without it, a queued job
# with no worker running is indistinguishable from one waiting its turn,
# and the UI shows a progress bar that will never move.
# ---------------------------------------------------------------------

# A worker polls every WORKER_POLL_INTERVAL_S (default 5s), so a gap of
# minutes means it is genuinely gone rather than briefly busy. Generous
# enough that a long single-frame stage never marks a live worker dead.
WORKER_ALIVE_WITHIN = timedelta(minutes=3)


async def record_worker_heartbeat(db: AsyncSession, worker_id: str, device: str | None = None) -> None:
    """Upsert this worker's liveness row. Called on every poll."""
    now = datetime.now(timezone.utc)
    await db.execute(
        pg_insert(orm.WorkerHeartbeat)
        .values(worker_id=worker_id, last_seen_at=now, device=device)
        .on_conflict_do_update(
            index_elements=[orm.WorkerHeartbeat.worker_id],
            set_={"last_seen_at": now, "device": device},
        )
    )
    await db.commit()


async def live_workers(db: AsyncSession, within: timedelta = WORKER_ALIVE_WITHIN) -> list[orm.WorkerHeartbeat]:
    cutoff = datetime.now(timezone.utc) - within
    rows = await db.execute(
        select(orm.WorkerHeartbeat)
        .where(orm.WorkerHeartbeat.last_seen_at >= cutoff)
        .order_by(orm.WorkerHeartbeat.last_seen_at.desc())
    )
    return list(rows.scalars().all())


async def any_worker_alive(db: AsyncSession, within: timedelta = WORKER_ALIVE_WITHIN) -> bool:
    cutoff = datetime.now(timezone.utc) - within
    found = await db.scalar(
        select(orm.WorkerHeartbeat.worker_id)
        .where(orm.WorkerHeartbeat.last_seen_at >= cutoff)
        .limit(1)
    )
    return found is not None


# Finished jobs are kept long enough to be useful for support ("what
# happened to my film last week?") and no longer. Without a bound the
# table grows for the life of the deployment, and its rows carry payloads
# and full result documents, not just counters.
COMPLETED_JOB_RETENTION = timedelta(days=int(os.getenv("JOB_RETENTION_DAYS", "30")))


async def purge_finished_jobs(
    db: AsyncSession, older_than: timedelta = COMPLETED_JOB_RETENTION
) -> int:
    """Delete completed/failed jobs finished longer ago than `older_than`.

    Only terminal jobs are eligible: anything queued or in flight is left
    alone regardless of age, so a long-running report is never deleted out
    from under the member watching it.
    """
    cutoff = datetime.now(timezone.utc) - older_than
    result = await db.execute(
        sql_delete(orm.AnalysisJob).where(
            orm.AnalysisJob.status.in_(_TERMINAL),
            orm.AnalysisJob.updated_at < cutoff,
        )
    )
    await db.commit()
    return result.rowcount or 0
