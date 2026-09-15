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

import os
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


# YouTube's anti-bot challenge is the dominant failure here, and it is not
# a bug in this code — it is YouTube declining to serve an anonymous
# client. These knobs are the two things that actually change the outcome.

def _player_clients() -> list[str | None]:
    """Clients to try, in order.

    Each identifies as a different YouTube app. YouTube challenges them
    inconsistently, so one being blocked rarely means all are. None means
    yt-dlp's own default, tried first so a working setup pays no cost.
    """
    configured = os.getenv("YTDLP_PLAYER_CLIENTS", "").strip()
    if configured:
        return [c.strip() for c in configured.split(",") if c.strip()]
    return [None, "android", "ios", "tv_embedded", "web_safari"]


def _auth_opts() -> dict:
    """Cookies, if configured.

    Signed-in requests are what reliably clears the bot challenge. Either
    point at a browser profile on this machine
    (YTDLP_COOKIES_FROM_BROWSER=chrome) or an exported cookies.txt
    (YTDLP_COOKIE_FILE=/path/to/cookies.txt).
    """
    browser = os.getenv("YTDLP_COOKIES_FROM_BROWSER", "").strip()
    if browser:
        # yt-dlp wants a tuple: (browser, profile, keyring, container).
        return {"cookiesfrombrowser": (browser, None, None, None)}
    cookie_file = os.getenv("YTDLP_COOKIE_FILE", "").strip()
    if cookie_file and Path(cookie_file).is_file():
        return {"cookiefile": cookie_file}
    return {}


def _is_bot_challenge(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in (
        "sign in to confirm", "not a bot", "confirm you're not a bot",
        "cookies", "age-restricted", "login required",
    ))


def _download_failure(error: Exception | None) -> HTTPException:
    """Turn yt-dlp's message into something the operator can act on.

    Relaying the raw error told the user to read the yt-dlp wiki, which is
    not an answer — the answer is either "upload the file directly" or
    "configure cookies", and which one depends on why it failed.
    """
    raw = str(error) if error else "unknown error"
    detail = raw.splitlines()[-1] if raw.splitlines() else raw

    if _is_bot_challenge(raw):
        return HTTPException(
            status_code=502,
            detail=(
                "YouTube refused the download, asking the server to prove it isn't a bot. "
                "This is YouTube blocking anonymous downloads, not a problem with the film "
                "or the link. Upload the video file directly instead — that always works "
                "and skips YouTube entirely. To keep using links, sign the server in by "
                "setting YTDLP_COOKIES_FROM_BROWSER or YTDLP_COOKIE_FILE "
                "(see docs/YOUTUBE_DOWNLOADS.md)."
            ),
        )
    if "private" in raw.lower() or "members-only" in raw.lower():
        return HTTPException(
            status_code=400,
            detail=("That video is private or members-only, so the server cannot reach it. "
                    "Make it unlisted rather than private, or upload the file directly."),
        )
    if "unavailable" in raw.lower() or "removed" in raw.lower():
        return HTTPException(
            status_code=400,
            detail=f"That YouTube video is unavailable: {detail}",
        )
    return HTTPException(
        status_code=502,
        detail=(f"Could not fetch that YouTube video: {detail} "
                "Uploading the file directly avoids YouTube entirely."),
    )


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

    base_opts = {
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
        **_auth_opts(),
    }

    info = None
    last_error: Exception | None = None
    # YouTube increasingly refuses anonymous downloads with "Sign in to
    # confirm you're not a bot", and which client it challenges varies.
    # Each of these identifies as a different YouTube app; when one is
    # blocked another often is not. Tried in order, cheapest first.
    for client in _player_clients():
        opts = dict(base_opts)
        if client:
            opts["extractor_args"] = {"youtube": {"player_client": [client]}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            break
        except yt_dlp.utils.DownloadError as exc:
            last_error = exc
            message = str(exc).lower()
            # Size and availability are settled facts — no other client
            # will produce a different answer, so stop immediately.
            if "max_filesize" in message or "file is larger than" in message:
                _cleanup(tmp_dir)
                raise HTTPException(status_code=413,
                                    detail="That YouTube video exceeds the upload size limit.")
            if _is_bot_challenge(message) or "http error 403" in message:
                continue  # worth retrying as a different client
            break
        except Exception as exc:
            last_error = exc
            break

    if info is None:
        _cleanup(tmp_dir)
        raise _download_failure(last_error)

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
