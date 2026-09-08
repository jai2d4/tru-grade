"""HTTP integration coverage for the temporary Phase 16 identity boundary."""
from __future__ import annotations

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
import pytest

from app.core.config import get_settings
from backend.main import app
from backend.security import Identity, get_identity_provider, require_identity


def _configure(monkeypatch, *, environment: str, api_key: str | None) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", environment)
    monkeypatch.setattr(settings, "API_KEY", api_key)


def test_every_v2_api_operation_requires_the_identity_dependency():
    v2_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.endpoint.__module__.startswith("backend.api.")
    ]

    assert v2_routes
    for route in v2_routes:
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        assert require_identity in dependency_calls, f"{route.path} has no identity boundary"


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
        with TestClient(app):
            pass


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
