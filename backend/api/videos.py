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

import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import orm
from backend.video.ingestion import VideoStore


router = APIRouter(prefix="/api/videos", tags=["videos"])
storage_root = Path(os.getenv("TRUGRADE_STORAGE_DIR", Path(__file__).parents[1] / "storage"))
video_store = VideoStore(storage_root, int(os.getenv("MAX_UPLOAD_MB", "500")))


@router.post("/upload", status_code=201)
async def upload_video(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    metadata = await video_store.save(file)
    db.add(orm.FilmUpload(
        id=UUID(metadata["video_id"]), filename=metadata["filename"], status=metadata["status"],
    ))
    await db.commit()
    return {key: metadata[key] for key in ("video_id", "filename", "status")}


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
