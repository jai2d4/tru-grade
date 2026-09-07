"""Movement metrics derived only from tracked coordinates."""
from __future__ import annotations

from math import hypot


def movement_metrics(positions: list[dict], calibration=None) -> dict:
    if len(positions) < 2:
        return {"value": "unknown", "confidence": 0.0, "reason": "Insufficient tracked points."}
    speeds = [float(point.get("speed_px", 0)) for point in positions]
    directions = [float(point.get("direction", 0)) for point in positions]
    accelerations = []
    for before, after in zip(positions, positions[1:]):
        elapsed = (after["timestamp_ms"] - before["timestamp_ms"]) / 1000
        if elapsed > 0:
            accelerations.append((float(after.get("speed_px", 0)) - float(before.get("speed_px", 0))) / elapsed)
    displacement = hypot(positions[-1]["center_x"] - positions[0]["center_x"],
                         positions[-1]["center_y"] - positions[0]["center_y"])
    direction_change = max(directions) - min(directions) if directions else 0
    result = {"max_speed_px": round(max(speeds), 2),
            "max_acceleration_px_s2": round(max(accelerations, default=0), 2),
            "max_deceleration_px_s2": round(min(accelerations, default=0), 2),
            "direction_change_deg": round(direction_change, 2),
            "displacement_px": round(displacement, 2),
            "confidence": round(sum(float(p.get("confidence", 0)) for p in positions) / len(positions), 4)}
    if calibration is not None:
        field_points = [calibration.pixel_to_field(point["center_x"], point["center_y"]) for point in positions]
        yard_speeds = []
        for before, after, field_before, field_after in zip(
            positions, positions[1:], field_points, field_points[1:]
        ):
            elapsed = (after["timestamp_ms"] - before["timestamp_ms"]) / 1000
            if elapsed > 0:
                yard_speeds.append(hypot(field_after[0] - field_before[0], field_after[1] - field_before[1]) / elapsed)
        result.update(
            field_positions=[{"x_yards": x, "y_yards": y} for x, y in field_points],
            displacement_yards=round(hypot(field_points[-1][0] - field_points[0][0],
                                           field_points[-1][1] - field_points[0][1]), 3),
            max_speed_yards_per_second=round(max(yard_speeds, default=0), 3),
            field_speed_mph=round(max(yard_speeds, default=0) * 2.04545, 2),
            calibration_confidence=calibration.confidence,
            confidence=round(result["confidence"] * calibration.confidence, 4),
        )
    return result
