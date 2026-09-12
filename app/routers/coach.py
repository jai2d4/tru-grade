"""Module 7 — Coach Dashboard aggregate view."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.models import orm
from app.models.schemas import BoardStage, CoachDashboard

router = APIRouter(prefix="/api/v1/coach", tags=["coach"], dependencies=[Depends(require_api_key)])


@router.get("/dashboard", response_model=CoachDashboard)
async def coach_dashboard(db: AsyncSession = Depends(get_db)):
    total_athletes = (await db.execute(select(func.count()).select_from(orm.Athlete))).scalar_one()
    total_evaluations = (await db.execute(select(func.count()).select_from(orm.Evaluation))).scalar_one()

    board_counts = {stage.value: 0 for stage in BoardStage}
    rows = await db.execute(
        select(orm.BoardEntry.stage, func.count()).group_by(orm.BoardEntry.stage)
    )
    for stage, count in rows.all():
        board_counts[stage] = count

    team_needs = (await db.execute(select(orm.TeamNeed).order_by(orm.TeamNeed.position))).scalars().all()

    recent = (
        await db.execute(select(orm.Evaluation).order_by(orm.Evaluation.created_at.desc()).limit(5))
    ).scalars().all()

    return CoachDashboard(
        total_athletes=total_athletes,
        total_evaluations=total_evaluations,
        board_counts=board_counts,
        team_needs=team_needs,
        recent_evaluations=recent,
    )
