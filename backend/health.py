"""Separate liveness from dependency-aware production readiness."""
from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import _engine
from backend.contracts import CONTRACT_VERSION


router = APIRouter(prefix="/api/health", tags=["health"])
Probe = Callable[[], Awaitable[None]]

_PROCESS_STARTED_AT = time.monotonic()


class DependencyCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    detail: str | None = None


class HealthResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    contract_version: str = CONTRACT_VERSION
    checks: dict[str, DependencyCheck] | None = None


async def database_probe() -> None:
    async with _engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def storage_probe() -> None:
    root = Path(get_settings().UPLOAD_TMP_DIR)

    def write_test() -> None:
        root.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(prefix=".trugrade-ready-", dir=root, delete=True) as handle:
            handle.write(b"ready")
            handle.flush()

    await asyncio.to_thread(write_test)


def get_readiness_probes() -> dict[str, Probe]:
    """Dependency seam for tests and future storage/job adapters."""

    return {"database": database_probe, "storage": storage_probe}


async def check_readiness(probes: dict[str, Probe], timeout_seconds: float = 2.0) -> HealthResult:
    checks: dict[str, DependencyCheck] = {}
    for name, probe in probes.items():
        try:
            await asyncio.wait_for(probe(), timeout=timeout_seconds)
            checks[name] = DependencyCheck(status="ok")
        except Exception as exc:  # readiness must report, not crash
            checks[name] = DependencyCheck(status="failed", detail=type(exc).__name__)
    ready = all(check.status == "ok" for check in checks.values())
    return HealthResult(status="ready" if ready else "not_ready", checks=checks)


@router.get("/live", response_model=HealthResult)
async def liveness() -> HealthResult:
    return HealthResult(status="live")


@router.get("/ready", response_model=HealthResult)
async def readiness(
    response: Response,
    probes: dict[str, Probe] = Depends(get_readiness_probes),
) -> HealthResult:
    result = await check_readiness(probes)
    if result.status != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


class StatusResult(BaseModel):
    """A richer, single-call diagnostic report — meant for an external
    monitor (a status dashboard, an on-call bot, a control center like a
    self-hosted ops tool) that wants more than a bare up/down. Never
    includes a secret value — only whether one is configured."""
    model_config = ConfigDict(extra="forbid")

    status: str
    contract_version: str = CONTRACT_VERSION
    environment: str
    uptime_seconds: float
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    checks: dict[str, DependencyCheck]
    gemini_configured: bool
    api_key_configured: bool


@router.get("/status", response_model=StatusResult)
async def detailed_status(
    response: Response,
    probes: dict[str, Probe] = Depends(get_readiness_probes),
) -> StatusResult:
    """Public, unauthenticated, read-only — same trust level as /live and
    /ready (an external monitor needs this to work without a credential),
    and just as careful never to leak anything secret through it."""
    settings = get_settings()
    readiness_result = await check_readiness(probes)
    if readiness_result.status != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return StatusResult(
        status=readiness_result.status,
        environment=settings.APP_ENV,
        uptime_seconds=round(time.monotonic() - _PROCESS_STARTED_AT, 1),
        # RENDER_GIT_COMMIT / RENDER_GIT_BRANCH are set automatically by
        # Render on every deploy; both are None when running elsewhere
        # (local dev, another host) rather than a confusing empty string.
        git_commit=os.environ.get("RENDER_GIT_COMMIT"),
        git_branch=os.environ.get("RENDER_GIT_BRANCH"),
        checks=readiness_result.checks or {},
        gemini_configured=bool(settings.GEMINI_API_KEY),
        api_key_configured=bool(settings.API_KEY),
    )
