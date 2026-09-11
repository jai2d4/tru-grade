"""Module 7 — Coach Recruitment Board and Team Needs."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.models import orm
from app.models.schemas import BoardEntryIn, BoardEntryOut, BoardStage, Position, TeamNeedIn, TeamNeedOut

router = APIRouter(prefix="/api/v1", tags=["coach"], dependencies=[Depends(require_api_key)])


def _board_entry_out(entry: orm.BoardEntry, athlete: orm.Athlete | None) -> BoardEntryOut:
    return BoardEntryOut(
        athlete_id=entry.athlete_id,
        stage=entry.stage,
        notes=entry.notes,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        first_name=athlete.first_name if athlete else None,
        last_name=athlete.last_name if athlete else None,
        position=athlete.position if athlete else None,
    )


@router.get("/board", response_model=list[BoardEntryOut])
async def list_board(stage: BoardStage | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(orm.BoardEntry, orm.Athlete).join(
        orm.Athlete, orm.Athlete.id == orm.BoardEntry.athlete_id,
    ).order_by(orm.BoardEntry.updated_at.desc())
    if stage:
        stmt = stmt.where(orm.BoardEntry.stage == stage.value)
    result = await db.execute(stmt)
    return [_board_entry_out(entry, athlete) for entry, athlete in result.all()]


@router.put("/board/{athlete_id}", response_model=BoardEntryOut)
async def upsert_board_entry(athlete_id: UUID, body: BoardEntryIn, db: AsyncSession = Depends(get_db)):
    """Add an athlete to the board, or move them to a different stage —
    same endpoint either way (UNIQUE(athlete_id) makes this an upsert)."""
    athlete = await db.get(orm.Athlete, athlete_id)
    if athlete is None:
        raise HTTPException(status_code=404, detail="Athlete not found.")

    stmt = select(orm.BoardEntry).where(orm.BoardEntry.athlete_id == athlete_id)
    entry = (await db.execute(stmt)).scalar_one_or_none()
    if entry is None:
        entry = orm.BoardEntry(athlete_id=athlete_id, stage=body.stage.value, notes=body.notes)
        db.add(entry)
    else:
        entry.stage = body.stage.value
        if body.notes is not None:
            entry.notes = body.notes
    await db.commit()
    await db.refresh(entry)
    return _board_entry_out(entry, athlete)


@router.delete("/board/{athlete_id}", status_code=204)
async def remove_board_entry(athlete_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(orm.BoardEntry).where(orm.BoardEntry.athlete_id == athlete_id)
    entry = (await db.execute(stmt)).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Athlete is not on the board.")
    await db.delete(entry)
    await db.commit()


@router.get("/team-needs", response_model=list[TeamNeedOut])
async def list_team_needs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(orm.TeamNeed).order_by(orm.TeamNeed.position))
    return result.scalars().all()


@router.put("/team-needs/{position}", response_model=TeamNeedOut)
async def set_team_need(position: Position, body: TeamNeedIn, db: AsyncSession = Depends(get_db)):
    stmt = select(orm.TeamNeed).where(orm.TeamNeed.position == position.value)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = orm.TeamNeed(position=position.value, priority=body.priority)
        db.add(row)
    else:
        row.priority = body.priority
    await db.commit()
    await db.refresh(row)
    return row
