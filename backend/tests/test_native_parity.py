"""The native core and the pure-Python fallback must agree exactly.

Two implementations of the same arithmetic is a standing invitation to drift,
so these tests are the contract between them: every assertion here compares the
native result against the Python one on the same input and demands equality,
not closeness. A failure means one path was changed without the other.

Everything skips cleanly when the library has not been built, so a checkout
that never ran scripts/build_native.sh still has a green suite.
"""
from __future__ import annotations

import random

import pytest

from backend import native
from backend.football.movement import _core_metrics, movement_metrics
from backend.vision.tracker import ByteTrackTracker, _iou

pytestmark = pytest.mark.skipif(
    not native.is_available(),
    reason=f"native core not built: {native.load_error()}",
)


def _python_tracker(**kwargs) -> ByteTrackTracker:
    """A tracker pinned to the Python associator.

    Detached immediately after construction, while the track table is still
    empty, so the two trackers start from identical state.
    """
    tracker = ByteTrackTracker(**kwargs)
    tracker._native = None
    return tracker


def _rounded(raw: native.RawMovement) -> dict:
    """Apply the rounding `_core_metrics` applies, so the two are comparable.

    The native core returns unrounded values on purpose; this is the only place
    that rounding is duplicated, and duplicating it is the point — it is what
    lets the comparison below be exact equality rather than a tolerance.
    """
    return {"max_speed_px": round(raw.max_speed_px, 2),
            "max_acceleration_px_s2": round(raw.max_acceleration_px_s2, 2),
            "max_deceleration_px_s2": round(raw.max_deceleration_px_s2, 2),
            "direction_change_deg": round(raw.direction_change_deg, 2),
            "displacement_px": round(raw.displacement_px, 2),
            "confidence": round(raw.confidence, 4)}


def _detection(x: float, y: float, width: float, height: float, confidence: float) -> dict:
    return {"class": "player", "confidence": confidence,
            "bbox": [x, y, x + width, y + height]}


def test_library_reports_itself_available():
    assert native.is_available()
    status = native.status()
    assert status["available"] is True
    assert status["version"]
    assert status["reason"] is None


@pytest.mark.parametrize("a, b", [
    ([0, 0, 10, 10], [0, 0, 10, 10]),
    ([0, 0, 10, 10], [5, 0, 15, 10]),
    ([0, 0, 10, 10], [20, 20, 30, 30]),
    ([0, 0, 10, 10], [2, 2, 8, 8]),
    ([0, 0, 0, 0], [0, 0, 0, 0]),
    ([5, 5, 5, 5], [0, 0, 10, 10]),
    ([-10, -10, -5, -5], [-7, -7, -1, -1]),
])
def test_iou_matches_python(a, b):
    assert native.iou(a, b) == _iou(a, b)


def test_iou_matches_python_on_random_boxes():
    rng = random.Random(20260914)
    for _ in range(2000):
        a = [rng.uniform(-50, 200), rng.uniform(-50, 200)]
        a += [a[0] + rng.uniform(0, 80), a[1] + rng.uniform(0, 80)]
        b = [rng.uniform(-50, 200), rng.uniform(-50, 200)]
        b += [b[0] + rng.uniform(0, 80), b[1] + rng.uniform(0, 80)]
        assert native.iou(a, b) == _iou(a, b), (a, b)


def _positions(rng: random.Random, count: int, *, simultaneous: bool = False) -> list[dict]:
    positions = []
    timestamp = 0
    for _ in range(count):
        positions.append({
            "center_x": round(rng.uniform(0, 1920), 2),
            "center_y": round(rng.uniform(0, 1080), 2),
            "timestamp_ms": timestamp,
            "speed_px": round(rng.uniform(0, 400), 2),
            "direction": round(rng.uniform(-180, 180), 2),
            "confidence": round(rng.uniform(0, 1), 4),
        })
        timestamp += 0 if simultaneous else rng.randint(1, 120)
    return positions


@pytest.mark.parametrize("count", [2, 3, 5, 17, 64])
def test_movement_metrics_match_python(count):
    rng = random.Random(1000 + count)
    for _ in range(50):
        positions = _positions(rng, count)
        raw = native.movement_metrics(positions)
        assert raw is not None
        assert _rounded(raw) == _core_metrics(positions)


def test_movement_metrics_match_python_when_timestamps_repeat():
    """Every interval is zero, so neither path may report an acceleration."""
    rng = random.Random(7)
    positions = _positions(rng, 8, simultaneous=True)
    raw = native.movement_metrics(positions)
    assert raw is not None
    native_result = _rounded(raw)
    assert native_result == _core_metrics(positions)
    assert native_result["max_acceleration_px_s2"] == 0
    assert native_result["max_deceleration_px_s2"] == 0


@pytest.mark.parametrize("count", [0, 1])
def test_short_tracks_are_unknown_on_both_paths(count):
    rng = random.Random(3)
    positions = _positions(rng, count)
    assert native.movement_metrics(positions) is None
    assert movement_metrics(positions)["value"] == "unknown"


