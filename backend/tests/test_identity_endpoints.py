"""HTTP contract for automatic jersey identification.

These endpoints were rewritten when identification moved off the web
service onto the worker queue, and the UI polls them on a loop
(frontend/src/features/film/useFilmAnalysis.ts). Only the algorithm had
coverage before, not the endpoints, so the response shape the UI depends
on was unpinned across that rewrite.

The statuses matter specifically: the UI branches on "processing",
"failed" and "identified", and treats anything else — notably
"confirmation_required" — as "evidence was uncertain, ask a human".
Nothing here may quietly start returning a status outside that set.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest


@pytest.fixture(autouse=True)
def _skip_without_db(db_available):
    available, reason = db_available
    if not available:
        pytest.skip(f"No PostgreSQL reachable — set POSTGRES_* env vars to run these tests. ({reason})")


def _sql(query: str, *args):
    """Run one statement on a standalone asyncpg connection.

    Deliberately NOT the shared SQLAlchemy engine: its pooled connections
    are bound to the TestClient's event loop, and touching that pool from
    a throwaway loop poisons it for every later test — the same hazard
    tests/conftest.py's db_available fixture documents.
    """
    import asyncpg
    from app.core.config import get_settings

    settings = get_settings()

    async def run():
        conn = await asyncpg.connect(
            host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
        )
        try:
            return await conn.fetch(query, *args)
        finally:
            await conn.close()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run())
    finally:
        loop.close()


def _latest_identity_job(video_id: str):
    rows = _sql(
        "SELECT job_id, job_type, status, payload FROM analysis_jobs "
        "WHERE video_id = $1 AND job_type = 'identity' ORDER BY created_at DESC LIMIT 1",
        uuid.UUID(video_id),
    )
    return rows[0] if rows else None


def _complete_identity_job(video_id: str, result: dict) -> None:
    """Stand in for the worker finishing the job."""
    job = _latest_identity_job(video_id)
    assert job is not None, "no identity job was queued"
    _sql(
        "UPDATE analysis_jobs SET status='completed', progress=100, result=$2 WHERE job_id=$1",
        job["job_id"], json.dumps(result),
    )


@pytest.fixture
def video_with_tracks(client, tmp_path, monkeypatch):
    """A stored video that has finished tracking — the precondition for
    identification."""
    import backend.api.players as players_module
    import backend.api.videos as videos_module

    response = client.post(
        "/api/videos/upload",
        files={"file": ("game.mp4", b"not-really-a-video", "video/mp4")},
    )
    assert response.status_code == 201, response.text
    video_id = response.json()["video_id"]

    tracks_path = videos_module.storage_root / "vision" / video_id / "tracks.json"
    tracks_path.parent.mkdir(parents=True, exist_ok=True)
    tracks_path.write_text(json.dumps([{"track_id": 1, "positions": []}]), encoding="utf-8")
    assert players_module._track_path(video_id).is_file()
    return video_id


IDENTIFY_BODY = {"jersey_number": "7", "school_colors": "navy and gold"}


def test_identify_returns_404_before_anything_has_been_requested(client, video_with_tracks):
    response = client.get(f"/api/videos/{video_with_tracks}/identify")
    assert response.status_code == 404


def test_identify_requires_tracking_to_have_completed(client):
    """Without tracks there is nothing to identify against, and the UI
    relies on this 409 rather than a job that can only fail later."""
    response = client.post(
        "/api/videos/upload",
        files={"file": ("untracked.mp4", b"bytes", "video/mp4")},
    )
    video_id = response.json()["video_id"]
    started = client.post(f"/api/videos/{video_id}/identify", json=IDENTIFY_BODY)
    assert started.status_code == 409


def test_starting_identification_enqueues_a_job_and_reports_processing(client, video_with_tracks):
    started = client.post(f"/api/videos/{video_with_tracks}/identify", json=IDENTIFY_BODY)
    assert started.status_code == 202
    body = started.json()
    assert body["status"] == "processing"
    assert body["selected_track_id"] is None
    assert body["confidence"] == 0

    # Queued for a worker — not executed inside this request.
    polled = client.get(f"/api/videos/{video_with_tracks}/identify").json()
    assert polled["status"] == "processing"


def test_the_queued_job_carries_the_request_payload_to_the_worker(client, video_with_tracks):
    client.post(f"/api/videos/{video_with_tracks}/identify", json={
        **IDENTIFY_BODY, "player_id": "jersey-7", "position": "CB",
    })

    job = _latest_identity_job(video_with_tracks)
    assert job is not None
    assert job["job_type"] == "identity"
    assert job["status"] == "queued"
    payload = json.loads(job["payload"])
    assert payload["jersey_number"] == "7"
    assert payload["school_colors"] == "navy and gold"
    assert payload["player_id"] == "jersey-7"
    assert payload["position"] == "CB"


@pytest.mark.parametrize(
    "worker_result",
    [
        {"status": "identified", "selected_track_id": 3, "confidence": 0.88,
         "status_detail": "Automatic multi-frame identification completed."},
        {"status": "confirmation_required", "selected_track_id": None, "confidence": 0.41,
         "status_detail": "Evidence was not conclusive."},
        {"status": "failed", "selected_track_id": None, "confidence": 0,
         "error": "easyocr exploded", "status_detail": "Automatic identification failed."},
    ],
    ids=["identified", "uncertain", "failed"],
)
def test_the_workers_result_is_served_back_verbatim(client, video_with_tracks, worker_result):
    """Every branch the UI switches on must survive the round trip through
    Postgres unchanged — the worker's disk isn't readable by the web
    service, so this row is the only channel between them."""
    client.post(f"/api/videos/{video_with_tracks}/identify", json=IDENTIFY_BODY)
    _complete_identity_job(video_with_tracks, worker_result)

    served = client.get(f"/api/videos/{video_with_tracks}/identify")
    assert served.status_code == 200
    assert served.json() == worker_result


def test_a_second_run_reports_the_newest_result_not_a_stale_one(client, video_with_tracks):
    """Re-identifying (a coach correcting the jersey number) must not keep
    serving the previous run's answer."""
    client.post(f"/api/videos/{video_with_tracks}/identify", json=IDENTIFY_BODY)
    _complete_identity_job(video_with_tracks,
                           {"status": "identified", "selected_track_id": 1, "confidence": 0.7})

    client.post(f"/api/videos/{video_with_tracks}/identify",
                json={**IDENTIFY_BODY, "jersey_number": "22"})
    _complete_identity_job(video_with_tracks,
                           {"status": "identified", "selected_track_id": 9, "confidence": 0.95})

    served = client.get(f"/api/videos/{video_with_tracks}/identify").json()
    assert served["selected_track_id"] == 9
