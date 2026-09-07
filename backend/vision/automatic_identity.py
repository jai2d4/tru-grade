"""Multi-frame team-color and jersey-number identification."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Protocol

import numpy as np


NAMED_RGB = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (200, 35, 45),
    "blue": (35, 80, 190), "navy": (20, 35, 85), "green": (30, 140, 70),
    "yellow": (235, 205, 45), "gold": (205, 160, 35), "orange": (230, 100, 30),
    "purple": (105, 55, 150), "maroon": (110, 30, 45), "gray": (130, 130, 130),
    "grey": (130, 130, 130),
}


class JerseyReader(Protocol):
    def read(self, crop: np.ndarray) -> list[tuple[str, float]]: ...


class EasyOCRJerseyReader:
    """Lazy local OCR constrained to one- or two-digit football numbers."""

    def __init__(self, gpu: bool | str = "auto"):
        self.gpu = gpu
        self._reader = None

    def _load(self):
        if self._reader is None:
            import torch
            import easyocr
            use_gpu = torch.cuda.is_available() if self.gpu == "auto" else self.gpu
            self._reader = easyocr.Reader(["en"], gpu=use_gpu)

    def read(self, crop: np.ndarray) -> list[tuple[str, float]]:
        self._load()
        output = []
        for _, text, confidence in self._reader.readtext(
            crop, allowlist="0123456789", detail=1, paragraph=False
        ):
            digits = "".join(re.findall(r"\d", text))
            if 1 <= len(digits) <= 2 and 0 <= int(digits) <= 99:
                output.append((digits, float(confidence)))
        return output


def parse_school_colors(value: str) -> list[tuple[int, int, int]]:
    colors = []
    for token in re.split(r"[,/;|]+|\band\b", value.lower()):
        token = token.strip()
        if token in NAMED_RGB:
            colors.append(NAMED_RGB[token])
        elif re.fullmatch(r"#[0-9a-f]{6}", token):
            colors.append(tuple(int(token[i:i + 2], 16) for i in (1, 3, 5)))
    return colors


def color_match_score(crop_bgr: np.ndarray, colors_rgb: list[tuple[int, int, int]]) -> float:
    if crop_bgr.size == 0 or not colors_rgb:
        return 0.5
    pixels = crop_bgr.reshape(-1, 3)[:, ::-1].astype(np.float32)
    # Ignore very dark shadow pixels; black remains matchable when explicitly supplied.
    scores = []
    for color in colors_rgb:
        distance = np.linalg.norm(pixels - np.asarray(color, dtype=np.float32), axis=1)
        scores.append(float(np.mean(distance <= 75)))
    return min(1.0, sum(sorted(scores, reverse=True)[:2]) * 2.5)


def jersey_crop(frame: np.ndarray, bbox: list[float]) -> np.ndarray:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    # Central upper torso avoids helmet, legs, and most nearby players.
    left = max(0, int(x1 + (x2 - x1) * .12))
    right = min(width, int(x2 - (x2 - x1) * .12))
    top = max(0, int(y1 + (y2 - y1) * .12))
    bottom = min(height, int(y1 + (y2 - y1) * .68))
    return frame[top:bottom, left:right]


def identify_player(
    target_number: str,
    school_colors: str,
    tracks: list[dict],
    frames_by_number: dict[int, np.ndarray],
    reader: JerseyReader,
    min_reads: int = 2,
    threshold: float = .62,
    margin: float = .12,
) -> dict:
    target_number = str(int(target_number))
    palette = parse_school_colors(school_colors)
    results = []
    for track in tracks:
        votes: dict[str, float] = defaultdict(float)
        reads: dict[str, int] = defaultdict(int)
        evidence = []
        considered = 0
        for point in track.get("positions", []):
            frame = frames_by_number.get(point["frame"])
            if frame is None:
                continue
            considered += 1
            crop = jersey_crop(frame, point["bbox"])
            team_score = color_match_score(crop, palette)
            for number, ocr_confidence in reader.read(crop):
                number = str(int(number))
                weight = ocr_confidence * (.35 + .65 * team_score) * point.get("confidence", 1)
                votes[number] += weight
                reads[number] += 1
                evidence.append({"frame": point["frame"], "timestamp_ms": point["timestamp_ms"],
                                 "number": number, "ocr_confidence": round(ocr_confidence, 4),
                                 "team_color_score": round(team_score, 4)})
        total = sum(votes.values())
        target_weight = votes.get(target_number, 0)
        confidence = target_weight / total if total else 0
        results.append({"track_id": track["track_id"], "target_number": target_number,
                        "confidence": round(confidence, 4), "matching_reads": reads.get(target_number, 0),
                        "frames_considered": considered, "candidates": dict(votes), "evidence": evidence})
    ranked = sorted(results, key=lambda item: (item["confidence"], item["matching_reads"]), reverse=True)
    best = ranked[0] if ranked else None
    runner_up = ranked[1]["confidence"] if len(ranked) > 1 else 0
    automatic = bool(best and best["matching_reads"] >= min_reads
                     and best["confidence"] >= threshold and best["confidence"] - runner_up >= margin)
    return {"target_number": target_number, "school_colors": school_colors,
            "status": "identified" if automatic else "confirmation_required",
            "selected_track_id": best["track_id"] if automatic else None,
            "confidence": best["confidence"] if best else 0, "tracks": ranked}


def load_track_frames(track: dict, manifest: list[dict]) -> dict[int, np.ndarray]:
    import cv2
    wanted = set(track.get("frames", []))
    return {item["frame_number"]: image for item in manifest
            if item["frame_number"] in wanted and (image := cv2.imread(str(Path(item["file_path"])))) is not None}
