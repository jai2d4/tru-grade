"""Pluggable outbound email — currently just password reset.

Until SMTP_HOST is configured (see app/core/config.py), this never claims
to have sent anything real. In a local/demo/test APP_ENV it logs the
message as structured JSON (see app/core/logging_config.py) so the whole
reset flow is testable without any email infrastructure — the reset link
is right there in the logs. Outside those environments, with no SMTP
configured, it raises: the caller (app/routers/auth.py) turns that into an
honest "this isn't available yet" response instead of a fabricated
"check your email."
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger("tru.email")

_LOCAL_ENVIRONMENTS = frozenset({"local", "development", "dev", "demo", "test", "testing"})


class EmailNotConfiguredError(RuntimeError):
    """No SMTP is configured and this isn't a local/demo/test environment
    where logging the message instead is an acceptable stand-in."""


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.SMTP_HOST) or settings.APP_ENV.strip().lower() in _LOCAL_ENVIRONMENTS


def send_email(*, to: str, subject: str, body: str) -> None:
    settings = get_settings()

    if not settings.SMTP_HOST:
        if settings.APP_ENV.strip().lower() in _LOCAL_ENVIRONMENTS:
            logger.info(
                "email not actually sent (no SMTP_HOST configured) — local/dev fallback",
                extra={"to": to, "subject": subject, "body": body},
            )
            return
        raise EmailNotConfiguredError("Email delivery is not configured (SMTP_HOST is unset).")

    message = EmailMessage()
    message["From"] = settings.SMTP_FROM or settings.SMTP_USER or "no-reply@trugrade.app"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(message)
