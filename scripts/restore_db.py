"""Restore a TruGrade database from a backup made by scripts/backup_db.py.

DESTRUCTIVE toward whatever database DATABASE_URL/POSTGRES_* currently
point at — the dump replays every CREATE TABLE and INSERT it contains, so
it expects an empty (or throwaway) target database. Never run this against
a database holding data you want to keep without first taking a fresh
backup of THAT database.

Usage:
    python scripts/restore_db.py path/to/trugrade-backup-*.sql.gz

Requires the `psql` client tool on PATH (the `postgresql-client` package
on Debian/Ubuntu).
"""
from __future__ import annotations

import gzip
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.config import get_settings  # noqa: E402


def run_restore(dsn: str, backup_path: Path) -> subprocess.CompletedProcess:
    with gzip.open(backup_path, "rb") as handle:
        sql = handle.read()
    return subprocess.run(["psql", dsn], input=sql, capture_output=True)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/restore_db.py path/to/backup.sql.gz", file=sys.stderr)
        raise SystemExit(1)

    if shutil.which("psql") is None:
        print("[restore_db] psql not found on PATH — install the postgresql-client package.", file=sys.stderr)
        raise SystemExit(1)

    backup_path = Path(sys.argv[1])
    if not backup_path.is_file():
        print(f"[restore_db] {backup_path} does not exist.", file=sys.stderr)
        raise SystemExit(1)

    settings = get_settings()
    target = settings.POSTGRES_DB if not settings.DATABASE_URL else "(from DATABASE_URL)"
    print(f"[restore_db] restoring {backup_path} into database {target} ...")

    result = run_restore(settings.asyncpg_dsn, backup_path)
    sys.stdout.write(result.stdout.decode(errors="replace"))
    sys.stderr.write(result.stderr.decode(errors="replace"))
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    print("[restore_db] restore complete.")


if __name__ == "__main__":
    main()
