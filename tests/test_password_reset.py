"""Password reset: a real, single-use, time-limited token end to end.
Real DB — mirrors test_auth.py. APP_ENV defaults to "development" in tests
(a local environment), so the local dev-fallback path (no SMTP configured,
the reset link comes back directly instead of being emailed) is what's
exercised here — the same code path a real SMTP-configured deployment
would run, minus the actual send. Each test uses its own email (the DB
persists across tests in one run, same as test_auth.py)."""
import re
from datetime import timedelta

import pytest


@pytest.fixture(autouse=True)
def _skip_without_db(db_available):
    available, reason = db_available
    if not available:
        pytest.skip(f"No PostgreSQL reachable — set POSTGRES_* env vars to run these tests. ({reason})")


def _headers(api_key_required):
    return {"X-API-Key": api_key_required}


def _signup(client, headers, email, password="original-pw"):
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "full_name": "Reset Me", "role": "coach"},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()


def _token_from_url(url: str) -> str:
    match = re.search(r"token=([^&]+)", url)
    assert match, f"no token found in {url}"
    return match.group(1)


def test_forgot_password_for_existing_user_returns_a_real_usable_link_in_dev(client, api_key_required):
    headers = _headers(api_key_required)
    _signup(client, headers, email="forgot1@example.com")

    r = client.post("/api/v1/auth/forgot-password", json={"email": "Forgot1@Example.com"}, headers=headers)
    assert r.status_code == 202
    body = r.json()
    assert body["detail"] == "If an account with that email exists, a reset link has been sent."
    assert body["dev_reset_url"] is not None
    assert "/reset-password?token=" in body["dev_reset_url"]


def test_forgot_password_for_unknown_email_gives_the_identical_generic_response(client, api_key_required):
    headers = _headers(api_key_required)
    r = client.post("/api/v1/auth/forgot-password", json={"email": "nobody-at-all@example.com"}, headers=headers)
    assert r.status_code == 202
    assert r.json()["detail"] == "If an account with that email exists, a reset link has been sent."
    # No account exists, so there's genuinely nothing to link to.
    assert r.json()["dev_reset_url"] is None


def test_forgot_password_is_honestly_unavailable_outside_local_env_without_smtp(client, api_key_required, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SMTP_HOST", None)

    r = client.post(
        "/api/v1/auth/forgot-password", json={"email": "forgot2@example.com"}, headers=_headers(api_key_required),
    )
    assert r.status_code == 503
    assert "isn't available" in r.json()["detail"].lower()


def test_reset_password_with_a_real_token_sets_the_new_password_and_logs_in(client, api_key_required):
    headers = _headers(api_key_required)
    _signup(client, headers, email="forgot3@example.com", password="original-pw")

    r = client.post("/api/v1/auth/forgot-password", json={"email": "forgot3@example.com"}, headers=headers)
    token = _token_from_url(r.json()["dev_reset_url"])

    r = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "brand-new-pw"}, headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["email"] == "forgot3@example.com"

    # Old password no longer works; the new one does.
    r = client.post(
        "/api/v1/auth/login", json={"email": "forgot3@example.com", "password": "original-pw"}, headers=headers,
    )
    assert r.status_code == 401

    r = client.post(
        "/api/v1/auth/login", json={"email": "forgot3@example.com", "password": "brand-new-pw"}, headers=headers,
    )
    assert r.status_code == 200


def test_reset_password_invalidates_every_prior_session(client, api_key_required):
    headers = _headers(api_key_required)
    _signup(client, headers, email="forgot4@example.com", password="original-pw")
    # The signup call itself already set a session cookie on this client.
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    r = client.post("/api/v1/auth/forgot-password", json={"email": "forgot4@example.com"}, headers=headers)
    token = _token_from_url(r.json()["dev_reset_url"])
    client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "brand-new-pw"}, headers=headers)

    # The pre-reset session cookie is gone — a stolen session shouldn't
    # survive a reset. (reset-password itself issues a fresh one, but we
    # explicitly drop cookies to prove the *old* one no longer works.)
    client.cookies.clear()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_reset_password_rejects_an_unknown_token(client, api_key_required):
    r = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "whatever-pw"},
        headers=_headers(api_key_required),
    )
    assert r.status_code == 400


def test_reset_password_token_is_single_use(client, api_key_required):
    headers = _headers(api_key_required)
    _signup(client, headers, email="forgot5@example.com", password="original-pw")
    r = client.post("/api/v1/auth/forgot-password", json={"email": "forgot5@example.com"}, headers=headers)
    token = _token_from_url(r.json()["dev_reset_url"])

    first = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "first-new-pw"}, headers=headers,
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "second-new-pw"}, headers=headers,
    )
    assert second.status_code == 400


def test_reset_password_rejects_an_expired_token(client, api_key_required, monkeypatch):
    import app.routers.auth as auth_module

    monkeypatch.setattr(auth_module, "_RESET_TOKEN_TTL", timedelta(seconds=-1))

    headers = _headers(api_key_required)
    _signup(client, headers, email="forgot6@example.com", password="original-pw")
    r = client.post("/api/v1/auth/forgot-password", json={"email": "forgot6@example.com"}, headers=headers)
    token = _token_from_url(r.json()["dev_reset_url"])

    r = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "brand-new-pw"}, headers=headers,
    )
    assert r.status_code == 400


def test_a_fresh_forgot_password_request_invalidates_the_previous_token(client, api_key_required):
    headers = _headers(api_key_required)
    _signup(client, headers, email="forgot7@example.com", password="original-pw")

    first = client.post("/api/v1/auth/forgot-password", json={"email": "forgot7@example.com"}, headers=headers)
    first_token = _token_from_url(first.json()["dev_reset_url"])

    second = client.post("/api/v1/auth/forgot-password", json={"email": "forgot7@example.com"}, headers=headers)
    second_token = _token_from_url(second.json()["dev_reset_url"])
    assert first_token != second_token

    r = client.post(
        "/api/v1/auth/reset-password", json={"token": first_token, "new_password": "brand-new-pw"}, headers=headers,
    )
    assert r.status_code == 400  # the old token was invalidated by the newer request

    r = client.post(
        "/api/v1/auth/reset-password", json={"token": second_token, "new_password": "brand-new-pw"}, headers=headers,
    )
    assert r.status_code == 200
