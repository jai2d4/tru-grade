"""Phase 21 — real accounts: signup, login, logout, and "who am I".

Layered on top of the existing shared X-API-Key gate (app/core/auth.py),
same as every other /api/v1 router — this doesn't replace that baseline,
it adds a second, per-user layer on top of it.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.config import get_settings
from app.core.db import get_db
from app.core.email import EmailNotConfiguredError, send_email
from app.core.passwords import hash_password, verify_password
from app.core.session import end_session, get_current_user, start_session
from app.models import orm
from app.models.schemas import (
    CurrentUser,
    ForgotPasswordRequest,
    ForgotPasswordResult,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    UserRole,
)

logger = logging.getLogger("tru.auth")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"], dependencies=[Depends(require_api_key)])

# Same local/demo/test allowlist app/core/email.py and app/core/session.py
# already use — a reset link is safe to hand back directly in these
# environments (there's no real inbox to check), never in production.
_LOCAL_ENVIRONMENTS = frozenset({"local", "development", "dev", "demo", "test", "testing"})
_RESET_TOKEN_TTL = timedelta(minutes=30)


async def _link_or_create_athlete(db: AsyncSession, full_name: str, position: str):
    """Resolves a fresh athlete signup to a roster row.

    Splits "First Last" into first/last name and looks for an existing,
    not-yet-claimed athletes row with the same name and position — the
    realistic case of a coach having already run a Truth Report on this
    player before they ever created an account. Links it only when exactly
    one such match exists; ambiguous or absent matches create a new roster
    row instead of guessing.
    """
    parts = full_name.strip().split(maxsplit=1)
    first_name = parts[0] if parts else full_name.strip()
    last_name = parts[1] if len(parts) > 1 else ""

    stmt = (
        select(orm.Athlete)
        .outerjoin(orm.User, orm.User.athlete_id == orm.Athlete.id)
        .where(
            func.lower(orm.Athlete.first_name) == first_name.lower(),
            func.lower(orm.Athlete.last_name) == last_name.lower(),
            orm.Athlete.position == position,
            orm.User.id.is_(None),
        )
    )
    result = await db.execute(stmt)
    matches = result.scalars().all()
    if len(matches) == 1:
        return matches[0].id

    athlete = orm.Athlete(first_name=first_name, last_name=last_name or first_name, position=position)
    db.add(athlete)
    await db.flush()  # assigns athlete.id
    return athlete.id


@router.post("/signup", response_model=CurrentUser, status_code=201)
async def signup(body: SignupRequest, response: Response, db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()
    existing = await db.execute(select(orm.User).where(orm.User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    athlete_id = None
    if body.role == UserRole.ATHLETE:
        if body.position is None:
            raise HTTPException(status_code=422, detail="Position is required to create an athlete account.")
        athlete_id = await _link_or_create_athlete(db, body.full_name, body.position.value)

    user = orm.User(
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        role=body.role.value,
        athlete_id=athlete_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await start_session(db, response, user.id)
    return user


@router.post("/login", response_model=CurrentUser)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()
    result = await db.execute(select(orm.User).where(orm.User.email == email))
    user = result.scalar_one_or_none()
    # Same generic message either way — never reveal whether the email exists.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    await start_session(db, response, user.id)
    return user


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    await end_session(db, request, response)
    return None


@router.get("/me", response_model=CurrentUser)
async def me(user: orm.User | None = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return user


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.post("/forgot-password", response_model=ForgotPasswordResult, status_code=202)
async def forgot_password(request: Request, body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Always the same response regardless of whether the email matches an
    account — never let this endpoint reveal account existence. If email
    delivery genuinely isn't configured (no SMTP, and not a local/demo/test
    environment), says so plainly instead of claiming to have sent
    something that never went anywhere."""
    settings = get_settings()
    is_local = settings.APP_ENV.strip().lower() in _LOCAL_ENVIRONMENTS
    if not settings.SMTP_HOST and not is_local:
        raise HTTPException(status_code=503, detail="Password reset isn't available yet — email delivery isn't configured.")

    generic_result = ForgotPasswordResult(detail="If an account with that email exists, a reset link has been sent.")

    email = body.email.strip().lower()
    result = await db.execute(select(orm.User).where(orm.User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        return generic_result

    # One active token per user — a fresh request invalidates any prior one.
    await db.execute(delete(orm.PasswordResetToken).where(orm.PasswordResetToken.user_id == user.id))
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + _RESET_TOKEN_TTL
    db.add(orm.PasswordResetToken(token_hash=_hash_token(token), user_id=user.id, expires_at=expires_at))
    await db.commit()

    reset_url = f"{str(request.base_url).rstrip('/')}/reset-password?token={token}"
    try:
        send_email(
            to=user.email,
            subject="Reset your TruGrade password",
            body=(
                f"Use this link within 30 minutes to reset your TruGrade password:\n\n{reset_url}\n\n"
                "If you didn't request this, you can safely ignore this email."
            ),
        )
    except EmailNotConfiguredError:
        logger.warning("password reset requested but email delivery is not configured")

    if is_local:
        generic_result.dev_reset_url = reset_url
    return generic_result


@router.post("/reset-password", response_model=CurrentUser)
async def reset_password(body: ResetPasswordRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Consumes the token outright (deleted whether it's used successfully
    or found expired) so it's never usable twice, sets the new password,
    and invalidates every existing session for the account — a stolen
    session shouldn't survive a reset — before logging the user straight
    into a fresh one."""
    token_hash = _hash_token(body.token)
    result = await db.execute(select(orm.PasswordResetToken).where(orm.PasswordResetToken.token_hash == token_hash))
    reset_row = result.scalar_one_or_none()

    if reset_row is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
    if reset_row.expires_at < datetime.now(timezone.utc):
        await db.delete(reset_row)
        await db.commit()
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    user = await db.get(orm.User, reset_row.user_id)
    if user is None:
        await db.delete(reset_row)
        await db.commit()
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    user.password_hash = hash_password(body.new_password)
    await db.execute(delete(orm.PasswordResetToken).where(orm.PasswordResetToken.user_id == user.id))
    await db.execute(delete(orm.UserSession).where(orm.UserSession.user_id == user.id))
    await db.commit()

    await start_session(db, response, user.id)
    return user
