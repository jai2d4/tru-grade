"""Public Rating — the anonymous, share-link-gated view of an athlete.

Deliberately NOT behind require_api_key: a coach hands this token out to
recruiters/family/whoever, and it has to work without any login. The
token itself (24 random bytes, base64url) is the only gate — see the
athlete_share_links schema comment in db/init_schema.sql for what this
does and doesn't expose, and app/routers/athletes.py for how a coach
issues/revokes one."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import orm
from app.models.schemas import PublicAthleteOut

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/athletes/{token}", response_model=PublicAthleteOut)
async def get_public_athlete(token: str, db: AsyncSession = Depends(get_db)):
    stmt = select(orm.AthleteShareLink).where(orm.AthleteShareLink.token == token)
    result = await db.execute(stmt)
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="This link is invalid or has been revoked.")

    athlete = await db.get(orm.Athlete, link.athlete_id)
    if athlete is None:
        # The athlete was deleted but the link row somehow outlived it
        # (shouldn't happen — ON DELETE CASCADE — but fail closed anyway).
        raise HTTPException(status_code=404, detail="This link is invalid or has been revoked.")

    # Real tier/rating only — never fabricate one for an unevaluated athlete.
    stmt = (
        select(orm.Evaluation)
        .where(orm.Evaluation.athlete_id == athlete.id)
        .order_by(orm.Evaluation.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    latest_evaluation = result.scalar_one_or_none()

    return PublicAthleteOut(
        first_name=athlete.first_name,
        last_name=athlete.last_name,
        position=athlete.position,
        school=athlete.school,
        grad_year=athlete.grad_year,
        projected_tier=latest_evaluation.projected_tier if latest_evaluation else None,
        is_game_changer=latest_evaluation.is_game_changer if latest_evaluation else False,
    )