def _run_stream(tracker: ByteTrackTracker, frames: list[dict]) -> list[list[dict]]:
    return [tracker.update(frame) for frame in frames]


def _assert_streams_match(frames: list[dict], **kwargs) -> None:
    native_tracker = ByteTrackTracker(**kwargs)
    assert native_tracker.uses_native_core, "this test is meaningless without the native path"
    python_tracker = _python_tracker(**kwargs)

    assert _run_stream(native_tracker, frames) == _run_stream(python_tracker, frames)
    assert native_tracker.export_tracks() == python_tracker.export_tracks()


def test_tracker_matches_python_on_a_simple_drift():
    frames = [
        {"frame": index, "timestamp_ms": index * 100,
         "detections": [_detection(index * 2, 0, 10, 20, 0.9)]}
        for index in range(30)
    ]
    _assert_streams_match(frames)


def test_tracker_matches_python_across_the_confidence_split():
    """Weak detections must recover only the tracks strong ones did not claim."""
    frames = []
    for index in range(20):
        frames.append({"frame": index, "timestamp_ms": index * 40, "detections": [
            _detection(index * 3, 0, 12, 24, 0.95),
            _detection(index * 3 + 4, 2, 12, 24, 0.2),
            _detection(300 - index * 3, 100, 12, 24, 0.55),
        ]})
    _assert_streams_match(frames)


def test_tracker_matches_python_when_boxes_tie():
    """Identical candidates: both paths must keep the first, not an arbitrary one."""
    frames = []
    for index in range(12):
        frames.append({"frame": index, "timestamp_ms": index * 50, "detections": [
            _detection(50, 50, 20, 20, 0.9),
            _detection(50, 50, 20, 20, 0.9),
            _detection(50, 50, 20, 20, 0.8),
        ]})
    _assert_streams_match(frames)


def test_tracker_matches_python_when_tracks_go_stale():
    """A gap longer than max_lost_frames must retire the track on both paths."""
    frames = [{"frame": 0, "timestamp_ms": 0, "detections": [_detection(0, 0, 10, 10, 0.9)]}]
    frames.append({"frame": 1, "timestamp_ms": 100, "detections": []})
    frames.append({"frame": 40, "timestamp_ms": 4000, "detections": [_detection(0, 0, 10, 10, 0.9)]})
    frames.append({"frame": 41, "timestamp_ms": 4100, "detections": [_detection(0, 0, 10, 10, 0.9)]})
    _assert_streams_match(frames, max_lost_frames=5)


def test_tracker_matches_python_when_frames_share_a_timestamp():
    """The 1e-6 floor on elapsed time has to be applied identically."""
    frames = [
        {"frame": index, "timestamp_ms": 500,
         "detections": [_detection(index, 0, 10, 20, 0.9)]}
        for index in range(6)
    ]
    _assert_streams_match(frames)


def test_tracker_matches_python_on_empty_and_filtered_frames():
    frames = [
        {"frame": 0, "timestamp_ms": 0, "detections": []},
        {"frame": 1, "timestamp_ms": 100, "detections": [_detection(0, 0, 10, 10, 0.01)]},
        {"frame": 2, "timestamp_ms": 200, "detections": [
            {"class": "football", "confidence": 0.99, "bbox": [0, 0, 5, 5]}]},
        {"frame": 3, "timestamp_ms": 300, "detections": [_detection(0, 0, 10, 10, 0.9)]},
    ]
    _assert_streams_match(frames)


def test_tracker_matches_python_on_a_random_stream():
    """The broad net: crossing players, churn, and detections that come and go."""
    rng = random.Random(20260914)
    frames = []
    for index in range(120):
        detections = []
        for _ in range(rng.randint(0, 6)):
            detections.append(_detection(
                round(rng.uniform(0, 500), 2), round(rng.uniform(0, 300), 2),
                round(rng.uniform(5, 40), 2), round(rng.uniform(5, 40), 2),
                round(rng.uniform(0, 1), 4)))
        frames.append({"frame": index, "timestamp_ms": index * rng.randint(0, 80),
                       "detections": detections})
    _assert_streams_match(frames)


def test_movement_metrics_match_end_to_end_through_the_tracker():
    """Tracker output feeds movement_metrics, so parity has to survive the hand-off."""
    rng = random.Random(99)
    frames = []
    for index in range(60):
        frames.append({"frame": index, "timestamp_ms": index * 33, "detections": [
            _detection(round(rng.uniform(0, 400), 2), round(rng.uniform(0, 200), 2),
                       20, 40, round(rng.uniform(0.2, 1), 4))
            for _ in range(rng.randint(1, 3))
        ]})

    native_tracker = ByteTrackTracker()
    python_tracker = _python_tracker()
    _run_stream(native_tracker, frames)
    _run_stream(python_tracker, frames)

    native_tracks = native_tracker.export_tracks()
    python_tracks = python_tracker.export_tracks()
    assert len(native_tracks) == len(python_tracks)
    for native_track, python_track in zip(native_tracks, python_tracks):
        assert (movement_metrics(native_track["positions"])
                == movement_metrics(python_track["positions"]))
