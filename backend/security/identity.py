"""Replaceable identity boundary for the temporary single-owner deployment.

Phase 16 deliberately does not select a public authentication provider.  The
current provider maps the existing shared ``X-API-Key`` credential to one
owner and organization.  Routes depend on :func:`require_identity`, rather
than on API-key details, so a later provider can replace this adapter without
rewiring every route.
"""
from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Protocol

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings


_LOCAL_ENVIRONMENTS = frozenset({"dev", "development", "demo", "local", "test", "testing"})
_INVALID_CREDENTIAL_DETAIL = "Missing or invalid X-API-Key header."


class AuthConfigurationError(RuntimeError):
    """Raised when an exposed deployment would otherwise have no auth."""


@dataclass(frozen=True, slots=True)
class Identity:
    """Authenticated actor plus the ownership scope it is allowed to access."""

    subject: str
    owner_id: str
    organization_id: str
    authentication_method: str


class IdentityProvider(Protocol):
    """Provider contract that a future account system can implement."""

    def validate_configuration(self) -> None:
        """Raise when this provider cannot safely authenticate requests."""

    async def authenticate(self, credential: str | None) -> Identity:
        """Authenticate one request and return its ownership context."""


class APIKeyIdentityProvider:
    """Compatibility adapter for the existing shared ``API_KEY`` setting."""

    def __init__(self, settings: Settings):
        self._settings = settings

    @property
    def _configured_key(self) -> str | None:
        value = self._settings.API_KEY
        return value if value and value.strip() else None

    @property
    def _allows_anonymous_owner(self) -> bool:
        return self._settings.APP_ENV.strip().lower() in _LOCAL_ENVIRONMENTS

    def validate_configuration(self) -> None:
        if self._configured_key is None and not self._allows_anonymous_owner:
            raise AuthConfigurationError(
                "API_KEY must be set outside development, demo, local, or test environments."
            )

    async def authenticate(self, credential: str | None) -> Identity:
        self.validate_configuration()
        configured_key = self._configured_key
        if configured_key is not None:
            if credential is None or not hmac.compare_digest(credential, configured_key):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=_INVALID_CREDENTIAL_DETAIL,
                )
            method = "api_key"
        else:
            # An explicit local/demo environment may use the product without a
            # secret, but still receives the same owner scope as authenticated
            # deployments.  This keeps ownership plumbing active in dev.
            method = "local_development"

        return Identity(
            subject="single-owner",
            owner_id="single-owner",
            organization_id="single-owner",
            authentication_method=method,
        )


def get_identity_provider() -> IdentityProvider:
    """FastAPI dependency seam for replacing the temporary provider."""

    return APIKeyIdentityProvider(get_settings())


async def require_identity(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    provider: IdentityProvider = Depends(get_identity_provider),
) -> Identity:
    """Require an identity and return its owner/organization context."""

    return await provider.authenticate(x_api_key)


def validate_identity_configuration() -> None:
    """Fail application startup before a non-local API can be exposed."""

    get_identity_provider().validate_configuration()
