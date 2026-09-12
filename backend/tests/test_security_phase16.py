"""HTTP integration coverage for the temporary Phase 16 identity boundary."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.core.config import get_settings
from backend.main import app
from backend.security import (
    Identity,
    get_identity_provider,
    require_identity,
    validate_identity_configuration,
)


def _configure(monkeypatch, *, environment: str, api_key: str | None) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", environment)
    monkeypatch.setattr(settings, "API_KEY", api_key)


# One representative operation from each of the five V2 routers
# (backend/api/videos.py, analysis.py, players.py, football.py, reports.py —
# players.py and videos.py share the /api/videos prefix). Behavioral, not an
# introspection of FastAPI's internal route representation: newer FastAPI/
# Starlette releases wrap an included router lazily (an _IncludedRouter, not
# a flat list of APIRoute) rather than eagerly flattening app.routes the way
# an earlier version of this test relied on, so a route-object inspection is
# not a stable way to assert this — hitting the real endpoint is.
V2_OPERATIONS = [
    ("GET", "/api/videos"),
    ("GET", "/api/videos/missing/tracks"),
    ("GET", "/api/analysis/status/missing"),
    ("GET", "/api/videos/missing/plays"),
    ("GET", "/api/players/missing/grades"),
]


@pytest.mark.parametrize("method,path", V2_OPERATIONS)
def test_every_v2_api_operation_requires_the_identity_dependency(monkeypatch, method, path):
    _configure(monkeypatch, environment="production", api_key="phase16-secret")

    with TestClient(app) as client:
        response = client.request(method, path)

    assert response.status_code == 401, f"{method} {path} did not require an identity"


def test_v2_rejects_missing_and_wrong_api_keys(monkeypatch):
    _configure(monkeypatch, environment="development", api_key="phase16-secret")

    with TestClient(app) as client:
        missing = client.get("/api/videos")
        wrong = client.get("/api/videos", headers={"X-API-Key": "wrong"})
        accepted = client.get("/api/videos", headers={"X-API-Key": "phase16-secret"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.json() == wrong.json() == {"detail": "Missing or invalid X-API-Key header."}
    assert accepted.status_code == 200


@pytest.mark.parametrize("environment", ["development", "demo", "local", "test"])
def test_explicit_local_environments_remain_usable_without_a_key(monkeypatch, environment):
    _configure(monkeypatch, environment=environment, api_key=None)

    with TestClient(app) as client:
        response = client.get("/api/videos")

    assert response.status_code == 200


@pytest.mark.parametrize("api_key", [None, "", "   "])
def test_production_refuses_to_start_without_a_usable_api_key(monkeypatch, api_key):
    _configure(monkeypatch, environment="production", api_key=api_key)

    with pytest.raises(RuntimeError, match="API_KEY must be set"):
        validate_identity_configuration()


def test_identity_provider_can_be_replaced_without_rewiring_routes(monkeypatch):
    _configure(monkeypatch, environment="development", api_key="unused")
    replacement = Identity(
        subject="future-user",
        owner_id="owner-2",
        organization_id="organization-2",
        authentication_method="test-provider",
    )

    class ReplacementProvider:
        def validate_configuration(self) -> None:
            pass

        async def authenticate(self, credential: str | None) -> Identity:
            return replacement

    app.dependency_overrides[get_identity_provider] = ReplacementProvider
    try:
        with TestClient(app) as client:
            response = client.get("/api/videos")
    finally:
        app.dependency_overrides.pop(get_identity_provider, None)

    assert response.status_code == 200
