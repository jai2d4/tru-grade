"""Phase 8 deterministic player-grade API."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from backend.ai.football_reasoner import FootballReasoningResult
from backend.ai.football_reasoner import FootballReasoner
from backend.ai.provider import create_provider
from backend.api.videos import storage_root
from backend.football.evidence import EvidenceStore
from backend.football.observations import FootballObservation
from backend.football.truth_report import build_play_observations, five_trait_summary
from backend.grading.service import GradeStore, calculate_official_grade
from backend.grading.rules_loader import load_position_rules


router = APIRouter(prefix="/api/players", tags=["reports"])
grade_store = GradeStore(storage_root / "grades")
report_jobs_dir = storage_root / "report_jobs"
report_jobs_dir.mkdir(parents=True, exist_ok=True)


class GradeInput(BaseModel):
    observation: FootballObservation
    reasoning: FootballReasoningResult


class CalculateGradeRequest(BaseModel):
    game_id: str = Field(min_length=1)
    position: str = Field(min_length=1)
    items: list[GradeInput]


class TruthReportRequest(BaseModel):
    video_id: str = Field(min_length=1)
    track_id: int = Field(ge=1)
    position: str = Field(min_length=1)


def _report_job_path(player_id: str, video_id: str):
    # Player IDs originate in the UI and must never become filesystem paths.
    job_id = hashlib.sha256(f"{player_id}\0{video_id}".encode("utf-8")).hexdigest()
    return report_jobs_dir / f"{job_id}.json"


async def _build_truth_report(player_id: str, request: TruthReportRequest):
    path = _report_job_path(player_id, request.video_id)
    try:
        vision_dir = storage_root / "vision" / request.video_id
        tracks = json.loads((vision_dir / "tracks.json").read_text(encoding="utf-8"))
        track = next((item for item in tracks if item["track_id"] == request.track_id), None)
        if track is None:
            raise ValueError("Selected player track was not found.")
        plays = json.loads((storage_root / "football" / request.video_id / "plays.json").read_text(encoding="utf-8"))
        bio_path = vision_dir / "biomechanics.json"
        biomechanics = json.loads(bio_path.read_text(encoding="utf-8")) if bio_path.is_file() else None
        observations = build_play_observations(
            request.video_id, player_id, request.position, track, plays, biomechanics
        )
        allowed_traits = list(load_position_rules(request.position).traits)
        reasoner = FootballReasoner(create_provider())
        pairs = []
        evidence_store = EvidenceStore(storage_root / "evidence")
        for index, observation in enumerate(observations, 1):
            path.write_text(json.dumps({"status": "reasoning", "progress": round(index * 90 / max(len(observations), 1)),
                                        "message": f"Reasoning over play {index} of {len(observations)}."}), encoding="utf-8")
            reasoning = await reasoner.reason(observation, allowed_traits)
            pairs.append((observation, reasoning))
            for evidence in observation.evidence:
                evidence_store.save(evidence)
        grade, events = calculate_official_grade(request.position, pairs)
        traits = five_trait_summary(grade)
        report = grade_store.save(player_id, request.video_id, grade, events, traits)
        result = {"status": "completed", "progress": 100, "message": "Truth Report completed.",
                  "report": report, "updated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        result = {"status": "failed", "progress": 0, "message": "Truth Report failed.",
                  "error": str(exc), "updated_at": datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")


@router.post("/{player_id}/grades", status_code=201)
async def calculate_grade(player_id: str, request: CalculateGradeRequest):
    if any(item.observation.player_id != player_id for item in request.items):
        raise HTTPException(422, "Every observation must belong to the requested player.")
    try:
        grade, events = calculate_official_grade(
            request.position, [(item.observation, item.reasoning) for item in request.items]
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return grade_store.save(player_id, request.game_id, grade, events)


@router.get("/{player_id}/grades")
async def get_player_grades(player_id: str):
    return {"player_id": player_id, "grades": grade_store.get(player_id)}


@router.post("/{player_id}/truth-report", status_code=202)
async def start_truth_report(player_id: str, request: TruthReportRequest, background_tasks: BackgroundTasks):
    path = _report_job_path(player_id, request.video_id)
    payload = {"status": "queued", "progress": 0, "message": "Truth Report queued."}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    background_tasks.add_task(_build_truth_report, player_id, request)
    return payload


@router.get("/{player_id}/truth-report/{video_id}")
async def truth_report_status(player_id: str, video_id: str):
    path = _report_job_path(player_id, video_id)
    if not path.is_file():
        raise HTTPException(404, "Truth Report job not found.")
    return json.loads(path.read_text(encoding="utf-8"))
