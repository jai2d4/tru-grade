"""Football-detection plausibility filtering.

With stock YOLO weights, "football" is COCO's `sports ball` class — a
model trained on soccer balls and basketballs, not on a brown prolate
spheroid usually tucked under an arm. Its false positives (helmets,
gloved hands, turf patches) are not cosmetic: ball positions flow through
truth_report.py into ball-distance evidence and into an athlete's grade,
so a helmet mistaken for the ball puts a player in a play they were never
near.

These tests use realistic pixel geometry — a ~200px-tall player in a
wide shot, against which a football is roughly 30px.
"""
from __future__ import annotations

import pytest

from backend.vision import ball_filter
from backend.vision.biomechanics import BallTracker

PLAYER_HEIGHT = 200.0


def player(x=100.0, y=100.0, height=PLAYER_HEIGHT):
    return {"class": "player", "confidence": 0.9,
            "bbox": [x, y, x + height * 0.4, y + height]}


def ball(size=30.0, x=500.0, y=300.0, confidence=0.6, aspect=1.4):
    return {"class": "football", "confidence": confidence,
            "bbox": [x, y, x + size * aspect, y + size]}


def test_a_plausible_football_is_kept():
    kept, rejected = ball_filter.filter_candidates([player(), ball()])
    assert len(kept) == 1
    assert rejected == []


def test_a_helmet_sized_blob_is_rejected_as_too_small_relative_to_players():
    """A helmet reads as a small round object — precisely what COCO's
    sports-ball class was trained to find."""
    kept, rejected = ball_filter.filter_candidates([player(), ball(size=3.0, aspect=1.0)])
    assert kept == []
    assert any("below" in reason for reason in rejected)


def test_a_detection_the_size_of_a_player_is_rejected():
    """A turf patch or a crowd blob picked up as a 'ball'."""
    kept, rejected = ball_filter.filter_candidates([player(), ball(size=PLAYER_HEIGHT * 0.9)])
    assert kept == []
    assert any("exceeds" in reason for reason in rejected)


def test_a_long_thin_detection_is_rejected():
    """A football is never this elongated in any orientation — that shape
    is a limb, a shoe, or a painted line."""
    kept, rejected = ball_filter.filter_candidates([player(), ball(size=20.0, aspect=6.0)])
    assert kept == []
    assert any("aspect" in reason for reason in rejected)


def test_low_confidence_candidates_are_rejected():
    """Borrowing a class the model was never trained for deserves a higher
    bar than the threshold used for `person`, which it genuinely knows."""
    kept, rejected = ball_filter.filter_candidates([player(), ball(confidence=0.28)])
    assert kept == []
    assert any("confidence" in reason for reason in rejected)


def test_a_ball_with_no_player_in_frame_is_allowed_through():
    """No player means no scale reference. A ball in flight downfield is a
    legitimate detection, and inventing a rejection would be as wrong as
    inventing an acceptance."""
    kept, rejected = ball_filter.filter_candidates([ball()])
    assert len(kept) == 1
    assert rejected == []


def test_the_scale_reference_survives_one_bad_player_box():
    """Median, not mean: two merged players or a cropped one at the frame
    edge must not move the reference enough to change the verdict."""
    detections = [player(), player(), player(height=2000.0), ball()]
    kept, _ = ball_filter.filter_candidates(detections)
    assert len(kept) == 1, "a single outlier player box redefined plausible ball size"


def test_filtering_can_be_switched_off_for_a_football_trained_model(monkeypatch):
    """A model that actually knows the object shouldn't be second-guessed
    by heuristics built for one that doesn't."""
    monkeypatch.setenv("BALL_STRICT_FILTER", "false")
    kept, rejected = ball_filter.filter_candidates([player(), ball(size=3.0, confidence=0.1)])
    assert len(kept) == 1
    assert rejected == []


# ---------- tracker integration ----------


def _frame(detections, number=1):
    return {"frame": number, "timestamp_ms": number * 33, "detections": detections}


def test_the_tracker_ignores_implausible_candidates():
    tracker = BallTracker()
    assert tracker.update(_frame([player(), ball(size=PLAYER_HEIGHT * 0.9)])) is None
    assert tracker.positions == []
    assert tracker.rejected_count == 1


def test_the_tracker_still_follows_a_real_ball():
    tracker = BallTracker()
    first = tracker.update(_frame([player(), ball(x=500.0)], number=1))
    second = tracker.update(_frame([player(), ball(x=520.0)], number=2))
    assert first is not None and second is not None
    assert len(tracker.positions) == 2
    assert tracker.rejected_count == 0


def test_export_declares_that_a_stock_model_produced_the_track(monkeypatch):
    """Downstream must be able to tell a stock-model ball track from a
    football-trained one, rather than weighing them the same."""
    monkeypatch.setenv("BALL_MODEL_PATH", "yolo11n.pt")
    tracker = BallTracker()
    tracker.update(_frame([player(), ball()]))

    exported = tracker.export()
    assert exported["model_is_football_specific"] is False
    assert "not football-trained weights" in exported["note"]
    assert exported["rejected_implausible"] == 0


def test_export_reports_a_football_trained_model_without_the_caveat(monkeypatch):
    monkeypatch.setenv("BALL_MODEL_PATH", "football-detector-v2.pt")
    tracker = BallTracker()
    tracker.update(_frame([player(), ball()]))

    exported = tracker.export()
    assert exported["model_is_football_specific"] is True
    assert exported["note"] is None


def test_export_counts_what_was_discarded():
    """Silently dropping detections would hide a detector doing badly on
    this film; the count is how that becomes visible."""
    tracker = BallTracker()
    tracker.update(_frame([player(), ball(size=PLAYER_HEIGHT * 0.9)], number=1))
    tracker.update(_frame([player(), ball(size=2.0)], number=2))
    tracker.update(_frame([player(), ball()], number=3))

    exported = tracker.export()
    assert exported["rejected_implausible"] == 2
    assert len(exported["positions"]) == 1
