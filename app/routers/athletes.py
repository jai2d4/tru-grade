"""Module 5 — athlete roster CRUD.
Module 7 — coach notes and fit scores nest under the same /athletes/{id}
resource, since they're all athlete-scoped."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.models import orm
from app.models.schemas import (
    Athlete, AthleteCreate, CoachFitScoresIn, CoachFitScoresOut, CoachNoteIn, CoachNoteOut, FilmLinkOut,
)

router = APIRouter(
    prefix="/api/v1/athletes", tags=["athletes"], dependencies=[Depends(require_api_key)],
)


@router.post("", response_model=Athlete, status_code=201)
async def create_athlete(athlete: AthleteCreate, db: AsyncSession = Depends(get_db)):
    row = orm.Athlete(**athlete.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("", response_model=list[Athlete])
async def list_athletes(
    position: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(orm.Athlete).order_by(orm.Athlete.created_at.desc()).limit(min(limit, 200)).offset(offset)
    if position:
        stmt = stmt.where(orm.Athlete.position == position)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{athlete_id}", response_model=Athlete)
async def get_athlete(athlete_id: UUID, db: AsyncSession = Depends(get_db)):
    row = await db.get(orm.Athlete, athlete_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Athlete not found.")
    return row


@router.post("/{athlete_id}/notes", response_model=CoachNoteOut, status_code=201)
async def add_coach_note(athlete_id: UUID, body: CoachNoteIn, db: AsyncSession = Depends(get_db)):
    if await db.get(orm.Athlete, athlete_id) is None:
        raise HTTPException(status_code=404, detail="Athlete not found.")
    row = orm.CoachNote(athlete_id=athlete_id, note=body.note, author=body.author)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/{athlete_id}/notes", response_model=list[CoachNoteOut])
async def list_coach_notes(athlete_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(orm.CoachNote).where(orm.CoachNote.athlete_id == athlete_id).order_by(orm.CoachNote.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put("/{athlete_id}/fit-scores", response_model=CoachFitScoresOut)
async def set_fit_scores(athlete_id: UUID, body: CoachFitScoresIn, db: AsyncSession = Depends(get_db)):
    if await db.get(orm.Athlete, athlete_id) is None:
        raise HTTPException(status_code=404, detail="Athlete not found.")
    row = await db.get(orm.CoachFitScore, athlete_id)
    if row is None:
        row = orm.CoachFitScore(athlete_id=athlete_id, **body.model_dump())
        db.add(row)
    else:
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/{athlete_id}/fit-scores", response_model=CoachFitScoresOut)
async def get_fit_scores(athlete_id: UUID, db: AsyncSession = Depends(get_db)):
    if await db.get(orm.Athlete, athlete_id) is None:
        raise HTTPException(status_code=404, detail="Athlete not found.")
    row = await db.get(orm.CoachFitScore, athlete_id)
    if row is None:
        # Nothing graded yet — return an all-null row rather than 404, since
        # "not yet scored" is a normal state for the Player Profile view.
        from datetime import datetime, timezone
        return CoachFitScoresOut(athlete_id=athlete_id, updated_at=datetime.now(timezone.utc))
    return row


@router.get("/{athlete_id}/film-links", response_model=list[FilmLinkOut])
async def list_film_links(athlete_id: UUID, db: AsyncSession = Depends(get_db)):
    """Every video where a coach has confirmed (or automatic identification
    has proposed) this athlete's track identity — see
    backend/api/players.py. Does not include grades: that persistence is a
    separate, not-yet-built increment (see docs on the unification PR)."""
    if await db.get(orm.Athlete, athlete_id) is None:
        raise HTTPException(status_code=404, detail="Athlete not found.")
    stmt = (
        select(orm.FilmTrackAssignment, orm.FilmUpload)
        .join(orm.FilmUpload, orm.FilmUpload.id == orm.FilmTrackAssignment.video_id)
        .where(orm.FilmTrackAssignment.athlete_id == athlete_id)
        .order_by(orm.FilmTrackAssignment.updated_at.desc())
    )
    result = await db.execute(stmt)
    return [
        FilmLinkOut(
            video_id=assignment.video_id, track_id=assignment.track_id, filename=video.filename,
            jersey_number=assignment.jersey_number, team=assignment.team, position=assignment.position,
            confirmed=assignment.confirmed, confidence=assignment.confidence, source=assignment.source,
            updated_at=assignment.updated_at,
        )
        for assignment, video in result.all()
    ]
