"""Phase 16 API contract, CORS, liveness, and readiness coverage."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.cors import resolve_cors_allow_origins
from backend.health import get_readiness_probes
from backend.main import app


def test_production_cors_is_same_origin_by_default_and_rejects_wildcard():
    assert resolve_cors_allow_origins("production", "") == []
    assert resolve_cors_allow_origins("production", "https://app.example, https://admin.example/") == [
        "https://app.example", "https://admin.example"
    ]
    try:
        resolve_cors_allow_origins("production", "*")
    except ValueError as exc:
        assert "cannot contain '*'" in str(exc)
    else:
        raise AssertionError("production wildcard CORS must be rejected")


def test_local_cors_retains_demo_compatibility():
    assert resolve_cors_allow_origins("development", "") == ["*"]


def test_contract_descriptor_is_versioned_and_preserves_existing_paths():
    with TestClient(app) as client:
        response = client.get("/api/contracts/v1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "1.0"
    assert payload["compatibility"] == "existing-unversioned-v2-paths"
    assert payload["official_grade_authority"] == "deterministic-trugrade-engine"
    assert payload["unknown_policy"] == "exclude-from-score"


def test_liveness_does_not_run_dependency_probes():
    async def must_not_run():
        raise AssertionError("liveness called a dependency")

    app.dependency_overrides[get_readiness_probes] = lambda: {"forbidden": must_not_run}
    try:
        with TestClient(app) as client:
            response = client.get("/api/health/live")
    finally:
        app.dependency_overrides.pop(get_readiness_probes, None)

    assert response.status_code == 200
    assert response.json()["status"] == "live"
    assert response.json()["checks"] is None


def test_status_reports_diagnostics_without_leaking_secrets(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "real-gemini-key")
    monkeypatch.setattr(settings, "API_KEY", "real-api-key")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc1234")
    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")

    async def available():
        return None

    app.dependency_overrides[get_readiness_probes] = lambda: {"database": available, "storage": available}
    try:
        with TestClient(app) as client:
            response = client.get("/api/health/status")
    finally:
        app.dependency_overrides.pop(get_readiness_probes, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["environment"] == settings.APP_ENV
    assert payload["git_commit"] == "abc1234"
    assert payload["git_branch"] == "main"
    assert payload["uptime_seconds"] >= 0
    assert payload["gemini_configured"] is True
    assert payload["api_key_configured"] is True
    # Never the secret values themselves, only that they're set.
    assert "real-gemini-key" not in response.text
    assert "real-api-key" not in response.text


def test_status_reports_503_and_none_git_fields_outside_render(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "API_KEY", None)
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.delenv("RENDER_GIT_BRANCH", raising=False)

    async def unavailable():
        raise ConnectionError("boom")

    app.dependency_overrides[get_readiness_probes] = lambda: {"database": unavailable, "storage": unavailable}
    try:
        with TestClient(app) as client:
            response = client.get("/api/health/status")
    finally:
        app.dependency_overrides.pop(get_readiness_probes, None)

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["git_commit"] is None
    assert payload["git_branch"] is None
    assert payload["api_key_configured"] is False


def test_readiness_reports_required_dependency_failure():
    async def available():
        return None

    async def unavailable():
        raise ConnectionError("private detail must not leak")

    app.dependency_overrides[get_readiness_probes] = lambda: {
        "storage": available,
        "database": unavailable,
    }
    try:
        with TestClient(app) as client:
            response = client.get("/api/health/ready")
    finally:
        app.dependency_overrides.pop(get_readiness_probes, None)

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["storage"]["status"] == "ok"
    assert payload["checks"]["database"] == {
        "status": "failed",
        "detail": "ConnectionError",
    }
