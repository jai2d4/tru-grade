"""Typed access to the native core.

Every function here assumes ``is_available()`` is True — check once at the call
site rather than per frame. Values come back unrounded; rounding is applied by
the caller so the native and pure-Python paths round exactly once, in the same
place, to the same policy.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass

from . import _loader
from ._loader import BBox, Detection, MovementMetrics, Position, TrackPoint


class NativeCoreError(RuntimeError):
    """The native core was reachable but rejected the call."""


def _check(status: int) -> None:
    if status != _loader.TG_OK:
        raise NativeCoreError(_loader.status_message(status))


def iou(first: list[float], second: list[float]) -> float:
    """Intersection over union of two [x1, y1, x2, y2] boxes."""
    a = BBox(first[0], first[1], first[2], first[3])
    b = BBox(second[0], second[1], second[2], second[3])
    out = ctypes.c_double()
    _check(_loader.library().tg_iou(ctypes.byref(a), ctypes.byref(b), ctypes.byref(out)))
    return out.value


def torso_orientation_deg(shoulder_x: float, shoulder_y: float,
                          hip_x: float, hip_y: float) -> float:
    out = ctypes.c_double()
    _check(_loader.library().tg_torso_orientation_deg(
        shoulder_x, shoulder_y, hip_x, hip_y, ctypes.byref(out)))
    return out.value


@dataclass(frozen=True)
class RawMovement:
    """Unrounded movement metrics straight from the native core."""

    max_speed_px: float
    max_acceleration_px_s2: float
    max_deceleration_px_s2: float
    direction_change_deg: float
    displacement_px: float
    confidence: float


def movement_metrics(positions: list[dict]) -> RawMovement | None:
    """Summarise a track, or None when there are too few points to say anything."""
    count = len(positions)
    buffer = (Position * count)() if count else None
    for index, point in enumerate(positions):
        buffer[index] = Position(
            float(point.get("center_x", 0)),
            float(point.get("center_y", 0)),
            int(point.get("timestamp_ms", 0)),
            float(point.get("speed_px", 0)),
            float(point.get("direction", 0)),
            float(point.get("confidence", 0)),
        )

    out = MovementMetrics()
    status = _loader.library().tg_movement_metrics_compute(buffer, count, ctypes.byref(out))
    if status == _loader.TG_ERR_INSUFFICIENT_POINTS:
        return None
    _check(status)
    return RawMovement(
        max_speed_px=out.max_speed_px,
        max_acceleration_px_s2=out.max_acceleration_px_s2,
        max_deceleration_px_s2=out.max_deceleration_px_s2,
        direction_change_deg=out.direction_change_deg,
        displacement_px=out.displacement_px,
        confidence=out.confidence,
    )


@dataclass(frozen=True)
class RawTrackPoint:
    """One association result, unrounded."""

    track_id: int
    center_x: float
    center_y: float
    velocity_x: float
    velocity_y: float
    speed_px: float
    direction: float


class NativeTracker:
    """Owns a tg_tracker handle for the lifetime of one video."""

    def __init__(self, high_threshold: float, low_threshold: float,
                 match_iou: float, max_lost_frames: int):
        library = _loader.library()
        if library is None:
            raise NativeCoreError("the native core is not available")
        self._handle = library.tg_tracker_create(
            high_threshold, low_threshold, match_iou, max_lost_frames)
        if not self._handle:
            raise NativeCoreError("the native core could not allocate a tracker")
        # Held directly so __del__ still works during interpreter shutdown, when
        # module globals may already have been torn down.
        self._destroy = library.tg_tracker_destroy
        self._update = library.tg_tracker_update

    def update(self, detections: list[dict], frame: int, timestamp_ms: int) -> list[RawTrackPoint]:
        """Associate one frame's detections, already filtered to a single class."""
        count = len(detections)
        if not count:
            return []

        inputs = (Detection * count)()
        for index, detection in enumerate(detections):
            box = detection["bbox"]
            inputs[index] = Detection(
                BBox(float(box[0]), float(box[1]), float(box[2]), float(box[3])),
                float(detection["confidence"]),
            )

        # One detection can produce at most one point, so count entries always fit.
        outputs = (TrackPoint * count)()
        written = ctypes.c_int32()
        _check(self._update(self._handle, inputs, count, frame, timestamp_ms,
                            outputs, count, ctypes.byref(written)))

        return [
            RawTrackPoint(
                track_id=outputs[index].track_id,
                center_x=outputs[index].center_x,
                center_y=outputs[index].center_y,
                velocity_x=outputs[index].velocity_x,
                velocity_y=outputs[index].velocity_y,
                speed_px=outputs[index].speed_px,
                direction=outputs[index].direction,
            )
            for index in range(written.value)
        ]

    def close(self) -> None:
        handle, self._handle = getattr(self, "_handle", None), None
        if handle:
            self._destroy(handle)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:  # pragma: no cover - nothing useful to do at teardown
            pass
