import json

import pytest

from backend.ai.football_reasoner import FootballReasoningResult
from backend.football.observations import FootballObservation
from backend.grading.event_mapper import load_scoring_events, reasoning_to_events
from backend.grading.models import Evidence
from backend.grading.service import GradeStore, calculate_official_grade


def pair(value="positive_execution", trait="read_react", confidence=.8):
    source = FootballObservation(
        observation_id="O1", play_id="P1", player_id="19", position="LB",
        evidence=[Evidence(video_id="V1", play_id="P1", timestamp_start=1,
                           timestamp_end=2, description="Verified film range")],
    )
    reasoning = FootballReasoningResult(observations=[{
        "trait": trait, "value": value, "confidence": confidence,
        "evidence_timestamp": 1.5, "reason": "Observed on structured film evidence",
    }])
    return source, reasoning


def test_provisional_scoring_values_are_human_editable_json():
    values = load_scoring_events()
    assert values["game_changing_positive"] > values["positive_execution"] > values["neutral_execution"]
    assert values["game_changing_negative"] < values["minor_error"]


def test_ai_reasoning_becomes_event_then_deterministic_grade():
    grade, events = calculate_official_grade("LB", [pair()])
    assert events[0].value == load_scoring_events()["positive_execution"]
    assert grade.grade == 53
    assert grade.confidence == .8


def test_unknown_is_excluded_from_official_grade():
    grade, events = calculate_official_grade("LB", [pair(value="unknown")])
    assert events == []
    assert grade.grade is None
    assert grade.confidence == 0


def test_non_position_trait_is_rejected():
    with pytest.raises(ValueError, match="not an official LB trait"):
        reasoning_to_events(*pair(trait="arm_strength"))


def test_unsupported_ai_event_is_rejected():
    with pytest.raises(ValueError, match="Unsupported grading event"):
        reasoning_to_events(*pair(value="AI_SAYS_100"))


def test_grade_store_keeps_grade_and_confidence_separate(tmp_path):
    grade, events = calculate_official_grade("LB", [pair(confidence=.2)])
    payload = GradeStore(tmp_path).save("19", "game-1", grade, events)
    assert payload["game_grade"] == 53
    assert payload["confidence"] == .2
    assert json.loads((tmp_path / "19.json").read_text())[0]["events"][0]["rule_id"].startswith("LB_")

