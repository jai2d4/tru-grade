"""Shared fixtures for backend/tests — mirrors tests/conftest.py's pattern,
but wraps backend.main:app (not app.main:app) since these tests exercise
the V2 routers backend.main adds on top."""
import os

os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", os.environ.get("POSTGRES_DB", "tru_scouting_test"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A fresh TestClient per test, storage_root redirected to a throwaway
    tmp_path so tests never touch backend/storage/ or each other's files.
    Disposes the SQLAlchemy engine's connection pool afterward — see
    tests/conftest.py's client fixture for why that matters across tests
    that each run their own event loop."""
    monkeypatch.setenv("TRUGRADE_STORAGE_DIR", str(tmp_path))
    import backend.api.players as players_module
    import backend.api.reports as reports_module
    import backend.api.videos as videos_module
    from backend.grading.service import GradeStore
    from backend.video.ingestion import VideoStore
    store = VideoStore(tmp_path)
    # players.py and reports.py both did `from backend.api.videos import
    # storage_root`, which bound their own module-level names at import
    # time — patching videos_module's attributes alone would not reach
    # them. reports.py also derives grade_store and report_jobs_dir from
    # storage_root once at import time, so those need recomputing too, not
    # just the raw path.
    for module in (videos_module, players_module):
        monkeypatch.setattr(module, "storage_root", tmp_path)
        monkeypatch.setattr(module, "video_store", store)
    monkeypatch.setattr(reports_module, "storage_root", tmp_path)
    monkeypatch.setattr(reports_module, "grade_store", GradeStore(tmp_path / "grades"))
    report_jobs_dir = tmp_path / "report_jobs"
    report_jobs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(reports_module, "report_jobs_dir", report_jobs_dir)

    import backend.main as m
    from app.core.db import _engine
    with TestClient(m.app) as c:
        yield c
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_engine.dispose())
    finally:
        loop.close()


@pytest.fixture(scope="session")
def db_available():
    """Skips DB-dependent tests gracefully when no PostgreSQL is reachable."""
    import asyncio
    import asyncpg
    from app.core.config import get_settings

    settings = get_settings()

    async def _ping():
        conn = await asyncpg.connect(
            host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
        )
        await conn.close()

    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_ping())
        finally:
            loop.close()
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
