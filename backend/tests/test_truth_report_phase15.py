import asyncio

from backend.ai.football_reasoner import FootballReasoner
from backend.ai.provider import AIProvider
from backend.football.truth_report import build_play_observations, five_trait_summary
from backend.grading.models import Evidence, PositionGrade, TraitScore


def test_observation_builder_preserves_measured_evidence_without_claiming_tackle():
    track = {"track_id": 7, "movement": {"field_speed_mph": 18.2, "calibration_confidence": .7},
             "positions": [{"frame": 1, "timestamp_ms": 1000, "center_x": 10, "center_y": 10,
                            "bbox": [0, 0, 20, 40], "confidence": .9}]}
    plays = [{"play_id": "P001", "start_time": 0, "snap_time": 1, "end_time": 2, "excluded": False}]
    biomechanics = {"contact_candidates": [{"frame": 1, "timestamp_ms": 1000, "track_ids": [7, 8],
                                             "confidence": .8, "status": "contact_candidate"}],
                    "ball_track": {"confidence": .6, "positions": [{"frame": 1, "center_x": 12, "center_y": 12}]},
                    "poses": [{"frame": 1, "poses": [{"orientation_deg": -90}]}]}
    observation = build_play_observations("V1", "player-12", "LB", track, plays, biomechanics)[0]
    assert observation.movement["field_speed_mph"].value == 18.2
    assert observation.result["contact_candidates"].value == 1
    assert "tackle" not in observation.result
    assert observation.evidence[0].frame_ids == [1]


def test_five_demo_traits_are_views_of_official_position_traits():
    evidence = Evidence(video_id="V1", play_id="P1", timestamp_start=1, timestamp_end=2,
                        player_id="12", description="verified")
    grade = PositionGrade(position="LB", grade=60, confidence=.8, traits={
        "play_speed": TraitScore(trait="play_speed", score=62, confidence=.8, sample_count=2, evidence=[evidence]),
        "read_react": TraitScore(trait="read_react", score=58, confidence=.7, sample_count=1, evidence=[evidence]),
        "tackling_space": None,
    }, unknown_traits=["tackling_space"])
    summary = five_trait_summary(grade)
    assert summary["field_speed"]["score"] == 62
    assert summary["play_recognition"]["official_traits"] == ["read_react"]
    assert summary["tackling"]["status"] == "unknown"
    assert summary["field_speed"]["evidence"][0]["play_id"] == "P1"


def test_reasoner_is_given_only_official_position_trait_names():
    class CapturingProvider(AIProvider):
        prompt = ""

        async def generate_json(self, prompt, schema):
            self.prompt = prompt
            return {"observations": [], "provider_note": "test"}

    provider = CapturingProvider()
    observation = build_play_observations(
        "V1", "player-12", "LB",
        {"track_id": 7, "positions": [{"frame": 1, "timestamp_ms": 1000, "center_x": 0,
                                        "center_y": 0, "confidence": .9}]},
        [{"play_id": "P1", "start_time": 0, "snap_time": 1, "end_time": 2, "excluded": False}],
        None,
    )[0]
    asyncio.run(FootballReasoner(provider).reason(observation, ["read_react", "play_speed"]))
    assert "Use only these official position traits: read_react, play_speed" in provider.prompt
