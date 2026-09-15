"""Ultralytics YOLO adapter with stable TruGrade detection JSON."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class DetectorUnavailable(RuntimeError):
    pass


class FootballDetector:
    """Lazy YOLO adapter; callers do not depend on Ultralytics result objects."""

    def __init__(self, model_path: str | None = None, confidence: float = 0.25, model: Any = None):
        self.model_path = model_path or os.getenv("YOLO_MODEL_PATH", "yolo11n.pt")
        self.confidence = confidence
        self.model = model
        self.device = os.getenv("TRUGRADE_DEVICE", "auto").strip().lower()

    def load_model(self) -> None:
        if self.model is not None:
            return
        try:
            import torch
            from ultralytics import YOLO
            if self.device == "auto":
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            if self.device.startswith("cuda") and not torch.cuda.is_available():
                raise DetectorUnavailable(f"Configured device {self.device!r} is unavailable.")
            self.model = YOLO(self.model_path)
        except Exception as exc:
            raise DetectorUnavailable(f"YOLO could not be loaded: {exc}") from exc

    @staticmethod
    def _football_class(raw_name: str) -> str | None:
        name = raw_name.lower().strip()
        if name == "person" or name == "player":
            return "player"
        if name in {"sports ball", "football", "ball"}:
            return "football"
        if name in {"official", "referee"}:
            return "official"
        return None

    def _parse(self, result: Any, frame_number: int, timestamp_ms: int) -> dict:
        names = result.names
        detections = []
        for box in result.boxes:
            class_id = int(box.cls.item())
            mapped = self._football_class(str(names[class_id]))
            if mapped is None:
                continue
            coords = [round(float(value), 2) for value in box.xyxy[0].tolist()]
            detections.append({"class": mapped, "confidence": round(float(box.conf.item()), 4), "bbox": coords})
        return {"frame": frame_number, "timestamp_ms": timestamp_ms, "detections": detections}

    def detect_frame(self, frame: Any, frame_number: int, timestamp_ms: int) -> dict:
        self.load_model()
        result = self.model.predict(frame, conf=self.confidence, device=self.device, verbose=False)[0]
        return self._parse(result, frame_number, timestamp_ms)

    def detect_batch(self, frames: list[Any], metadata: list[dict]) -> list[dict]:
        """Detect over several frames in one model call.

        A GPU spends most of a single-frame call on transfer and launch
        overhead rather than on the convolutions, so feeding one frame at a
        time leaves the hardware largely idle. Batching is the difference
        between a clip analysing in minutes and in hours.

        Falls back to per-frame prediction if the model rejects a batch, so
        an adapter that only accepts single images still works.
        """
        self.load_model()
        if not frames:
            return []
        try:
            results = self.model.predict(frames, conf=self.confidence, device=self.device, verbose=False)
        except Exception:
            results = [
                self.model.predict(frame, conf=self.confidence, device=self.device, verbose=False)[0]
                for frame in frames
            ]
        return [
            self._parse(result, meta["frame_number"], meta["timestamp_ms"])
            for result, meta in zip(results, metadata)
        ]
