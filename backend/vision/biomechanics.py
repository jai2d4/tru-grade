"""Swappable pose, dedicated ball tracking, and contact-geometry evidence."""
from __future__ import annotations

import json
import os
from math import atan2, degrees, hypot
from pathlib import Path
from typing import Any

from backend.vision.detector import FootballDetector


class PoseEstimator:
    """Ultralytics pose adapter returning a stable, model-neutral contract."""

    def __init__(self, model_path: str | None = None, model: Any = None):
        self.model_path = model_path or os.getenv("POSE_MODEL_PATH", "yolo11n-pose.pt")
        self.model = model
        self.device = os.getenv("TRUGRADE_DEVICE", "auto")

    def load_model(self):
        if self.model is not None:
            return
        import torch
        from ultralytics import YOLO
        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = YOLO(self.model_path)

    def estimate(self, frame, frame_number: int, timestamp_ms: int) -> dict:
        self.load_model()
        result = self.model.predict(frame, device=self.device, verbose=False)[0]
        poses = []
        if result.keypoints is None:
            return {"frame": frame_number, "timestamp_ms": timestamp_ms, "poses": poses}
        xy = result.keypoints.xy.tolist()
        confidence = result.keypoints.conf.tolist() if result.keypoints.conf is not None else None
        boxes = result.boxes.xyxy.tolist()
        for index, points in enumerate(xy):
            keypoints = [{"index": keypoint_index, "x": round(float(point[0]), 2),
                          "y": round(float(point[1]), 2),
                          "confidence": round(float(confidence[index][keypoint_index]), 4)
                          if confidence else None}
                         for keypoint_index, point in enumerate(points)]
            poses.append({"bbox": [round(float(value), 2) for value in boxes[index]],
                          "keypoints": keypoints, "orientation_deg": body_orientation(keypoints)})
        return {"frame": frame_number, "timestamp_ms": timestamp_ms, "poses": poses}


def body_orientation(keypoints: list[dict]) -> float | None:
    # COCO shoulders: 5/6; hips: 11/12. Their midpoints establish torso axis.
    indexed = {point["index"]: point for point in keypoints}
    if not all(index in indexed for index in (5, 6, 11, 12)):
        return None
    shoulder = ((indexed[5]["x"] + indexed[6]["x"]) / 2, (indexed[5]["y"] + indexed[6]["y"]) / 2)
    hip = ((indexed[11]["x"] + indexed[12]["x"]) / 2, (indexed[11]["y"] + indexed[12]["y"]) / 2)
    return round(degrees(atan2(shoulder[1] - hip[1], shoulder[0] - hip[0])), 2)


class BallTracker:
    """Nearest-motion association for dedicated football detections."""

    def __init__(self, max_jump_px: float = 150):
        self.max_jump_px = max_jump_px
        self.positions: list[dict] = []

    def update(self, detection_frame: dict):
        balls = [item for item in detection_frame["detections"] if item["class"] == "football"]
        if not balls:
            return None
        prior = self.positions[-1] if self.positions else None
        def distance(item):
            x1, y1, x2, y2 = item["bbox"]
            center = ((x1 + x2) / 2, (y1 + y2) / 2)
            return hypot(center[0] - prior["center_x"], center[1] - prior["center_y"]) if prior else -item["confidence"]
        selected = min(balls, key=distance)
        x1, y1, x2, y2 = selected["bbox"]
        point = {"frame": detection_frame["frame"], "timestamp_ms": detection_frame["timestamp_ms"],
                 "center_x": round((x1 + x2) / 2, 2), "center_y": round((y1 + y2) / 2, 2),
                 "bbox": selected["bbox"], "confidence": selected["confidence"]}
        if prior and distance(selected) > self.max_jump_px:
            return None
        self.positions.append(point)
        return point

    def export(self):
        return {"track_id": "football-1", "positions": self.positions,
                "confidence": round(sum(p["confidence"] for p in self.positions) / len(self.positions), 4)
                if self.positions else 0}


def contact_geometry(tracks: list[dict], proximity_ratio: float = .18) -> list[dict]:
    frames: dict[int, list[tuple[int, dict]]] = {}
    for track in tracks:
        for point in track.get("positions", []):
            frames.setdefault(point["frame"], []).append((track["track_id"], point))
    contacts = []
    active = set()
    for frame_number, players in sorted(frames.items()):
        current = set()
        for index, (first_id, first) in enumerate(players):
            for second_id, second in players[index + 1:]:
                gap = _bbox_gap(first["bbox"], second["bbox"])
                height = max(first["bbox"][3] - first["bbox"][1], second["bbox"][3] - second["bbox"][1], 1)
                normalized = gap / height
                pair = tuple(sorted((first_id, second_id)))
                if normalized <= proximity_ratio:
                    current.add(pair)
                    if pair not in active:
                        contacts.append({"frame": frame_number, "timestamp_ms": first["timestamp_ms"],
                                         "track_ids": list(pair), "normalized_gap": round(normalized, 4),
                                         "confidence": round(min(first.get("confidence", 0),
                                                                 second.get("confidence", 0)), 4),
                                         "status": "contact_candidate"})
        active = current
    return contacts


def _bbox_gap(first, second):
    horizontal = max(first[0] - second[2], second[0] - first[2], 0)
    vertical = max(first[1] - second[3], second[1] - first[3], 0)
    return hypot(horizontal, vertical)


def analyze_biomechanics(video_id: str, frames: list[dict], tracks: list[dict], output_root: Path,
                         pose_estimator=None, ball_detector=None, progress=None) -> dict:
    import cv2
    pose_estimator = pose_estimator or PoseEstimator()
    ball_detector = ball_detector or FootballDetector(os.getenv("BALL_MODEL_PATH", "yolo11n.pt"))
    ball_tracker, poses = BallTracker(), []
    for index, metadata in enumerate(frames):
        image = cv2.imread(metadata["file_path"])
        if image is None:
            continue
        poses.append(pose_estimator.estimate(image, metadata["frame_number"], metadata["timestamp_ms"]))
        ball_tracker.update(ball_detector.detect_frame(
            image, metadata["frame_number"], metadata["timestamp_ms"]
        ))
        if progress:
            progress(int((index + 1) * 100 / max(len(frames), 1)))
    payload = {"video_id": video_id, "poses": poses, "ball_track": ball_tracker.export(),
               "contact_candidates": contact_geometry(tracks)}
    target = Path(output_root) / video_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "biomechanics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
