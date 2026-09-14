"""Server-side YouTube video ingestion for the V2 Film Analysis pipeline.

Module 1's simpler Gemini-only flow (app/main.py) can hand Gemini a bare
YouTube URL and let Google's own servers fetch it — Gemini's video
understanding works referentially. This pipeline can't do that: player
tracking, pose estimation, and ball detection (backend/vision/*) run
locally frame-by-frame via OpenCV/ultralytics, which needs the actual
video bytes on disk. This module is what gets them there — downloading
with yt-dlp into the same local storage a direct upload would use, so
everything downstream (backend/api/videos.py's /content route, the
tracking pipeline, etc.) treats it identically to a phone-uploaded file.

The practical reason this exists: a phone-shot game film file is often
too large, or too slow to upload over a mobile connection, to reliably
finish a direct HTTP upload. Uploading it to YouTube first (even
unlisted) and pasting the link here sidesteps both problems — YouTube's
own apps are built for exactly that upload job, and this fetch happens
server-to-server instead of from the phone.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def is_youtube_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host in _YOUTUBE_HOSTS


def _sanitize_title(title: str | None, video_id: str) -> str:
    base = (title or video_id).strip()
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip("._ ") or video_id
    return safe[:80]


def download(url: str, max_upload_mb: int) -> tuple[Path, str]:
    """Downloads `url` into a fresh temp file and returns (path, filename).
    Caller owns the returned file — VideoStore.save_from_path() moves it
    into permanent storage, or the caller should unlink it on failure.

    Runs synchronously (yt-dlp's own API is blocking) — call this via
    asyncio.to_thread from an async route, same pattern app/main.py uses
    for its own blocking Gemini calls.
    """
    if not is_youtube_url(url):
        raise HTTPException(status_code=400, detail="Not a valid YouTube URL.")

    import yt_dlp  # imported lazily — a heavy optional dep only this path needs

    tmp_dir = Path(tempfile.mkdtemp(prefix="trugrade-yt-"))
    max_bytes = max_upload_mb * 1024 * 1024

    ydl_opts = {
        "outtmpl": str(tmp_dir / "%(id)s.%(ext)s"),
        # Capped at 1080p and merged to mp4 — the tracking pipeline gains
        # nothing from 4K, and it keeps downloads/storage reasonable.
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "max_filesize": max_bytes,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        _cleanup(tmp_dir)
        message = str(exc)
        if "max_filesize" in message.lower() or "file is larger than" in message.lower():
            raise HTTPException(status_code=413, detail="That YouTube video exceeds the upload size limit.")
        raise HTTPException(status_code=400, detail=f"Could not fetch that YouTube video: {message.splitlines()[-1]}")
    except Exception as exc:
        _cleanup(tmp_dir)
        raise HTTPException(status_code=502, detail=f"Could not fetch that YouTube video: {exc}")

    video_id = info.get("id") or "video"
    # Glob rather than trust prepare_filename()'s reported extension — after
    # merge_output_format re-muxes separate streams, the file on disk can
    # end up with a different suffix than info['ext'] still claims.
    candidates = sorted(p for p in tmp_dir.glob(f"{video_id}.*") if p.is_file())
    if not candidates:
        _cleanup(tmp_dir)
        raise HTTPException(status_code=502, detail="YouTube download finished but produced no file.")
    downloaded_path = candidates[0]

    title = _sanitize_title(info.get("title"), video_id)
    filename = f"{title}{downloaded_path.suffix.lower()}"
    return downloaded_path, filename


def _cleanup(tmp_dir: Path) -> None:
    import shutil

    shutil.rmtree(tmp_dir, ignore_errors=True)
