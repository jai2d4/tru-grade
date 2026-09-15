"""Worker liveness, and the honesty that depends on it.

The problem this solves is live right now on the deployed site: the web
service was split away from the CV stack, so nothing is processing film
there. A queued job with no worker running is indistinguishable, through
the API, from one waiting its turn — so the UI showed a progress bar that
would never move.

These tests pin the behaviour that a queued job with no live worker says
so, and that the same wording never appears when a worker IS alive
(which would be its own kind of lie).
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture(autouse=True)
def _skip_without_db(db_available):
    available, reason = db_available
    if not available:
        pytest.skip(f"No PostgreSQL reachable — set POSTGRES_* env vars to run these tests. ({reason})")


def _sql(query: str, *args):
    """Standalone asyncpg connection — never the shared engine, whose pool
    is bound to the TestClient's loop (see tests/conftest.py)."""
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


@pytest.fixture(autouse=True)
def _no_workers():
    """Every test starts with nobody home, and leaves nothing behind."""
    _sql("DELETE FROM worker_heartbeats")
    yield
    _sql("DELETE FROM worker_heartbeats")


def _mark_worker_alive(worker_id="test-worker", *, seconds_ago=0, device="cuda"):
    seen = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    _sql(
        "INSERT INTO worker_heartbeats (worker_id, last_seen_at, device) VALUES ($1, $2, $3) "
        "ON CONFLICT (worker_id) DO UPDATE SET last_seen_at = $2, device = $3",
        worker_id, seen, device,
    )


def _queued_job(video_id: str | None = None) -> str:
    rows = _sql(
        "INSERT INTO analysis_jobs (video_id, status, progress, message) "
        "VALUES ($1, 'queued', 0, 'Analysis queued.') RETURNING job_id",
        uuid.UUID(video_id or str(uuid.uuid4())),
    )
    return str(rows[0]["job_id"])


# ---------- the workers endpoint ----------


def test_workers_endpoint_says_plainly_when_nothing_is_running(client):
    body = client.get("/api/analysis/workers").json()
    assert body["available"] is False
    assert body["workers"] == []
    assert "No analysis worker is running" in body["detail"]


def test_workers_endpoint_lists_a_live_worker(client):
    _mark_worker_alive("gpu-box:1234", device="cuda")
    body = client.get("/api/analysis/workers").json()
    assert body["available"] is True
    assert [w["worker_id"] for w in body["workers"]] == ["gpu-box:1234"]
    assert body["workers"][0]["device"] == "cuda"


def test_a_worker_that_stopped_reporting_is_not_counted_as_available(client):
    """Liveness has to expire, or a worker that died last week still reads
    as capacity and the queue looks healthy when it isn't."""
    _mark_worker_alive("ghost", seconds_ago=60 * 60)
    body = client.get("/api/analysis/workers").json()
    assert body["available"] is False
    assert body["workers"] == []


# ---------- job status honesty ----------


def test_queued_job_with_no_worker_says_so_instead_of_implying_progress(client):
    job_id = _queued_job()
    body = client.get(f"/api/analysis/status/{job_id}").json()

    assert body["status"] == "queued"
    assert body["worker_available"] is False
    assert "No worker is currently running" in body["message"]
    # Honest about the consequence, not alarming: the work isn't lost.
    assert "queued" in body["message"].lower()


def test_queued_job_with_a_live_worker_does_not_claim_nothing_is_running(client):
    _mark_worker_alive()
    job_id = _queued_job()
    body = client.get(f"/api/analysis/status/{job_id}").json()

    assert body["worker_available"] is True
    assert "No worker is currently running" not in (body["message"] or "")


def test_a_running_job_is_never_labelled_as_having_no_worker(client):
    """Only the queued state can be starved. A job already in progress has
    a worker by definition, and must not be second-guessed."""
    job_id = _queued_job()
    _sql("UPDATE analysis_jobs SET status='detecting', progress=40 WHERE job_id=$1", uuid.UUID(job_id))

    body = client.get(f"/api/analysis/status/{job_id}").json()
    assert body["status"] == "detecting"
    assert body["worker_available"] is True
    assert "No worker" not in (body["message"] or "")


def test_the_job_payload_shape_the_ui_depends_on_is_unchanged(client):
    """worker_available is additive — every key the UI already reads must
    still be present."""
    job_id = _queued_job()
    body = client.get(f"/api/analysis/status/{job_id}").json()
    assert set(body) >= {
        "job_id", "video_id", "status", "progress", "message", "error",
        "frame_count", "detection_frames", "track_count", "biomechanics",
    }


# ---------- identity status honesty ----------


def test_queued_identification_with_no_worker_says_so(client):
    upload = client.post("/api/videos/upload", files={"file": ("g.mp4", b"x", "video/mp4")})
    video_id = upload.json()["video_id"]

    import backend.api.videos as videos_module
    tracks = videos_module.storage_root / "vision" / video_id / "tracks.json"
    tracks.parent.mkdir(parents=True, exist_ok=True)
    tracks.write_text(json.dumps([{"track_id": 1, "positions": []}]), encoding="utf-8")

    client.post(f"/api/videos/{video_id}/identify",
                json={"jersey_number": "7", "school_colors": "navy"})

    body = client.get(f"/api/videos/{video_id}/identify").json()
    assert body["status"] == "processing"       # still the UI's polling state
    assert body["selected_track_id"] is None    # nothing invented
    assert "No worker is currently running" in body["status_detail"]
