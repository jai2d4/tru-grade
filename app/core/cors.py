"""Environment-aware cross-origin policy for the TruGrade API."""
from __future__ import annotations


_LOCAL_ENVIRONMENTS = frozenset({"dev", "development", "demo", "local", "test", "testing"})


def resolve_cors_allow_origins(app_env: str, configured_origins: str) -> list[str]:
    """Return a normalized allowlist and reject wildcard production CORS."""

    environment = app_env.strip().lower()
    origins = [value.strip().rstrip("/") for value in configured_origins.split(",") if value.strip()]
    if environment not in _LOCAL_ENVIRONMENTS and "*" in origins:
        raise ValueError("CORS_ALLOW_ORIGINS cannot contain '*' outside a local environment.")
    if origins:
        return list(dict.fromkeys(origins))
    return ["*"] if environment in _LOCAL_ENVIRONMENTS else []
