"""Two-stage ByteTrack-style association behind a replaceable tracker API.

The association itself runs in the native core when it is built (see
backend/native and docs/NATIVE_CORE.md) and in the pure-Python `_associate`
below when it is not. The two are asserted to agree exactly in
backend/tests/test_native_parity.py — if you change one, change both.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, degrees, hypot

from backend import native


def _iou(a: list[float], b: list[float]) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = max(0, a[2] - a[0]) * max(0, a[3] - a[1]) + max(0, b[2] - b[0]) * max(0, b[3] - b[1]) - intersection
    return intersection / union if union else 0.0


@dataclass
class _Track:
    track_id: int
    bbox: list[float]
    last_frame: int
    history: list[dict] = field(default_factory=list)


class ByteTrackTracker:
    """Associates high-confidence detections first, then recovers with low scores."""

    def __init__(self, high_threshold: float = 0.5, low_threshold: float = 0.1,
                 match_iou: float = 0.3, max_lost_frames: int = 30):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.match_iou = match_iou
        self.max_lost_frames = max_lost_frames
        self._tracks: dict[int, _Track] = {}
        self._next_id = 1
        self._native = self._open_native()

    def _open_native(self):
        """The native associator, or None to run in Python.

        A tracker that cannot be allocated is not an error worth failing a
        video over — the fallback produces the same numbers.
        """
        if not native.is_available():
            return None
        try:
            return native.NativeTracker(self.high_threshold, self.low_threshold,
                                        self.match_iou, self.max_lost_frames)
        except native.NativeCoreError:
            return None

    @property
    def uses_native_core(self) -> bool:
        return self._native is not None

    @staticmethod
    def _point(frame: int, timestamp_ms: int, center_x: float, center_y: float,
               bbox: list[float], velocity_x: float, velocity_y: float,
               speed: float, direction: float, confidence: float) -> dict:
        """Build a history point.

        Both paths round here and only here, so the native core's extra
        precision can never leak into a value the Python path would have
        rounded away.
        """
        return {"frame": frame, "timestamp_ms": timestamp_ms,
                "center_x": round(center_x, 2), "center_y": round(center_y, 2),
                "bbox": bbox,
                "velocity_x": round(velocity_x, 2), "velocity_y": round(velocity_y, 2),
                "speed_px": round(speed, 2), "direction": round(direction, 2),
                "confidence": confidence}

    def _associate(self, detections: list[dict], frame: int, timestamp_ms: int, claimed: set[int]) -> list[dict]:
        output = []
        for detection in detections:
            candidates = [(track_id, _iou(track.bbox, detection["bbox"])) for track_id, track in self._tracks.items()
                          if track_id not in claimed and frame - track.last_frame <= self.max_lost_frames]
            track_id, score = max(candidates, key=lambda item: item[1], default=(None, 0))
            if track_id is None or score < self.match_iou:
                track_id = self._next_id
                self._next_id += 1
                self._tracks[track_id] = _Track(track_id, detection["bbox"], frame)
            track = self._tracks[track_id]
            old_x = (track.bbox[0] + track.bbox[2]) / 2
            old_y = (track.bbox[1] + track.bbox[3]) / 2
            center_x = (detection["bbox"][0] + detection["bbox"][2]) / 2
            center_y = (detection["bbox"][1] + detection["bbox"][3]) / 2
            elapsed = max((timestamp_ms - track.history[-1]["timestamp_ms"]) / 1000, 1e-6) if track.history else 0
            vx, vy = ((center_x - old_x) / elapsed, (center_y - old_y) / elapsed) if elapsed else (0.0, 0.0)
            point = self._point(frame, timestamp_ms, center_x, center_y, detection["bbox"],
                                vx, vy, hypot(vx, vy), degrees(atan2(vy, vx)), detection["confidence"])
            track.bbox, track.last_frame = detection["bbox"], frame
            track.history.append(point)
            claimed.add(track_id)
            output.append({"track_id": track_id, **point})
        return output

    def _associate_native(self, players: list[dict], frame: int, timestamp_ms: int) -> list[dict]:
        """Run the native associator and mirror its results into the history.

        The native core keeps only what association needs; the point history
        that `export_tracks` serialises stays here, so the two never hold two
        copies of the same list.
        """
        results = self._native.update(players, frame, timestamp_ms)

        # The core returns points in its own output order — the high-confidence
        # pass first, then the low — so the detections have to be re-ordered the
        # same way before they can be paired back up. `players` is already above
        # the low threshold when it gets here, so this split loses nothing.
        high = [item for item in players if item["confidence"] >= self.high_threshold]
        low = [item for item in players if item["confidence"] < self.high_threshold]
        ordered = high + low

        # zip() would paste a shortfall over in silence and mislabel every point
        # after it; a disagreement here means the two filters have drifted apart
        # and is worth stopping for.
        if len(results) != len(ordered):
            raise RuntimeError(
                f"native core returned {len(results)} points for {len(ordered)} detections")

        output = []
        for result, detection in zip(results, ordered):
            point = self._point(frame, timestamp_ms, result.center_x, result.center_y,
                                detection["bbox"], result.velocity_x, result.velocity_y,
                                result.speed_px, result.direction, detection["confidence"])
            track = self._tracks.get(result.track_id)
            if track is None:
                track = _Track(result.track_id, detection["bbox"], frame)
                self._tracks[result.track_id] = track
                self._next_id = max(self._next_id, result.track_id + 1)
            track.bbox, track.last_frame = detection["bbox"], frame
            track.history.append(point)
            output.append({"track_id": result.track_id, **point})
        return output

    def update(self, detection_frame: dict) -> list[dict]:
        players = [item for item in detection_frame["detections"] if item["class"] == "player" and item["confidence"] >= self.low_threshold]
        if self._native is not None:
            return self._associate_native(players, detection_frame["frame"], detection_frame["timestamp_ms"])
        high = [item for item in players if item["confidence"] >= self.high_threshold]
        low = [item for item in players if item["confidence"] < self.high_threshold]
        claimed: set[int] = set()
        return self._associate(high, detection_frame["frame"], detection_frame["timestamp_ms"], claimed) + self._associate(low, detection_frame["frame"], detection_frame["timestamp_ms"], claimed)

    def export_tracks(self) -> list[dict]:
        return [{"track_id": track.track_id, "frames": [p["frame"] for p in track.history],
                 "start_time": track.history[0]["timestamp_ms"] if track.history else None,
                 "end_time": track.history[-1]["timestamp_ms"] if track.history else None,
                 "positions": track.history} for track in self._tracks.values()]
