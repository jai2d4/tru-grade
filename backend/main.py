"""Stable Phase 1 backend entrypoint.

The existing FastAPI application remains the source of truth during the safe
restructure. Later phases can move routers behind this entrypoint without
changing the Windows launcher or public server command.
"""
from pathlib import Path

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.main import app
from backend.api.analysis import router as analysis_router
from backend.api.videos import router as videos_router
from backend.api.players import router as players_router
from backend.api.football import router as football_router
from backend.api.reports import router as reports_router
from backend.contracts import ContractDescriptor, descriptor
from backend.health import router as health_router
from backend.security import require_identity, validate_identity_configuration


# Fail before the ASGI server can expose a production deployment. This is an
# import-time configuration check, so it does not depend on deprecated FastAPI
# startup-event APIs.
validate_identity_configuration()

v2_identity = [Depends(require_identity)]
app.include_router(videos_router, dependencies=v2_identity)
app.include_router(analysis_router, dependencies=v2_identity)
app.include_router(players_router, dependencies=v2_identity)
app.include_router(football_router, dependencies=v2_identity)
app.include_router(reports_router, dependencies=v2_identity)
app.include_router(health_router)


@app.get("/api/contracts/v1", response_model=ContractDescriptor, tags=["contract"])
async def api_contract_v1() -> ContractDescriptor:
    """Describe the stable compatibility contract used during UI migration."""

    return descriptor()

# ---------------------------------------------------------------------------
# Serve the built React app (frontend/dist/, from `npm run build`) and give
# its client-side routes (e.g. /coach/dashboard) a working page on reload.
#
# This has to live here, after every router above, rather than in app.main:
# app.main is imported and re-registered onto by this module, so anything
# registered inside app.main that matched every path would run before these
# V2 routers exist and would shadow them. Registering it last — after every
# router this composed app has — means it only ever catches a request that
# genuinely matched nothing else.
# ---------------------------------------------------------------------------
_DIST = (Path(__file__).resolve().parent.parent / "frontend" / "dist").resolve()

if (_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="frontend-assets")

_DIST_INDEX = _DIST / "index.html"


@app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
async def spa_fallback(full_path: str):
    """Last-resort route: a real file under dist/ (favicon, manifest, the
    logo — everything Vite copied from frontend/public/) wins if it exists;
    otherwise this is a client-side route like /coach/dashboard, so hand back
    index.html and let React Router take it from there. An /api/... path
    that reaches this point matched no real endpoint — a plain 404 says so
    instead of masking it as a page."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found.")

    # full_path is attacker-controlled — resolve it and refuse anything that
    # walks (via "../") outside _DIST before ever touching the filesystem.
    candidate = (_DIST / full_path).resolve()
    if full_path and candidate.is_relative_to(_DIST) and candidate.is_file():
        return FileResponse(candidate)

    if not _DIST_INDEX.is_file():
        raise HTTPException(
            status_code=503,
            detail="Frontend is not built. Run `npm run build` in frontend/ (frontend/dist/ is missing).",
        )
    return _DIST_INDEX.read_text(encoding="utf-8")


__all__ = ["app"]
