"""Phase 5 track identity and field-calibration endpoints."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

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


def _run_automatic_identity(video_id: str, request: AutomaticIdentityRequest) -> None:
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
            assignment_dir = storage_root / "assignments"
            assignment_dir.mkdir(parents=True, exist_ok=True)
            assignment_path = assignment_dir / f"{video_id}.json"
            assignments = json.loads(assignment_path.read_text(encoding="utf-8")) if assignment_path.is_file() else {}
            key = str(result["selected_track_id"])
            assignments[key] = {
                "track_id": result["selected_track_id"], "player_id": request.player_id,
                "jersey_number": request.jersey_number, "team": request.school_colors,
                "position": request.position, "candidates": [], "confidence": result["confidence"],
                "confirmed": False, "source": "automatic_multi_frame",
                "history": [{"source": "automatic", "reason": "Multi-frame OCR and team-color match."}],
            }
            assignment_path.write_text(json.dumps(assignments, indent=2), encoding="utf-8")
    except Exception as exc:
        result = {"status": "failed", "status_detail": "Automatic identification failed.",
                  "error": str(exc), "selected_track_id": None, "confidence": 0}
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")


@router.get("/{video_id}/tracks")
async def get_tracks(video_id: str):
    _require_video(video_id)
    path = _track_path(video_id)
    tracks = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    assignment_path = storage_root / "assignments" / f"{video_id}.json"
    assignments = json.loads(assignment_path.read_text(encoding="utf-8")) if assignment_path.is_file() else {}
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
async def assign_track(video_id: str, track_id: int, request: AssignmentRequest):
    _require_video(video_id)
    tracks_path = _track_path(video_id)
    tracks = json.loads(tracks_path.read_text(encoding="utf-8")) if tracks_path.is_file() else []
    if not any(item.get("track_id") == track_id for item in tracks):
        raise HTTPException(404, "Track not found.")
    directory = storage_root / "assignments"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{video_id}.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    existing = data.get(str(track_id), {})
    original = TrackIdentity(track_id=track_id, player_id=existing.get("player_id"),
                             jersey_number=existing.get("jersey_number"), team=existing.get("team"),
                             position=existing.get("position"), candidates=existing.get("candidates", []),
                             confidence=existing.get("confidence", 0), confirmed=existing.get("confirmed", False))
    identity, audit = confirm_identity(original, **request.model_dump())
    history = existing.get("history", []) + [audit]
    data[str(track_id)] = {**identity.model_dump(), "history": history}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data[str(track_id)]


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
