"""Module 5 — athlete roster CRUD.
Module 7 — coach notes and fit scores nest under the same /athletes/{id}
resource, since they're all athlete-scoped."""
from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.models import orm
from app.models.schemas import (
    Athlete, AthleteCreate, CoachFitScoresIn, CoachFitScoresOut, CoachNoteIn, CoachNoteOut, FilmGradeOut, FilmLinkOut,
    ShareLinkOut,
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


@router.get("/{athlete_id}/share-link", response_model=ShareLinkOut | None)
async def get_share_link(athlete_id: UUID, db: AsyncSession = Depends(get_db)):
    """The athlete's current public share link, if one has ever been
    issued — None (not 404) when none exists yet, since "no link issued"
    is a normal state for the Public Rating view, same pattern as
    get_fit_scores above."""
    if await db.get(orm.Athlete, athlete_id) is None:
        raise HTTPException(status_code=404, detail="Athlete not found.")
    row = await db.get(orm.AthleteShareLink, athlete_id)
    if row is None:
        return None
    return row


@router.post("/{athlete_id}/share-link", response_model=ShareLinkOut, status_code=201)
async def create_or_regenerate_share_link(athlete_id: UUID, db: AsyncSession = Depends(get_db)):
    """Issues a fresh, unguessable token for this athlete. athlete_id is
    the primary key, so this is always an upsert — regenerating silently
    invalidates whatever link was out there before, which is the intended
    revoke-by-replacing behavior."""
    if await db.get(orm.Athlete, athlete_id) is None:
        raise HTTPException(status_code=404, detail="Athlete not found.")
    token = secrets.token_urlsafe(24)
    row = await db.get(orm.AthleteShareLink, athlete_id)
    if row is None:
        row = orm.AthleteShareLink(athlete_id=athlete_id, token=token)
        db.add(row)
    else:
        row.token = token
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{athlete_id}/share-link", status_code=204)
async def revoke_share_link(athlete_id: UUID, db: AsyncSession = Depends(get_db)):
    """Fully revokes public access — deletes the row outright rather than
    just rotating the token, so GET goes back to reporting "none issued"."""
    row = await db.get(orm.AthleteShareLink, athlete_id)
    if row is not None:
        await db.delete(row)
        await db.commit()
    return None


@router.get("/{athlete_id}/grades", response_model=list[FilmGradeOut])
async def list_film_grades(athlete_id: UUID, db: AsyncSession = Depends(get_db)):
    """Every deterministic V2 grade run linked to this athlete — a
    best-effort mirror of backend/grading/service.py's GradeStore, written
    once a track already confirmed against this athlete gets a Truth
    Report run. See the film_grades schema comment for what this does and
    doesn't guarantee."""
    if await db.get(orm.Athlete, athlete_id) is None:
        raise HTTPException(status_code=404, detail="Athlete not found.")
    stmt = (
        select(orm.FilmGrade)
        .where(orm.FilmGrade.athlete_id == athlete_id)
        .order_by(orm.FilmGrade.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()
