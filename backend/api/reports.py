"""Phase 8 deterministic player-grade API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.ai.football_reasoner import FootballReasoningResult
from backend.api.videos import storage_root
from backend.football.observations import FootballObservation
from backend.grading.service import GradeStore, calculate_official_grade


router = APIRouter(prefix="/api/players", tags=["reports"])
grade_store = GradeStore(storage_root / "grades")


class GradeInput(BaseModel):
    observation: FootballObservation
    reasoning: FootballReasoningResult


class CalculateGradeRequest(BaseModel):
    game_id: str = Field(min_length=1)
    position: str = Field(min_length=1)
    items: list[GradeInput]


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

