"""Phase 5 track identity and field-calibration endpoints.

Track identity is unified with the athlete roster: film_track_assignments
(Postgres) is the only store for who a track is, replacing the local JSON
file this router used to keep. Track geometry (frames/positions) stays
local — see the schema comment in db/init_schema.sql for why. Automatic
identification proposes a jersey number and team-color match; it never
resolves a real athlete_id by itself, only a coach confirming a track
through /assign does that.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import best_effort_session, get_db
from app.models import orm
from backend.api.videos import storage_root, video_store
from backend.football.movement import movement_metrics
from backend.vision.field_calibration import (
    FieldCalibration, automatic_calibration_unavailable, automatic_field_calibration,
)
from backend.vision.jersey_identifier import TrackIdentity, confirm_identity
from backend.vision.automatic_identity import EasyOCRJerseyReader, identify_player


router = APIRouter(prefix="/api/videos", tags=["players"])


class AssignmentRequest(BaseModel):
    player_id: str | None = None
    # The real roster link. Optional: not every tracked player is a known
    # prospect yet (e.g. scouting an opponent), so a track can stay
    # identified only by jersey_number/player_id with no athlete_id.
    athlete_id: str | None = None
    jersey_number: str = Field(pattern=r"^[0-9]{1,2}$")
    team: str | None = None
    position: str | None = None
    reason: str = Field(min_length=2)


class AutomaticIdentityRequest(BaseModel):
    jersey_number: str = Field(pattern=r"^[0-9]{1,2}$")
    school_colors: str = Field(min_length=2)
    player_id: str | None = None
    position: str | None = None


def _require_video(video_id: str) -> dict:
    video = video_store.get(video_id)
    if not video:
        raise HTTPException(404, "Video not found.")
    return video


def _track_path(video_id: str) -> Path:
    return storage_root / "vision" / video_id / "tracks.json"


def _identity_path(video_id: str) -> Path:
    directory = storage_root / "identity"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{video_id}.json"


def _assignment_dict(row: orm.FilmTrackAssignment) -> dict:
    return {
        "track_id": row.track_id,
        "player_id": row.player_id,
        "athlete_id": str(row.athlete_id) if row.athlete_id else None,
        "jersey_number": row.jersey_number,
        "team": row.team,
        "position": row.position,
        "candidates": row.candidates or [],
        "confidence": row.confidence,
        "confirmed": row.confirmed,
        "history": row.history or [],
    }


async def _get_assignments(db: AsyncSession, video_id: UUID) -> dict[str, dict]:
    stmt = select(orm.FilmTrackAssignment).where(orm.FilmTrackAssignment.video_id == video_id)
    rows = (await db.execute(stmt)).scalars().all()
    return {str(row.track_id): _assignment_dict(row) for row in rows}


async def _persist_automatic_assignment(video_id: str, track_id: int, request: AutomaticIdentityRequest,
                                        confidence: float) -> None:
    """Best-effort: automatic identification is a background convenience, not
    a user action, so a DB hiccup here logs and moves on rather than losing
    the whole job. A coach confirming the track through /assign is the
    action that must not silently degrade."""
    async with best_effort_session() as session:
        if session is None:
            return
        existing = (await session.execute(
            select(orm.FilmTrackAssignment).where(
                orm.FilmTrackAssignment.video_id == UUID(video_id),
                orm.FilmTrackAssignment.track_id == track_id,
            )
        )).scalar_one_or_none()
        if existing is None:
            existing = orm.FilmTrackAssignment(video_id=UUID(video_id), track_id=track_id)
            session.add(existing)
        existing.player_id = request.player_id
        existing.jersey_number = request.jersey_number
        existing.team = request.school_colors
        existing.position = request.position
        existing.confidence = confidence
        existing.confirmed = False
        existing.source = "automatic_multi_frame"
        existing.history = (existing.history or []) + [
            {"source": "automatic", "reason": "Multi-frame OCR and team-color match."}
        ]
        await session.commit()


def _run_automatic_identity(video_id: str, request: AutomaticIdentityRequest) -> None:
    """Runs in BackgroundTasks' threadpool (this function is sync on purpose —
    cv2 decode and OCR are CPU-bound; making this async would run them
    straight on the event loop and stall every other request meanwhile).
    asyncio.run() for the small DB-persist step is safe here: this thread
    has no event loop of its own to conflict with."""
    import cv2
    path = _identity_path(video_id)
    try:
        tracks = json.loads(_track_path(video_id).read_text(encoding="utf-8"))
        manifest_path = storage_root / "frames" / video_id / "frames.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        frames = {}
        wanted = {point["frame"] for track in tracks for point in track.get("positions", [])}
        for item in manifest:
            if item["frame_number"] in wanted:
                image = cv2.imread(item["file_path"])
                if image is not None:
                    frames[item["frame_number"]] = image
        result = identify_player(
            request.jersey_number, request.school_colors, tracks, frames, EasyOCRJerseyReader(),
            min_reads=int(os.getenv("JERSEY_ID_MIN_READS", "2")),
            threshold=float(os.getenv("JERSEY_ID_CONFIDENCE", ".62")),
            margin=float(os.getenv("JERSEY_ID_MARGIN", ".12")),
        )
        result.update(status_detail="Automatic multi-frame identification completed.",
                      player_id=request.player_id, position=request.position)
        if result["selected_track_id"] is not None:
            asyncio.run(_persist_automatic_assignment(
                video_id, result["selected_track_id"], request, result["confidence"],
            ))
    except Exception as exc:
        result = {"status": "failed", "status_detail": "Automatic identification failed.",
                  "error": str(exc), "selected_track_id": None, "confidence": 0}
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")


@router.get("/{video_id}/tracks")
async def get_tracks(video_id: str, db: AsyncSession = Depends(get_db)):
    _require_video(video_id)
    path = _track_path(video_id)
    tracks = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    assignments = await _get_assignments(db, UUID(video_id))
    return {"video_id": video_id, "tracks": tracks, "assignments": assignments}


@router.get("/{video_id}/detections")
async def get_detections(video_id: str):
    _require_video(video_id)
    path = storage_root / "vision" / video_id / "detections.json"
    return {"video_id": video_id, "detections": json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []}


@router.get("/{video_id}/biomechanics")
async def get_biomechanics(video_id: str):
    _require_video(video_id)
    path = storage_root / "vision" / video_id / "biomechanics.json"
    if not path.is_file():
        raise HTTPException(404, "Pose, ball, and contact evidence is not available.")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/{video_id}/identify", status_code=202)
async def start_automatic_identity(video_id: str, request: AutomaticIdentityRequest,
                                   background_tasks: BackgroundTasks):
    _require_video(video_id)
    if not _track_path(video_id).is_file():
        raise HTTPException(409, "Detection and tracking must complete before identification.")
    payload = {"status": "processing", "status_detail": "Reading jersey numbers across tracked frames.",
               "selected_track_id": None, "confidence": 0}
    _identity_path(video_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    background_tasks.add_task(_run_automatic_identity, video_id, request)
    return payload


@router.get("/{video_id}/identify")
async def automatic_identity_status(video_id: str):
    _require_video(video_id)
    path = _identity_path(video_id)
    if not path.is_file():
        raise HTTPException(404, "Automatic identification has not started.")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/{video_id}/tracks/{track_id}/assign")
async def assign_track(video_id: str, track_id: int, request: AssignmentRequest,
                       db: AsyncSession = Depends(get_db)):
    _require_video(video_id)
    tracks_path = _track_path(video_id)
    tracks = json.loads(tracks_path.read_text(encoding="utf-8")) if tracks_path.is_file() else []
    if not any(item.get("track_id") == track_id for item in tracks):
        raise HTTPException(404, "Track not found.")

    athlete_uuid: UUID | None = None
    if request.athlete_id:
        try:
            athlete_uuid = UUID(request.athlete_id)
        except ValueError:
            raise HTTPException(422, "athlete_id must be a UUID.")
        if await db.get(orm.Athlete, athlete_uuid) is None:
            raise HTTPException(404, "That athlete is not on the roster.")

    video_uuid = UUID(video_id)
    existing = (await db.execute(
        select(orm.FilmTrackAssignment).where(
            orm.FilmTrackAssignment.video_id == video_uuid,
            orm.FilmTrackAssignment.track_id == track_id,
        )
    )).scalar_one_or_none()

    original = TrackIdentity(
        track_id=track_id,
        player_id=existing.player_id if existing else None,
        athlete_id=str(existing.athlete_id) if existing and existing.athlete_id else None,
        jersey_number=existing.jersey_number if existing else None,
        team=existing.team if existing else None,
        position=existing.position if existing else None,
        candidates=existing.candidates if existing else [],
        confidence=existing.confidence if existing else 0,
        confirmed=existing.confirmed if existing else False,
    )
    identity, audit = confirm_identity(original, **request.model_dump())

    if existing is None:
        existing = orm.FilmTrackAssignment(video_id=video_uuid, track_id=track_id)
        db.add(existing)
    existing.player_id = identity.player_id
    existing.athlete_id = athlete_uuid
    existing.jersey_number = identity.jersey_number
    existing.team = identity.team
    existing.position = identity.position
    existing.confidence = identity.confidence
    existing.confirmed = identity.confirmed
    existing.source = "manual"
    existing.history = (existing.history or []) + [audit]
    await db.commit()
    await db.refresh(existing)
    return _assignment_dict(existing)


@router.get("/{video_id}/calibration")
async def get_calibration(video_id: str):
    _require_video(video_id)
    path = storage_root / "calibrations" / f"{video_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else automatic_calibration_unavailable()


@router.post("/{video_id}/calibration")
async def save_calibration(video_id: str, calibration: FieldCalibration):
    _require_video(video_id)
    directory = storage_root / "calibrations"
    directory.mkdir(parents=True, exist_ok=True)
    payload = calibration.model_dump()
    (directory / f"{video_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


@router.post("/{video_id}/calibration/auto")
async def create_automatic_calibration(video_id: str):
    import cv2
    _require_video(video_id)
    manifest_path = storage_root / "frames" / video_id / "frames.json"
    if not manifest_path.is_file():
        raise HTTPException(409, "Frame extraction must complete before calibration.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest:
        raise HTTPException(409, "No extracted frames are available.")
    sample = manifest[len(manifest) // 2]
    frame = cv2.imread(sample["file_path"])
    if frame is None:
        raise HTTPException(409, "The calibration frame is unavailable.")
    result = automatic_field_calibration(frame)
    if isinstance(result, dict):
        return result
    directory = storage_root / "calibrations"
    directory.mkdir(parents=True, exist_ok=True)
    payload = {**result.model_dump(), "status": "calibrated", "sample_frame": sample["frame_number"],
               "measurement_quality": "estimated",
               "measurement_note": "Confirm known field points to verify absolute yardage."}
    (directory / f"{video_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tracks_path = _track_path(video_id)
    tracks = json.loads(tracks_path.read_text(encoding="utf-8")) if tracks_path.is_file() else []
    for track in tracks:
        track["movement"] = movement_metrics(track.get("positions", []), result)
    tracks_path.write_text(json.dumps(tracks, indent=2), encoding="utf-8")
    payload["tracks_calibrated"] = len(tracks)
    return payload
