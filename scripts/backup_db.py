"""Create a timestamped, portable backup of the TruGrade database.

Independent of Render's own managed backups — a second, downloadable copy
that survives even a lost/deleted Render account, an accidental database
deletion, or a plan downgrade, and that plain `psql` can restore on its own,
with no dependency on Render at all.

Usage:
    python scripts/backup_db.py [output_dir]     # defaults to ./backups

Reads the same DATABASE_URL / POSTGRES_* env vars the app itself uses (see
app/core/config.py), so it backs up whatever database the app is currently
pointed at — run it with production's env vars to back up production.
Requires the `pg_dump` client tool on PATH (the `postgresql-client` package
on Debian/Ubuntu).
"""
from __future__ import annotations

import gzip
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.config import get_settings  # noqa: E402


def run_backup(dsn: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = output_dir / f"trugrade-backup-{timestamp}.sql.gz"

    result = subprocess.run(["pg_dump", dsn, "--no-owner", "--no-privileges"], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed:\n{result.stderr.decode(errors='replace')}")

    with gzip.open(dest, "wb") as handle:
        handle.write(result.stdout)
    return dest


def main() -> None:
    if shutil.which("pg_dump") is None:
        print("[backup_db] pg_dump not found on PATH — install the postgresql-client package.", file=sys.stderr)
        raise SystemExit(1)

    settings = get_settings()
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("backups")

    try:
        dest = run_backup(settings.asyncpg_dsn, output_dir)
    except RuntimeError as exc:
        print(f"[backup_db] {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(f"[backup_db] wrote {dest} ({dest.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
