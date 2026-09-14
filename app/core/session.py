"""Session-cookie identity for Phase 21 accounts — layered on top of the
shared X-API-Key gate (app/core/auth.py), not a replacement for it.

An httpOnly cookie carries an opaque, unguessable token; the token maps to a
row in `user_sessions` which names the user and an expiry. Nothing about the
password or the user's identity is in the cookie itself, so it can't be
decoded or forged client-side, and logging out is just deleting the row.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.models import orm

SESSION_COOKIE = "trugrade_session"
SESSION_TTL = timedelta(days=30)

# Cookies with Secure require HTTPS; local/dev/test run over plain http.
_INSECURE_ENVIRONMENTS = frozenset({"local", "development", "dev", "demo", "test", "testing"})


async def start_session(db: AsyncSession, response: Response, user_id) -> None:
    """Issues a fresh session row and sets the cookie on `response`."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + SESSION_TTL
    db.add(orm.UserSession(token=token, user_id=user_id, expires_at=expires_at))
    await db.commit()

    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=settings.APP_ENV.strip().lower() not in _INSECURE_ENVIRONMENTS,
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
    )


async def end_session(db: AsyncSession, request: Request, response: Response) -> None:
    """Deletes the session row named by the cookie, if any, and clears it."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await db.execute(delete(orm.UserSession).where(orm.UserSession.token == token))
        await db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> orm.User | None:
    """Resolves the signed-in user from the session cookie, or None if
    there isn't one — missing, unknown, and expired are all just "not
    signed in", never an error. An expired session is deleted on sight
    instead of waiting on a cleanup job."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None

    result = await db.execute(select(orm.UserSession).where(orm.UserSession.token == token))
    session_row = result.scalar_one_or_none()
    if session_row is None:
        return None

    if session_row.expires_at < datetime.now(timezone.utc):
        await db.execute(delete(orm.UserSession).where(orm.UserSession.token == token))
        await db.commit()
        return None

    return await db.get(orm.User, session_row.user_id)
