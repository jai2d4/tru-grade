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
    return store.as_dict(job)


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
