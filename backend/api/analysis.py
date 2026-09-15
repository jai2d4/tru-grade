"""Analysis job API — enqueue and report status.

This endpoint no longer *runs* analysis. It used to, via
BackgroundTasks.add_task, which meant the CV pipeline (torch, ultralytics,
easyocr) executed inside the web process — measured at 539 MB of imports
alone against a 512 MB instance limit, i.e. guaranteed to OOM-kill the
site the first time a member analyzed film. See
docs/WORKER_SETUP_BRIEF.md for the measurements and the resulting split.

Now: the web service enqueues into a Postgres-backed queue
(backend/jobs/store.py) and a separate worker on a GPU machine
(backend/jobs/worker.py) claims and runs the job. The response shapes are
unchanged, so the UI's existing poll loop works exactly as before.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from backend.api.videos import video_store
from backend.jobs import store

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# Statuses a job can be resumed from. A job that's genuinely mid-flight on
# a live worker must not be re-queued underneath it; requeue_stale() is
# what recovers those, on evidence the worker actually died.
_RESUMABLE = frozenset({"failed", "interrupted"})


@router.post("/start/{video_id}", status_code=202)
async def start_analysis(video_id: str, db: AsyncSession = Depends(get_db)):
    video = video_store.get(video_id)
    if not video:
        raise HTTPException(404, "Video not found.")
    job = await store.enqueue(db, video_id)
    return store.as_dict(job)


@router.get("/status/{job_id}")
async def analysis_status(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await store.get(db, job_id)
    if not job:
        raise HTTPException(404, "Analysis job not found.")
    payload = store.as_dict(job)

    # A queued job with no worker running looks exactly like one waiting
    # its turn, so the UI would show a progress bar that never moves. Say
    # what is actually true instead — the job is safely queued and will
    # run as soon as a worker is started.
    if job.status == "queued" and not await store.any_worker_alive(db):
        payload["message"] = (
            "Waiting for an analysis worker. No worker is currently running, so this "
            "film has not started processing yet — it stays queued and will begin "
            "automatically once one is available."
        )
        payload["worker_available"] = False
    else:
        payload["worker_available"] = True
    return payload


@router.get("/workers")
async def analysis_workers(db: AsyncSession = Depends(get_db)):
    """Which workers are alive, for an operator checking whether film can
    be processed at all. Reports emptiness plainly rather than implying
    capacity that isn't there."""
    workers = await store.live_workers(db)
    return {
        "workers": [
            {
                "worker_id": worker.worker_id,
                "device": worker.device,
                "last_seen_at": worker.last_seen_at.isoformat() if worker.last_seen_at else None,
            }
            for worker in workers
        ],
        "available": bool(workers),
        "detail": (
            f"{len(workers)} analysis worker(s) available."
            if workers else
            "No analysis worker is running. Film can be uploaded, but it will stay "
            "queued until one is started (see docs/RUN_ON_V2.md)."
        ),
    }


@router.post("/resume/{job_id}", status_code=202)
async def resume_analysis(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await store.get(db, job_id)
    if not job:
        raise HTTPException(404, "Analysis job not found.")
    if job.status not in _RESUMABLE:
        raise HTTPException(409, "Only failed or interrupted jobs can be resumed.")
    if not video_store.get(str(job.video_id)):
        raise HTTPException(404, "Video not found.")
    # Back to 'queued' rather than run here — the next free worker picks it
    # up, and the pipeline's own stage-level resume means completed stages
    # (extracted frames, finished detection) are reused, not redone.
    await store.update(
        db, job_id, status="queued", claimed_by=None, claimed_at=None,
        heartbeat_at=None, error=None, message="Analysis resume queued.",
    )
    refreshed = await store.get(db, job_id)
    return store.as_dict(refreshed)
