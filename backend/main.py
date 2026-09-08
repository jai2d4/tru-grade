"""Stable Phase 1 backend entrypoint.

The existing FastAPI application remains the source of truth during the safe
restructure. Later phases can move routers behind this entrypoint without
changing the Windows launcher or public server command.
"""

from fastapi import Depends

from app.main import app
from backend.api.analysis import router as analysis_router
from backend.api.football import router as football_router
from backend.api.players import router as players_router
from backend.api.reports import router as reports_router
from backend.api.videos import router as videos_router
from backend.contracts import ContractDescriptor, descriptor
from backend.health import router as health_router
from backend.security import require_identity, validate_identity_configuration


v2_identity = [Depends(require_identity)]
app.include_router(videos_router, dependencies=v2_identity)
app.include_router(analysis_router, dependencies=v2_identity)
app.include_router(players_router, dependencies=v2_identity)
app.include_router(football_router, dependencies=v2_identity)
app.include_router(reports_router, dependencies=v2_identity)
app.include_router(health_router)
app.add_event_handler("startup", validate_identity_configuration)


@app.get("/api/contracts/v1", response_model=ContractDescriptor, tags=["contract"])
async def api_contract_v1() -> ContractDescriptor:
    """Describe the stable compatibility contract used during UI migration."""

    return descriptor()

__all__ = ["app"]
