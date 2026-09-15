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


# ---------- YouTube's anti-bot challenge ----------
#
# The failure seen in real use: YouTube refuses an anonymous download with
# "Sign in to confirm you're not a bot". This is YouTube declining to
# serve the server, not a fault in the link or the film, and the previous
# code relayed yt-dlp's raw message telling the operator to go read a wiki
# page — which is not an answer they can act on.


BOT_MESSAGE = (
    "ERROR: [youtube] Jv78FCb9KM8: Sign in to confirm you're not a bot. "
    "Use --cookies-from-browser or --cookies for the authentication."
)


def test_it_retries_with_another_client_when_one_is_challenged():
    """YouTube challenges its own clients inconsistently, so a block on one
    rarely means a block on all. Give up after the first and downloads fail
    that would have succeeded."""
    attempts = []
    original = FakeYoutubeDL.extract_info

    def flaky(self, url, download=True):
        client = (self.opts.get("extractor_args", {})
                      .get("youtube", {}).get("player_client", [None]))[0]
        attempts.append(client)
        if client != "android":
            raise FakeDownloadError(BOT_MESSAGE)
        return original(self, url, download)

    FakeYoutubeDL.extract_info = flaky
    try:
        path, filename = youtube.download("https://youtu.be/dQw4w9WgXcQ", max_upload_mb=500)
        path.unlink(missing_ok=True)
    finally:
        FakeYoutubeDL.extract_info = original

    assert "android" in attempts
    assert len(attempts) > 1, "gave up without trying another client"


def test_when_every_client_is_challenged_the_error_says_what_to_do():
    _BEHAVIOR["mode"] = "generic_error"
    original = FakeYoutubeDL.extract_info

    def always_challenged(self, url, download=True):
        raise FakeDownloadError(BOT_MESSAGE)

    FakeYoutubeDL.extract_info = always_challenged
    try:
        with pytest.raises(HTTPException) as excinfo:
            youtube.download("https://youtu.be/dQw4w9WgXcQ", max_upload_mb=500)
    finally:
        FakeYoutubeDL.extract_info = original

    detail = excinfo.value.detail
    # The operator needs the workaround, not a wiki link.
    assert "Upload the video file directly" in detail
    # And it must not read as though their film or link is at fault.
    assert "not a problem with the film" in detail


def test_an_oversized_video_fails_immediately_without_retrying():
    """Size is a settled fact — no other client returns a smaller file, so
    retrying would just be slow."""
    attempts = []
    original = FakeYoutubeDL.extract_info

    def too_big(self, url, download=True):
        attempts.append(1)
        raise FakeDownloadError("ERROR: File is larger than max-filesize (100000 bytes)")

    FakeYoutubeDL.extract_info = too_big
    try:
        with pytest.raises(HTTPException) as excinfo:
            youtube.download("https://youtu.be/dQw4w9WgXcQ", max_upload_mb=1)
    finally:
        FakeYoutubeDL.extract_info = original

    assert excinfo.value.status_code == 413
    assert len(attempts) == 1, "retried a failure that cannot change"


def test_a_private_video_is_explained_rather_than_relayed():
    original = FakeYoutubeDL.extract_info

    def private(self, url, download=True):
        raise FakeDownloadError("ERROR: [youtube] abc: Private video. Sign in if you've been granted access")

    FakeYoutubeDL.extract_info = private
    try:
        with pytest.raises(HTTPException) as excinfo:
            youtube.download("https://youtu.be/abc", max_upload_mb=500)
    finally:
        FakeYoutubeDL.extract_info = original

    assert "unlisted rather than private" in excinfo.value.detail


def test_cookies_from_a_browser_are_passed_through_when_configured(monkeypatch):
    """Signing the server in is what reliably clears the challenge."""
    monkeypatch.setenv("YTDLP_COOKIES_FROM_BROWSER", "chrome")
    seen = {}
    original = FakeYoutubeDL.__init__

    def capture(self, opts):
        seen.update(opts)
        original(self, opts)

    FakeYoutubeDL.__init__ = capture
    try:
        path, _ = youtube.download("https://youtu.be/dQw4w9WgXcQ", max_upload_mb=500)
        path.unlink(missing_ok=True)
    finally:
        FakeYoutubeDL.__init__ = original

    assert seen.get("cookiesfrombrowser") == ("chrome", None, None, None)


def test_no_cookie_options_are_sent_when_nothing_is_configured(monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_FROM_BROWSER", raising=False)
    monkeypatch.delenv("YTDLP_COOKIE_FILE", raising=False)
    seen = {}
    original = FakeYoutubeDL.__init__

    def capture(self, opts):
        seen.update(opts)
        original(self, opts)

    FakeYoutubeDL.__init__ = capture
    try:
        path, _ = youtube.download("https://youtu.be/dQw4w9WgXcQ", max_upload_mb=500)
        path.unlink(missing_ok=True)
    finally:
        FakeYoutubeDL.__init__ = original

    assert "cookiesfrombrowser" not in seen
    assert "cookiefile" not in seen
