"""The Postgres-backed analysis job queue — backend/jobs/store.py.

Real database, no mocks: the whole point of this table is that two
separate machines coordinate through it, and the concurrency guarantee
(SELECT ... FOR UPDATE SKIP LOCKED) only exists in Postgres. Testing it
against a fake would prove nothing.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.db import async_session
from backend.jobs import store


@pytest.fixture(autouse=True)
def _skip_without_db(db_available):
    available, reason = db_available
    if not available:
        pytest.skip(f"No PostgreSQL reachable — set POSTGRES_* env vars to run these tests. ({reason})")


@pytest.fixture(autouse=True)
def _empty_queue(db_available):
    """Start every test from an empty queue.

    These tests assert on FIFO order and on "exactly one worker wins",
    which only hold when the table is empty — a job left behind by an
    earlier test (or an earlier run, since the database outlives the
    process) would be claimed instead of the one under test. Same
    reasoning as clean_accounts_tables in tests/conftest.py.
    """
    available, _ = db_available
    if not available:
        yield
        return

    import asyncpg
    from app.core.config import get_settings

    settings = get_settings()

    async def _truncate():
        conn = await asyncpg.connect(
            host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
        )
        try:
            await conn.execute("TRUNCATE analysis_jobs")
        finally:
            await conn.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_truncate())
    finally:
        loop.close()
    yield


def _run(coro):
    """Each test drives its own loop — asyncpg connections are loop-bound
    (see the note in tests/conftest.py's client fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(_dispose())
        loop.close()


async def _dispose():
    from app.core.db import _engine
    await _engine.dispose()


def test_enqueued_job_starts_queued_and_is_readable_back():
    async def scenario():
        video_id = str(uuid4())
        async with async_session() as db:
            job = await store.enqueue(db, video_id)
            job_id = str(job.job_id)
        async with async_session() as db:
            found = await store.get(db, job_id)
        return job_id, video_id, found

    job_id, video_id, found = _run(scenario())
    assert found is not None
    assert found.status == "queued"
    assert found.progress == 0
    assert str(found.video_id) == video_id
    payload = store.as_dict(found)
    # The UI's AnalysisJob contract (frontend/src/api/types.ts) — unchanged
    # by the move off JSON files.
    assert payload["job_id"] == job_id
    assert payload["status"] == "queued"
    assert set(payload) >= {"job_id", "video_id", "status", "progress", "message", "error"}


def test_get_returns_none_for_a_malformed_id_rather_than_raising():
    """A bad id in the URL is a 404, not a 500."""
    async def scenario():
        async with async_session() as db:
            return await store.get(db, "not-a-uuid")

    assert _run(scenario()) is None


def test_claim_takes_the_oldest_queued_job_and_marks_the_worker():
    async def scenario():
        async with async_session() as db:
            first = await store.enqueue(db, str(uuid4()))
            first_id = str(first.job_id)
        async with async_session() as db:
            await store.enqueue(db, str(uuid4()))
        async with async_session() as db:
            claimed = await store.claim_next(db, "worker-a")
        return first_id, claimed

    first_id, claimed = _run(scenario())
    assert claimed is not None
    assert str(claimed.job_id) == first_id, "FIFO: the oldest queued job is claimed first"
    assert claimed.status == "claimed"
    assert claimed.claimed_by == "worker-a"
    assert claimed.attempts == 1
    assert claimed.heartbeat_at is not None


def test_two_workers_never_claim_the_same_job():
    """The core concurrency guarantee. With exactly one job queued, two
    concurrent claimers must produce one winner and one empty-handed
    worker — never the same job twice."""
    async def scenario():
        async with async_session() as db:
            job = await store.enqueue(db, str(uuid4()))
            only_id = str(job.job_id)

        async def claim(worker: str):
            async with async_session() as db:
                got = await store.claim_next(db, worker)
                return str(got.job_id) if got else None

        a, b = await asyncio.gather(claim("worker-a"), claim("worker-b"))
        return only_id, a, b

    only_id, a, b = _run(scenario())
    claimed = [x for x in (a, b) if x is not None]
    assert claimed == [only_id], f"exactly one worker should win, got a={a!r} b={b!r}"


def test_claim_returns_none_when_the_queue_is_empty():
    async def scenario():
        # Drain anything left by other tests, then confirm an empty queue.
        async with async_session() as db:
            while await store.claim_next(db, "drainer"):
                pass
        async with async_session() as db:
            return await store.claim_next(db, "worker-a")

    assert _run(scenario()) is None


def test_progress_updates_land_and_refresh_the_heartbeat():
    async def scenario():
        async with async_session() as db:
            job = await store.enqueue(db, str(uuid4()))
            job_id = str(job.job_id)
        async with async_session() as db:
            await store.claim_next(db, "worker-a")
        async with async_session() as db:
            await store.update(db, job_id, status="detecting", progress=42, frame_count=1200)
        async with async_session() as db:
            return await store.get(db, job_id)

    job = _run(scenario())
    assert job.status == "detecting"
    assert job.progress == 42
    assert job.frame_count == 1200
    assert job.heartbeat_at is not None


def test_finish_clears_the_claim_so_it_is_not_mistaken_for_live_work():
    async def scenario():
        async with async_session() as db:
            job = await store.enqueue(db, str(uuid4()))
            job_id = str(job.job_id)
        async with async_session() as db:
            await store.claim_next(db, "worker-a")
        async with async_session() as db:
            await store.finish(db, job_id, status="completed", progress=100, track_count=7)
        async with async_session() as db:
            return await store.get(db, job_id)

    job = _run(scenario())
    assert job.status == "completed"
    assert job.progress == 100
    assert job.track_count == 7
    assert job.claimed_by is None and job.claimed_at is None


def test_a_dead_workers_job_is_returned_to_the_queue():
    """If the worker machine reboots mid-job, the member must not be left
    watching a progress bar that never moves."""
    async def scenario():
        async with async_session() as db:
            job = await store.enqueue(db, str(uuid4()))
            job_id = str(job.job_id)
        async with async_session() as db:
            await store.claim_next(db, "doomed-worker")
        # Backdate the heartbeat to simulate a worker that stopped responding.
        async with async_session() as db:
            await store.update(
                db, job_id, status="detecting",
                heartbeat_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        async with async_session() as db:
            recovered = await store.requeue_stale(db)
        async with async_session() as db:
            return recovered, await store.get(db, job_id)

    recovered, job = _run(scenario())
    assert recovered >= 1
    assert job.status == "queued"
    assert job.claimed_by is None
    assert "stopped responding" in (job.message or "")


def test_a_live_workers_job_is_left_alone_by_the_stale_sweep():
    """The sweep must not steal work from a worker that is healthy."""
    async def scenario():
        async with async_session() as db:
            job = await store.enqueue(db, str(uuid4()))
            job_id = str(job.job_id)
        async with async_session() as db:
            await store.claim_next(db, "healthy-worker")
        async with async_session() as db:
            await store.update(db, job_id, status="detecting", progress=10)  # fresh heartbeat
        async with async_session() as db:
            await store.requeue_stale(db)
        async with async_session() as db:
            return await store.get(db, job_id)

    job = _run(scenario())
    assert job.status == "detecting"
    assert job.claimed_by == "healthy-worker"


def test_completed_jobs_are_never_resurrected_by_the_stale_sweep():
    async def scenario():
        async with async_session() as db:
            job = await store.enqueue(db, str(uuid4()))
            job_id = str(job.job_id)
        async with async_session() as db:
            await store.claim_next(db, "worker-a")
        async with async_session() as db:
            await store.finish(
                db, job_id, status="completed", progress=100,
                heartbeat_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        async with async_session() as db:
            await store.requeue_stale(db)
        async with async_session() as db:
            return await store.get(db, job_id)

    assert _run(scenario()).status == "completed"


# ---------- poison-pill protection ----------


def test_a_job_that_keeps_killing_workers_is_eventually_failed_not_retried_forever():
    """The failure this guards against is specific and silent.

    A job that kills its worker hard — OOM on an oversized film, a
    segfault, the box rebooting — never reaches the handler that marks it
    failed. requeue_stale() puts it back, the next worker dies the same
    way, and because claiming takes the OLDEST job first, that one upload
    blocks the whole queue indefinitely.
    """
    from backend.jobs.store import MAX_ATTEMPTS

    async def scenario():
        async with async_session() as db:
            job = await store.enqueue(db, str(uuid4()))
            job_id = str(job.job_id)

        # Each round: a worker claims it, then dies without reporting.
        for _ in range(MAX_ATTEMPTS):
            async with async_session() as db:
                await store.claim_next(db, "doomed-worker")
            async with async_session() as db:
                await store.update(
                    db, job_id, status="detecting",
                    heartbeat_at=datetime.now(timezone.utc) - timedelta(hours=1),
                )
            async with async_session() as db:
                await store.requeue_stale(db)

        async with async_session() as db:
            return await store.get(db, job_id)

    job = _run(scenario())
    assert job.status == "failed", (
        f"after {MAX_ATTEMPTS} worker deaths the job is still {job.status!r} — "
        "it would keep taking down workers and blocking the queue"
    )
    assert job.attempts >= MAX_ATTEMPTS
    assert job.claimed_by is None
    assert "Gave up after" in (job.error or "")


def test_a_job_under_the_attempt_cap_is_still_retried():
    """One transient crash (a reboot, a blip) must not condemn a job."""
    async def scenario():
        async with async_session() as db:
            job = await store.enqueue(db, str(uuid4()))
            job_id = str(job.job_id)
        async with async_session() as db:
            await store.claim_next(db, "unlucky-worker")
        async with async_session() as db:
            await store.update(
                db, job_id, status="detecting",
                heartbeat_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        async with async_session() as db:
            await store.requeue_stale(db)
        async with async_session() as db:
            return await store.get(db, job_id)

    job = _run(scenario())
    assert job.status == "queued"
    assert job.attempts == 1
    assert "returned to the queue" in (job.message or "")


def test_an_exhausted_job_stops_blocking_the_rest_of_the_queue():
    """The point of failing it: work behind the poison pill must move."""
    from backend.jobs.store import MAX_ATTEMPTS

    async def scenario():
        async with async_session() as db:
            poison = await store.enqueue(db, str(uuid4()))
            poison_id = str(poison.job_id)
        async with async_session() as db:
            healthy = await store.enqueue(db, str(uuid4()))
            healthy_id = str(healthy.job_id)

        for _ in range(MAX_ATTEMPTS):
            async with async_session() as db:
                claimed = await store.claim_next(db, "doomed")
            async with async_session() as db:
                await store.update(
                    db, str(claimed.job_id), status="detecting",
                    heartbeat_at=datetime.now(timezone.utc) - timedelta(hours=1),
                )
            async with async_session() as db:
                await store.requeue_stale(db)

        # The next claim must be the healthy job, not the poison one again.
        async with async_session() as db:
            nxt = await store.claim_next(db, "fresh-worker")
        return poison_id, healthy_id, str(nxt.job_id) if nxt else None

    poison_id, healthy_id, claimed_next = _run(scenario())
    assert claimed_next == healthy_id, (
        "the exhausted job was claimed again instead of the healthy one behind it"
    )
    assert claimed_next != poison_id
