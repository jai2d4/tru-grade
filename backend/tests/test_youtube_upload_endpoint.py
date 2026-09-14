"""HTTP-level coverage for POST /api/videos/upload-from-youtube — the real
download step (backend/video/youtube.py) is mocked here (see
test_youtube_ingestion.py for that layer's own coverage); this file proves
the route wires it into the same film_uploads row and VideoStore a direct
upload gets."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _skip_without_db(db_available):
    available, reason = db_available
    if not available:
        pytest.skip(f"No PostgreSQL reachable — set POSTGRES_* env vars to run these tests. ({reason})")


def _fake_download(tmp_path_factory):
    def _download(url: str, max_upload_mb: int):
        scratch = tmp_path_factory.mktemp("yt")
        path = scratch / "dQw4w9WgXcQ.mp4"
        path.write_bytes(b"real downloaded football film")
        return path, "Real Game Film.mp4"

    return _download


def test_upload_from_youtube_stores_the_video_like_a_direct_upload(client, monkeypatch, tmp_path_factory):
    import backend.api.videos as videos_module

    monkeypatch.setattr(videos_module.youtube, "download", _fake_download(tmp_path_factory))

    response = client.post("/api/videos/upload-from-youtube", json={"youtube_url": "https://youtu.be/dQw4w9WgXcQ"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "uploaded"
    assert body["filename"] == "Real Game Film.mp4"

    listing = client.get("/api/videos").json()["videos"]
    assert any(v["video_id"] == body["video_id"] for v in listing)

    content = client.get(f"/api/videos/{body['video_id']}/content")
    assert content.status_code == 200
    assert content.content == b"real downloaded football film"


def test_upload_from_youtube_rejects_a_non_youtube_url(client):
    # The real youtube.download() is left in place here (not mocked) — its
    # own is_youtube_url check rejects this before yt_dlp is ever imported,
    # which is exactly what this asserts.
    response = client.post("/api/videos/upload-from-youtube", json={"youtube_url": "https://vimeo.com/123"})
    assert response.status_code == 400


def test_upload_from_youtube_cleans_up_the_downloaded_file_if_storing_it_fails(client, monkeypatch, tmp_path_factory):
    import backend.api.videos as videos_module

    monkeypatch.setattr(videos_module.youtube, "download", _fake_download(tmp_path_factory))

    downloaded_paths: list[Path] = []
    original_save_from_path = videos_module.video_store.save_from_path

    def _boom(path, filename):
        downloaded_paths.append(path)
        raise RuntimeError("disk exploded")

    monkeypatch.setattr(videos_module.video_store, "save_from_path", _boom)

    response = client.post("/api/videos/upload-from-youtube", json={"youtube_url": "https://youtu.be/dQw4w9WgXcQ"})
    assert response.status_code == 500
    assert downloaded_paths and not downloaded_paths[0].exists()

    monkeypatch.setattr(videos_module.video_store, "save_from_path", original_save_from_path)
