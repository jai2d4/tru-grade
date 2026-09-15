"""Phase 3 video upload/list API.

Unified with the athlete roster (see the db/init_schema.sql comment above
film_track_assignments): every uploaded video gets a real film_uploads row,
using the same id the local VideoStore already generates, so a video is
the same row no matter which pipeline created it. Which specific athletes
appear in it is a backend/api/players.py concern (a video can show more
than one prospect); this router only establishes that the video itself
exists in the shared database.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import orm
from backend.video import youtube
from backend.video.ingestion import VideoStore

logger = logging.getLogger("tru.videos")

router = APIRouter(prefix="/api/videos", tags=["videos"])
storage_root = Path(os.getenv("TRUGRADE_STORAGE_DIR", Path(__file__).parents[1] / "storage"))
_max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "2048"))
video_store = VideoStore(storage_root, _max_upload_mb)


class YouTubeUploadRequest(BaseModel):
    youtube_url: str = Field(..., min_length=1, max_length=2048)


async def _record_upload(metadata: dict, db: AsyncSession) -> dict:
    db.add(orm.FilmUpload(
        id=UUID(metadata["video_id"]), filename=metadata["filename"], status=metadata["status"],
    ))
    await db.commit()
    return {key: metadata[key] for key in ("video_id", "filename", "status")}


@router.post("/upload", status_code=201)
async def upload_video(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    metadata = await video_store.save(file)
    return await _record_upload(metadata, db)


@router.post("/upload-from-youtube", status_code=201)
async def upload_video_from_youtube(body: YouTubeUploadRequest, db: AsyncSession = Depends(get_db)):
    """Fetches the video server-side (see backend/video/youtube.py) and
    stores it exactly like a direct upload — this is the recommended path
    for phone-shot film: upload to YouTube (unlisted is fine) from the
    phone, where mobile upload is a solved problem, then paste the link
    here instead of pushing the same large file through this API."""
    downloaded_path, filename = await asyncio.to_thread(youtube.download, body.youtube_url, _max_upload_mb)
    try:
        metadata = video_store.save_from_path(downloaded_path, filename)
    except HTTPException:
        downloaded_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        downloaded_path.unlink(missing_ok=True)
        logger.exception("failed to store a downloaded YouTube video")
        raise HTTPException(status_code=500, detail=f"Could not store the downloaded video: {exc}")
    return await _record_upload(metadata, db)


@router.get("")
async def list_videos():
    return {"videos": video_store.list()}


@router.get("/{video_id}/content")
async def video_content(video_id: str):
    metadata = video_store.get(video_id)
    if not metadata:
        raise HTTPException(404, "Video not found.")
    path = Path(metadata["file_path"])
    if not path.is_file():
        raise HTTPException(404, "Stored video file is unavailable.")
    return FileResponse(path, filename=metadata["filename"])
