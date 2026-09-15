"""Bounded-memory access to extracted frames.

`identify_player` (backend/vision/automatic_identity.py) asks for frames
through a mapping's `.get(frame_number)`. The original caller satisfied
that by decoding **every** referenced frame into a dict up front — at
1080p a decoded frame is roughly 6 MB of RAM, so a track set referencing a
few thousand frames meant multiple GB resident before OCR even started.

This provides the same `.get()` contract while holding at most
`cache_size` decoded frames at a time: paths are cheap to keep, pixels are
not. Nothing about the identification algorithm changes — it just stops
requiring the whole video in memory to run.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any


class LazyFrameStore:
    """Maps frame number -> decoded image, loading on demand.

    Not a dict subclass on purpose: only `.get()` is part of the contract
    the vision code relies on, and pretending to be a full mapping would
    invite callers to iterate it — which is exactly the whole-video-in-RAM
    behaviour this exists to prevent.
    """

    def __init__(self, manifest: list[dict], cache_size: int = 8):
        # Paths only — no pixels are read until .get() asks for one.
        self._paths: dict[int, str] = {
            int(item["frame_number"]): item["file_path"]
            for item in manifest
            if item.get("file_path") is not None
        }
        self._cache: OrderedDict[int, Any] = OrderedDict()
        self._cache_size = max(1, cache_size)

    def __contains__(self, frame_number: int) -> bool:
        return int(frame_number) in self._paths

    def __len__(self) -> int:
        """How many frames are available, not how many are resident."""
        return len(self._paths)

    def get(self, frame_number: int, default: Any = None) -> Any:
        key = int(frame_number)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)  # keep the LRU ordering honest
            return cached

        path = self._paths.get(key)
        if path is None or not Path(path).is_file():
            return default

        import cv2  # local: keeps this module importable without OpenCV

        image = cv2.imread(path)
        if image is None:
            return default

        self._cache[key] = image
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)  # evict least-recently-used
        return image
