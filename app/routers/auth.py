"""Phase 21 — real accounts: signup, login, logout, and "who am I".

Layered on top of the existing shared X-API-Key gate (app/core/auth.py),
same as every other /api/v1 router — this doesn't replace that baseline,
it adds a second, per-user layer on top of it.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.core.passwords import hash_password, verify_password
from app.core.session import end_session, get_current_user, start_session
from app.models import orm
from app.models.schemas import CurrentUser, LoginRequest, SignupRequest, UserRole

router = APIRouter(prefix="/api/v1/auth", tags=["auth"], dependencies=[Depends(require_api_key)])


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
