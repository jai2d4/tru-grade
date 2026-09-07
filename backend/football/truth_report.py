"""Evidence-to-reasoning pipeline for the five-trait demo Truth Report."""
from __future__ import annotations

from math import hypot

from backend.football.observations import FootballObservation, ObservationDatum
from backend.grading.models import Evidence, PositionGrade


DEMO_TRAIT_ALIASES = {
    "field_speed": {"foot_speed", "speed", "play_speed", "acceleration", "burst_acceleration",
                    "acceleration_burst", "quickness", "foot_quickness", "range", "lateral_range"},
    "contact": {"contact_balance", "play_strength", "strike_shed", "heavy_hands", "anchor",
                "blocking", "press", "toughness"},
    "play_recognition": {"instincts", "instincts_judgment", "read_react", "vision",
                         "quick_minded", "awareness", "spatial_awareness", "anticipation"},
    "tackling": {"tackling", "tackling_space", "leverage_angles", "strike_shed"},
    "versatility": {"reactionary_athleticism", "team_value", "coverage", "coverage_drop",
                    "man_coverage", "zone_coverage", "inside_outside_run", "throw_off_platform"},
}


def build_play_observations(video_id: str, player_id: str, position: str, track: dict,
                            plays: list[dict], biomechanics: dict | None) -> list[FootballObservation]:
    biomechanics = biomechanics or {}
    contacts = biomechanics.get("contact_candidates", [])
    ball_by_frame = {point["frame"]: point for point in biomechanics.get("ball_track", {}).get("positions", [])}
    pose_by_frame = {record["frame"]: record for record in biomechanics.get("poses", [])}
    observations = []
    for play in plays:
        if play.get("excluded"):
            continue
        start_ms, end_ms = play["start_time"] * 1000, play["end_time"] * 1000
        positions = [point for point in track.get("positions", [])
                     if start_ms <= point["timestamp_ms"] <= end_ms]
        if not positions:
            continue
        frame_ids = [point["frame"] for point in positions]
        evidence = Evidence(video_id=video_id, play_id=play["play_id"],
                            timestamp_start=play["start_time"], timestamp_end=play["end_time"],
                            frame_ids=frame_ids, track_id=track["track_id"], player_id=player_id,
                            description="Tracked player, field movement, pose, ball, and contact evidence.")
        movement = track.get("movement", {})
        speed = movement.get("field_speed_mph", "unknown")
        calibration_confidence = movement.get("calibration_confidence", 0)
        relevant_contacts = [event for event in contacts if track["track_id"] in event["track_ids"]
                             and event["frame"] in frame_ids]
        ball_distances = []
        for point in positions:
            ball = ball_by_frame.get(point["frame"])
            if ball:
                ball_distances.append(hypot(point["center_x"] - ball["center_x"],
                                            point["center_y"] - ball["center_y"]))
        pose_frames = sum(1 for frame in frame_ids if pose_by_frame.get(frame, {}).get("poses"))
        observations.append(FootballObservation(
            observation_id=f'{video_id}-{play["play_id"]}-{track["track_id"]}',
            play_id=play["play_id"], player_id=player_id, position=position,
            movement={
                "field_speed_mph": ObservationDatum(
                    value=speed, confidence=calibration_confidence,
                    evidence_timestamp=play["snap_time"],
                    reason="Calibrated track speed." if speed != "unknown" else "Verified field scale unavailable."),
                "pose_frames": ObservationDatum(
                    value=pose_frames, confidence=pose_frames / max(len(frame_ids), 1),
                    evidence_timestamp=play["snap_time"], reason="Frames containing body-pose evidence."),
            },
            result={
                "contact_candidates": ObservationDatum(
                    value=len(relevant_contacts),
                    confidence=max((item["confidence"] for item in relevant_contacts), default=0),
                    evidence_timestamp=relevant_contacts[0]["timestamp_ms"] / 1000 if relevant_contacts else None,
                    reason="Geometry indicates proximity only; AI must not assume a tackle."),
                "minimum_ball_distance_px": ObservationDatum(
                    value=round(min(ball_distances), 2) if ball_distances else "unknown",
                    confidence=biomechanics.get("ball_track", {}).get("confidence", 0),
                    evidence_timestamp=play["snap_time"],
                    reason="Measured player-to-ball distance; outcome is not inferred."),
            },
            evidence=[evidence],
        ))
    return observations


def five_trait_summary(grade: PositionGrade) -> dict:
    output = {}
    for display_name, aliases in DEMO_TRAIT_ALIASES.items():
        matched = [value for name, value in grade.traits.items() if name in aliases and value is not None]
        if not matched:
            output[display_name] = {"score": None, "confidence": 0, "status": "unknown",
                                    "official_traits": [], "evidence": []}
            continue
        weight = sum(item.sample_count for item in matched)
        output[display_name] = {
            "score": round(sum(item.score * item.sample_count for item in matched) / weight, 2),
            "confidence": round(sum(item.confidence * item.sample_count for item in matched) / weight, 4),
            "status": "graded",
            "official_traits": [item.trait for item in matched],
            "evidence": [e.model_dump(mode="json") for item in matched for e in item.evidence],
        }
    return output
