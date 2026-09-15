"""OpenCV frame extraction retaining original frame numbers and timestamps."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Callable


class FrameExtractionError(RuntimeError):
    pass


# cv2's default JPEG quality is 95, which is near-lossless and enormous:
# a 1080p frame lands around 1.3 MB, so native-rate extraction of a single
# clip runs to tens of GB. Detection, tracking and OCR read these frames
# as model input, not as anything a person looks at, and gain nothing from
# quality 95. Override via FRAME_JPEG_QUALITY if a specific model ever
# proves otherwise.
DEFAULT_JPEG_QUALITY = 80


class FrameExtractor:
    def __init__(self, frames_root: Path, analysis_fps: float | None = None, checkpoint_every: int = 250,
                 jpeg_quality: int | None = None):
        if analysis_fps is not None and analysis_fps <= 0:
            raise ValueError("analysis_fps must be positive")
        self.frames_root = Path(frames_root)
        self.analysis_fps = analysis_fps
        self.checkpoint_every = max(1, checkpoint_every)
        if jpeg_quality is None:
            jpeg_quality = int(os.getenv("FRAME_JPEG_QUALITY", str(DEFAULT_JPEG_QUALITY)))
        self.jpeg_quality = max(1, min(100, jpeg_quality))

    def extract(self, video_id: str, video_path: Path, progress: Callable[[int], None] | None = None) -> list[dict]:
        import cv2

        output_dir = self.frames_root / video_id
        output_dir.mkdir(parents=True, exist_ok=True)
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise FrameExtractionError("OpenCV could not open the uploaded video.")
        source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if source_fps <= 0:
            capture.release()
            raise FrameExtractionError("Video frame rate could not be determined.")
        # None means native FPS: every source frame is retained for analysis.
        interval = max(source_fps / self.analysis_fps, 1.0) if self.analysis_fps else 1.0
        next_sample = 0.0
        frame_number = 0
        frames: list[dict] = []
        manifest = output_dir / "frames.json"
        complete_marker = output_dir / "frames.complete"
        complete_marker.unlink(missing_ok=True)
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if frame_number + 1e-9 >= next_sample:
                    height, width = frame.shape[:2]
                    file_path = output_dir / f"frame-{frame_number:09d}.jpg"
                    if not cv2.imwrite(str(file_path), frame,
                                       [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]):
                        raise FrameExtractionError(f"Could not write frame {frame_number}.")
                    frames.append({
                        "frame_number": frame_number,
                        "timestamp_ms": round(frame_number * 1000 / source_fps),
                        "video_id": video_id, "width": width, "height": height,
                        "file_path": str(file_path),
                    })
                    if len(frames) % self.checkpoint_every == 0:
                        manifest.write_text(json.dumps(frames, indent=2), encoding="utf-8")
                    next_sample += interval
                frame_number += 1
                if progress and total_frames:
                    progress(min(99, int(frame_number * 100 / total_frames)))
        finally:
            capture.release()
        manifest.write_text(json.dumps(frames, indent=2), encoding="utf-8")
        complete_marker.write_text(str(len(frames)), encoding="utf-8")
        if progress:
            progress(100)
        return frames

    def keyframe_path(self, video_id: str) -> Path:
        """Where the one preserved sample frame lives.

        Field calibration only ever needs a single representative frame,
        but it used to read one out of the full extracted set — which made
        deleting that set break calibration. Keeping one small JPEG makes
        the cleanup safe instead of mutually exclusive with it.
        """
        return self.frames_root.parent / "keyframes" / f"{video_id}.jpg"

    def preserve_keyframe(self, video_id: str, manifest: list[dict]) -> Path | None:
        """Copy the middle frame somewhere that survives discard_frames().
        Middle rather than first: the opening frames of game film are often
        a title card, a sideline pan, or an empty field."""
        if not manifest:
            return None
        sample = manifest[len(manifest) // 2]
        source = Path(sample["file_path"])
        if not source.is_file():
            return None
        target = self.keyframe_path(video_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return target

    def discard_frames(self, video_id: str) -> int:
        """Delete the extracted JPEGs for a video, returning how many bytes
        were freed.

        Nothing used to clean these up, so every analyzed video left its
        frames on disk forever — at native frame rate that is GB per clip.
        They are an intermediate artifact: once detection, tracking and
        identification have run, the evidence that matters lives in
        tracks.json / detections.json / biomechanics.json.

        The manifest and its completion marker are removed alongside the
        images on purpose. Leaving them would make the resume path believe
        extraction is still complete and hand downstream stages a list of
        files that no longer exist; deleting them means a re-run simply
        extracts again.
        """
        directory = self.frames_root / video_id
        if not directory.is_dir():
            return 0
        freed = sum(f.stat().st_size for f in directory.glob("*") if f.is_file())
        shutil.rmtree(directory, ignore_errors=True)
        return freed
