"""Server-side YouTube ingestion for the V2 Film Analysis pipeline —
backend/video/youtube.py and VideoStore.save_from_path. yt_dlp itself is
faked (sys.modules injection, same pattern test_video_phase3.py uses for
cv2) since this sandbox has no route to youtube.com — the real network
path can only be proven on the actual deployment."""
from __future__ import annotations

import asyncio
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

from backend.video import youtube
from backend.video.ingestion import VideoStore


class FakeDownloadError(Exception):
    pass


class FakeYoutubeDL:
    """Mimics yt_dlp.YoutubeDL just enough: writes a real file into the
    outtmpl's directory (as yt_dlp actually would) and returns an info
    dict, or raises to simulate a real failure."""

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=True):
        behavior = _BEHAVIOR["mode"]
        if behavior == "size_error":
            raise FakeDownloadError("ERROR: File is larger than max-filesize (100000 bytes)")
        if behavior == "generic_error":
            raise FakeDownloadError("ERROR: Video unavailable")
        if behavior == "no_file":
            return {"id": "novid", "title": "Ghost", "ext": "mp4"}

        tmp_dir = Path(self.opts["outtmpl"]).parent
        video_id = "dQw4w9WgXcQ"
        target = tmp_dir / f"{video_id}.mp4"
        target.write_bytes(_BEHAVIOR.get("payload", b"real-downloaded-bytes"))
        return {"id": video_id, "title": _BEHAVIOR.get("title", "Real Game Film: Week 3"), "ext": "mp4"}


_BEHAVIOR = {"mode": "success"}


@pytest.fixture(autouse=True)
def _fake_yt_dlp(monkeypatch):
    _BEHAVIOR["mode"] = "success"
    _BEHAVIOR.pop("payload", None)
    _BEHAVIOR.pop("title", None)
    fake_module = SimpleNamespace(
        YoutubeDL=FakeYoutubeDL,
        utils=SimpleNamespace(DownloadError=FakeDownloadError),
    )
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_module)
    yield


def test_is_youtube_url_recognizes_real_hosts_only():
    assert youtube.is_youtube_url("https://www.youtube.com/watch?v=abc123")
    assert youtube.is_youtube_url("https://youtu.be/abc123")
    assert youtube.is_youtube_url("https://m.youtube.com/watch?v=abc123")
    assert not youtube.is_youtube_url("https://vimeo.com/123456")
    assert not youtube.is_youtube_url("not a url at all")
    assert not youtube.is_youtube_url("https://youtube.com.evil.example/watch")


def test_download_rejects_a_non_youtube_url_before_touching_yt_dlp():
    with pytest.raises(HTTPException) as excinfo:
        youtube.download("https://vimeo.com/123456", max_upload_mb=500)
    assert excinfo.value.status_code == 400


def test_download_fetches_a_real_file_with_a_readable_filename():
    path, filename = youtube.download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", max_upload_mb=500)
    try:
        assert path.is_file()
        assert path.read_bytes() == b"real-downloaded-bytes"
        assert filename.endswith(".mp4")
        assert "Real_Game_Film" in filename or "Real Game Film" in filename
    finally:
        path.unlink(missing_ok=True)


def test_download_sanitizes_a_title_with_unsafe_characters():
    _BEHAVIOR["title"] = "Week 3 / Opponent: \"The Wolves\" <film>"
    path, filename = youtube.download("https://youtu.be/dQw4w9WgXcQ", max_upload_mb=500)
    try:
        assert "/" not in filename and '"' not in filename and "<" not in filename
    finally:
        path.unlink(missing_ok=True)


def test_download_reports_413_when_the_video_exceeds_the_size_limit():
    _BEHAVIOR["mode"] = "size_error"
    with pytest.raises(HTTPException) as excinfo:
        youtube.download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", max_upload_mb=1)
    assert excinfo.value.status_code == 413


def test_download_reports_a_clear_400_for_an_unavailable_video():
    _BEHAVIOR["mode"] = "generic_error"
    with pytest.raises(HTTPException) as excinfo:
        youtube.download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", max_upload_mb=500)
    assert excinfo.value.status_code == 400
    assert "unavailable" in excinfo.value.detail.lower()


def test_download_reports_502_if_yt_dlp_claims_success_with_no_file_on_disk():
    _BEHAVIOR["mode"] = "no_file"
    with pytest.raises(HTTPException) as excinfo:
        youtube.download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", max_upload_mb=500)
    assert excinfo.value.status_code == 502


# ---------- VideoStore.save_from_path ----------


def test_save_from_path_adopts_a_downloaded_file_into_the_store(tmp_path):
    store = VideoStore(tmp_path / "storage", max_upload_mb=500)
    downloaded = tmp_path / "scratch" / "dQw4w9WgXcQ.mp4"
    downloaded.parent.mkdir(parents=True)
    downloaded.write_bytes(b"real football film bytes")

    result = store.save_from_path(downloaded, "Real Game Film.mp4")

    assert result["status"] == "uploaded"
    assert result["filename"] == "Real Game Film.mp4"
    assert result["size_bytes"] == len(b"real football film bytes")
    assert Path(result["file_path"]).is_file()
    assert not downloaded.exists()  # moved, not copied
    assert store.get(result["video_id"])["size_bytes"] == len(b"real football film bytes")


def test_save_from_path_rejects_an_unsupported_extension(tmp_path):
    store = VideoStore(tmp_path / "storage")
    downloaded = tmp_path / "scratch.exe"
    downloaded.parent.mkdir(exist_ok=True)
    downloaded.write_bytes(b"not a video")

    with pytest.raises(HTTPException) as excinfo:
        store.save_from_path(downloaded, "scratch.exe")
    assert excinfo.value.status_code == 400


def test_save_from_path_rejects_a_file_over_the_limit(tmp_path):
    store = VideoStore(tmp_path / "storage", max_upload_mb=0)  # 0 MB -> anything nonempty is over
    downloaded = tmp_path / "big.mp4"
    downloaded.write_bytes(b"x" * 1024)

    with pytest.raises(HTTPException) as excinfo:
        store.save_from_path(downloaded, "big.mp4")
    assert excinfo.value.status_code == 413
    assert not downloaded.exists()  # cleaned up on rejection


def test_save_still_works_unchanged_after_the_refactor(tmp_path):
    """save() and save_from_path() now share _target_path/_record —
    confirm the original direct-upload path wasn't disturbed."""
    store = VideoStore(tmp_path, max_upload_mb=1)
    upload = UploadFile(filename="Game Film.MKV", file=BytesIO(b"football-film"))
    result = asyncio.run(store.save(upload))
    assert result["status"] == "uploaded"
    assert result["filename"] == "Game Film.MKV"
    assert store.get(result["video_id"])["size_bytes"] == 13
