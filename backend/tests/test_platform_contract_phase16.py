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
