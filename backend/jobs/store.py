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

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import orm

# A claimed job whose worker stopped heartbeating for this long is assumed
# dead and returned to the queue. Generously longer than the worker's own
# heartbeat interval so a slow frame-extraction pass is never mistaken for
# a crash.
STALE_AFTER = timedelta(minutes=10)

# Terminal states — nothing reclaims or retries these.
_TERMINAL = frozenset({"completed", "failed"})


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


async def enqueue(db: AsyncSession, video_id: str) -> orm.AnalysisJob:
    """Queue a video for analysis. Returns immediately — no work is done
    in this process; a worker picks it up."""
    job = orm.AnalysisJob(
        video_id=uuid.UUID(str(video_id)),
        status="queued",
        progress=0,
        message="Analysis queued.",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


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
    result = await db.execute(
        sql_update(orm.AnalysisJob)
        .where(
            orm.AnalysisJob.status.not_in(_TERMINAL),
            orm.AnalysisJob.status != "queued",
            orm.AnalysisJob.heartbeat_at.is_not(None),
            orm.AnalysisJob.heartbeat_at < cutoff,
        )
        .values(
            status="queued",
            claimed_by=None,
            claimed_at=None,
            heartbeat_at=None,
            message="Previous worker stopped responding; returned to the queue.",
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    return result.rowcount or 0
