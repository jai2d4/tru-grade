"""Official AI-observation-to-TruGrade orchestration and local persistence."""
from __future__ import annotations

import json
from pathlib import Path

from backend.ai.football_reasoner import FootballReasoningResult
from backend.football.observations import FootballObservation
from .engine import TruGradeFilmEngine
from .event_mapper import reasoning_to_events
from .models import PositionGrade


class GradeStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, player_id: str, game_id: str, grade: PositionGrade, events: list) -> dict:
        payload = {"player_id": player_id, "game_id": game_id,
                   "position_grade": grade.model_dump(mode="json"),
                   "game_grade": grade.grade, "confidence": grade.confidence,
                   "events": [event.model_dump(mode="json") for event in events]}
        path = self.root / f"{player_id}.json"
        records = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
        records.append(payload)
        path.write_text(json.dumps(records, indent=2), encoding="utf-8")
        return payload

    def get(self, player_id: str) -> list[dict]:
        path = self.root / f"{player_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def calculate_official_grade(position: str, items: list[tuple[FootballObservation, FootballReasoningResult]]) -> tuple[PositionGrade, list]:
    events = [event for observation, reasoning in items for event in reasoning_to_events(observation, reasoning)]
    return TruGradeFilmEngine().grade(position, events), events
