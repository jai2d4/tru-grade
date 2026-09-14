"""Real end-to-end backup/restore drill — scripts/backup_db.py and
scripts/restore_db.py, proven against a real, disposable Postgres database
rather than just asserted to look right. Creates and destroys its own
throwaway database; never touches the shared test database."""
from __future__ import annotations

import gzip
import subprocess
from pathlib import Path

import pytest

from app.core.config import get_settings
from scripts.backup_db import run_backup
from scripts.restore_db import run_restore


@pytest.fixture(autouse=True)
def _skip_without_db(db_available):
    available, reason = db_available
    if not available:
        pytest.skip(f"No PostgreSQL reachable — set POSTGRES_* env vars to run these tests. ({reason})")


def _maintenance_dsn(settings) -> str:
    """A DSN to the default `postgres` database — CREATE/DROP DATABASE can't
    run against the database the connection is already using."""
    return (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/postgres"
    )


def _run(dsn: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["psql", dsn, *args], capture_output=True)


def test_backup_then_restore_round_trips_real_data_through_a_dropped_database(tmp_path):
    settings = get_settings()
    if settings.DATABASE_URL or not settings.POSTGRES_PASSWORD:
        pytest.skip("This drill needs POSTGRES_* fields to build a throwaway database.")

    maintenance_dsn = _maintenance_dsn(settings)
    drill_db = "trugrade_backup_restore_drill"
    drill_dsn = (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{drill_db}"
    )
    schema_path = Path(__file__).resolve().parent.parent / "db" / "init_schema.sql"

    _run(maintenance_dsn, "-c", f"DROP DATABASE IF EXISTS {drill_db};")
    assert _run(maintenance_dsn, "-c", f"CREATE DATABASE {drill_db};").returncode == 0

    try:
        assert _run(drill_dsn, "-f", str(schema_path)).returncode == 0
        assert _run(
            drill_dsn, "-c",
            "INSERT INTO athletes (first_name, last_name, position, school, grad_year) "
            "VALUES ('Drill', 'Athlete', 'QB', 'Round Trip High', 2029);",
        ).returncode == 0

        # --- the actual backup, via the real script's own function ---
        backup_path = run_backup(drill_dsn, tmp_path)
        assert backup_path.is_file()
        with gzip.open(backup_path, "rb") as handle:
            dump = handle.read().decode()
        assert "CREATE TABLE" in dump
        assert "Drill" in dump  # the real row made it into the dump, not just the schema

        # --- the disaster this drill exists to survive ---
        _run(maintenance_dsn, "-c", f"DROP DATABASE {drill_db};")
        assert _run(maintenance_dsn, "-c", f"CREATE DATABASE {drill_db};").returncode == 0
        # The fresh database is genuinely empty — querying athletes fails outright.
        assert _run(drill_dsn, "-c", "SELECT * FROM athletes;").returncode != 0

        # --- the actual restore, via the real script's own function ---
        result = run_restore(drill_dsn, backup_path)
        assert result.returncode == 0, result.stderr.decode()

        check = _run(
            drill_dsn, "-t", "-c",
            "SELECT first_name || ' ' || last_name || ' ' || school FROM athletes WHERE first_name='Drill';",
        )
        assert "Drill Athlete Round Trip High" in check.stdout.decode()
    finally:
        _run(maintenance_dsn, "-c", f"DROP DATABASE IF EXISTS {drill_db};")
