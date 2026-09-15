"""Frame-manifest to detection/track JSON pipeline."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from .detector import FootballDetector
from .tracker import ByteTrackTracker
from backend.football.movement import movement_metrics


def analyze_frames(video_id: str, frames: list[dict], output_root: Path,
                   progress: Callable[[int], None] | None = None) -> tuple[list[dict], list[dict]]:
    import cv2

    detector, tracker = FootballDetector(), ByteTrackTracker()
    detections = []
    total = max(len(frames), 1)

    # Frames go to the model in batches: a GPU spends most of a
    # single-frame call on transfer and launch overhead rather than on the
    # actual convolutions, so one-at-a-time leaves the hardware mostly
    # idle. Tracking still consumes the results strictly in frame order —
    # ByteTrack's association depends on it — so only the detection call is
    # batched, not the tracking.
    batch_size = max(1, int(os.getenv("DETECT_BATCH_SIZE", "16")))
    done = 0
    for start in range(0, len(frames), batch_size):
        window = frames[start:start + batch_size]
        images, metadata = [], []
        for item in window:
            image = cv2.imread(item["file_path"])
            if image is None:
                continue
            images.append(image)
            metadata.append(item)

        # A detector adapter is only required to implement detect_frame;
        # batching is an optimisation, not part of the contract.
        if hasattr(detector, "detect_batch"):
            results = detector.detect_batch(images, metadata)
        else:
            results = [
                detector.detect_frame(image, meta["frame_number"], meta["timestamp_ms"])
                for image, meta in zip(images, metadata)
            ]

        for result in results:
            detections.append(result)
            tracker.update(result)

        done += len(window)
        if progress:
            progress(int(done * 100 / total))
    tracks = tracker.export_tracks()
    for track in tracks:
        track["movement"] = movement_metrics(track["positions"])
    target = Path(output_root) / video_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "detections.json").write_text(json.dumps(detections, indent=2), encoding="utf-8")
    (target / "tracks.json").write_text(json.dumps(tracks, indent=2), encoding="utf-8")
    return detections, tracks
