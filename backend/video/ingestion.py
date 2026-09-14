"""Chunked, validated local video storage."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile


ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


class VideoStore:
    def __init__(self, root: Path, max_upload_mb: int = 500):
        self.root = Path(root)
        self.video_dir = self.root / "videos"
        self.metadata_dir = self.root / "metadata"
        self.video_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_upload_mb * 1024 * 1024

    async def save(self, upload: UploadFile) -> dict:
        original = Path(upload.filename or "").name
        suffix = Path(original).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, "Video must be MP4, MOV, AVI, or MKV.")
        video_id = str(uuid4())
        target = self._target_path(video_id, original, suffix)
        size = 0
        try:
            with target.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise HTTPException(413, "File exceeds upload limit.")
                    output.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return self._record(video_id, original, target, size)

    def save_from_path(self, source: Path, original_filename: str) -> dict:
        """Adopts an already-downloaded file (see backend/video/youtube.py)
        into the store — same validation, metadata, and directory layout as
        a direct upload, just skipping the chunked-read step since the
        bytes are already on disk. Moves rather than copies; the caller's
        temp file no longer exists afterward."""
        suffix = Path(original_filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, "Video must be MP4, MOV, AVI, or MKV.")
        video_id = str(uuid4())
        target = self._target_path(video_id, original_filename, suffix)
        size = source.stat().st_size
        if size > self.max_bytes:
            source.unlink(missing_ok=True)
            raise HTTPException(413, "File exceeds upload limit.")
        source.replace(target)
        return self._record(video_id, original_filename, target, size)

    def _target_path(self, video_id: str, original: str, suffix: str) -> Path:
        safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original).stem).strip("._") or "film"
        return self.video_dir / f"{video_id}-{safe_stem}{suffix}"

    def _record(self, video_id: str, original: str, target: Path, size: int) -> dict:
        metadata = {
            "video_id": video_id, "filename": original, "status": "uploaded",
            "size_bytes": size, "file_path": str(target),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.write_metadata(video_id, metadata)
        return metadata

    def write_metadata(self, video_id: str, metadata: dict) -> None:
        (self.metadata_dir / f"{video_id}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def get(self, video_id: str) -> dict | None:
        path = self.metadata_dir / f"{video_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def list(self) -> list[dict]:
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(self.metadata_dir.glob("*.json"))]

