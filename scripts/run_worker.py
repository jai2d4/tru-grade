"""Entry point for the TruGrade analysis worker.

Run this on the GPU machine:

    python scripts/run_worker.py

It polls the shared Postgres queue for film-analysis jobs, runs them
locally, and writes results back. It serves no HTTP and needs no inbound
network access — see docs/WORKER_SETUP_BRIEF.md.

Required environment (same values the web service uses):
    DATABASE_URL  (or the POSTGRES_* set)   — the shared queue
    GEMINI_API_KEY                          — read at import by app.core.config
    TRUGRADE_STORAGE_DIR                    — where film and frames live

Optional:
    WORKER_ID                 label for this worker in the queue
    WORKER_POLL_INTERVAL_S    default 5
    ANALYSIS_FPS              default "native" (every source frame)
    ENABLE_BIOMECHANICS       default false
    TRUGRADE_DEVICE           auto | cpu | cuda
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Allow `python scripts/run_worker.py` from the repo root without installing
# the project as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging_config import configure_logging  # noqa: E402
from backend.jobs.worker import main  # noqa: E402


if __name__ == "__main__":
    import os

    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger("tru.worker").info("worker stopped by operator")
