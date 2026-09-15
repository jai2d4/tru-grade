"""Plausibility filtering for football detections.

The detector is a stock YOLO model, so "football" is really COCO's
`sports ball` class — trained on soccer balls, basketballs and tennis
balls, none of which are a brown prolate spheroid that spends most of a
play tucked under someone's arm. It produces false positives: helmets,
gloved hands, turf patches, line-judge caps.

That matters because ball positions are not cosmetic. They flow through
backend/football/truth_report.py into ball-distance observations, into
the reasoner, and into an athlete's grade — so a helmet mistaken for the
ball makes a player look involved in a play they were nowhere near.

Training a football-specific model is the real fix (set BALL_MODEL_PATH
to those weights and this filtering can be relaxed via
BALL_STRICT_FILTER=false). Until then, this rejects the candidates that
cannot physically be a football, using the one reliable reference in the
frame: the players themselves.
"""
from __future__ import annotations

import os

# A regulation football's long axis is ~11 inches against a ~70-inch
# player, so roughly 0.16 of a player's height. The accepted band is much
# wider than that on both sides to absorb perspective — a ball thrown
# toward the camera genuinely looks larger, a ball downfield smaller —
# while still excluding the things that are obviously not a football.
MIN_PLAYER_HEIGHT_RATIO = float(os.getenv("BALL_MIN_PLAYER_RATIO", "0.03"))
MAX_PLAYER_HEIGHT_RATIO = float(os.getenv("BALL_MAX_PLAYER_RATIO", "0.35"))

# A football is never this elongated in any orientation; something this
# shape is a limb, a shoe, or a painted field marking.
MAX_ASPECT_RATIO = float(os.getenv("BALL_MAX_ASPECT", "3.0"))

# Borrowing a class the model was never trained for deserves a higher bar
# than the 0.25 used for `person`, which it genuinely knows.
MIN_CONFIDENCE = float(os.getenv("BALL_MIN_CONFIDENCE", "0.35"))


def _dimensions(bbox) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return abs(x2 - x1), abs(y2 - y1)


def median_player_height(detections: list[dict]) -> float | None:
    """Median height of players in this frame — the scale reference.

    Median rather than mean: a single bad player box (two players merged,
    or a partially cropped one at the frame edge) shouldn't move the
    reference enough to change what counts as a plausible ball.
    """
    heights = sorted(
        _dimensions(item["bbox"])[1]
        for item in detections
        if item.get("class") == "player" and item.get("bbox")
    )
    if not heights:
        return None
    middle = len(heights) // 2
    if len(heights) % 2:
        return heights[middle]
    return (heights[middle - 1] + heights[middle]) / 2


def rejection_reason(ball: dict, player_height: float | None) -> str | None:
    """Why this candidate cannot be a football, or None if it might be.

    Returns the reason rather than a bool so the caller can report what
    was discarded instead of silently dropping detections.
    """
    if ball.get("confidence", 0) < MIN_CONFIDENCE:
        return f"confidence {ball.get('confidence')} below {MIN_CONFIDENCE}"

    width, height = _dimensions(ball["bbox"])
    if width <= 0 or height <= 0:
        return "degenerate bounding box"

    longest, shortest = max(width, height), min(width, height)
    if shortest > 0 and longest / shortest > MAX_ASPECT_RATIO:
        return f"aspect ratio {longest / shortest:.1f} exceeds {MAX_ASPECT_RATIO}"

    # Without a player in frame there is no scale reference, so size can't
    # be judged. Allowed through rather than dropped: a ball in flight
    # downfield is a legitimate detection, and inventing a rejection would
    # be as wrong as inventing an acceptance.
    if player_height is None or player_height <= 0:
        return None

    ratio = longest / player_height
    if ratio < MIN_PLAYER_HEIGHT_RATIO:
        return f"size {ratio:.3f} of player height is below {MIN_PLAYER_HEIGHT_RATIO}"
    if ratio > MAX_PLAYER_HEIGHT_RATIO:
        return f"size {ratio:.2f} of player height exceeds {MAX_PLAYER_HEIGHT_RATIO}"
    return None


def filter_candidates(detections: list[dict]) -> tuple[list[dict], list[str]]:
    """Split football detections into plausible ones and reasons rejected.

    Set BALL_STRICT_FILTER=false once BALL_MODEL_PATH points at
    football-trained weights — a model that actually knows the object
    doesn't need heuristics second-guessing it.
    """
    balls = [item for item in detections if item.get("class") == "football"]
    if os.getenv("BALL_STRICT_FILTER", "true").lower() != "true":
        return balls, []

    player_height = median_player_height(detections)
    kept, rejected = [], []
    for ball in balls:
        reason = rejection_reason(ball, player_height)
        if reason is None:
            kept.append(ball)
        else:
            rejected.append(reason)
    return kept, rejected
