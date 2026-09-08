"""Separate liveness from dependency-aware production readiness."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import _engine
from backend.contracts import CONTRACT_VERSION


router = APIRouter(prefix="/api/health", tags=["health"])
Probe = Callable[[], Awaitable[None]]


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
