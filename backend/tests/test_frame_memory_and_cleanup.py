"""LazyFrameStore and frame cleanup — the two fixes to the extracted-frame
disk/memory problem.

The memory one matters most: the previous identification path decoded
every referenced frame into a dict before starting OCR, which at 1080p is
~6 MB per frame resident. These tests pin the bounded behaviour so a
future change can't quietly reintroduce it.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from backend.video.frame_extractor import FrameExtractor  # noqa: E402
from backend.vision.frame_source import LazyFrameStore  # noqa: E402


def _write_frames(directory, count: int, size=(64, 48)) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    manifest = []
    for n in range(count):
        path = directory / f"frame-{n:09d}.jpg"
        image = np.full((size[1], size[0], 3), (n * 7) % 255, dtype=np.uint8)
        cv2.imwrite(str(path), image)
        manifest.append({"frame_number": n, "file_path": str(path),
                         "timestamp_ms": n * 33, "width": size[0], "height": size[1]})
    return manifest


def test_lazy_store_returns_the_right_frame(tmp_path):
    manifest = _write_frames(tmp_path / "frames", 5)
    store = LazyFrameStore(manifest)
    image = store.get(3)
    assert image is not None
    assert image.shape == (48, 64, 3)
    # Value round-trips through JPEG, so compare approximately.
    assert abs(int(image[0][0][0]) - (3 * 7) % 255) <= 4


def test_lazy_store_holds_only_a_bounded_number_of_decoded_frames(tmp_path):
    """The whole point: reading 100 frames must not retain 100 frames."""
    manifest = _write_frames(tmp_path / "frames", 100)
    store = LazyFrameStore(manifest, cache_size=8)
    for n in range(100):
        assert store.get(n) is not None
    assert len(store._cache) <= 8
    assert len(store) == 100, "all frames remain *available*, just not resident"


def test_lazy_store_returns_default_for_missing_or_unreadable_frames(tmp_path):
    manifest = _write_frames(tmp_path / "frames", 2)
    manifest.append({"frame_number": 99, "file_path": str(tmp_path / "frames" / "gone.jpg")})
    store = LazyFrameStore(manifest)
    assert store.get(99) is None      # path in the manifest, no file on disk
    assert store.get(12345) is None   # not in the manifest at all
    assert store.get(12345, "fallback") == "fallback"


def test_lazy_store_satisfies_the_contract_identify_player_relies_on(tmp_path):
    """identify_player only ever calls .get(frame_number) — if that stops
    being true this test should fail loudly rather than the pipeline
    silently finding no frames."""
    manifest = _write_frames(tmp_path / "frames", 3)
    store = LazyFrameStore(manifest)
    assert callable(store.get)
    assert store.get(0) is not None
    assert 0 in store and 77 not in store


def test_discard_frames_frees_disk_and_removes_the_resume_marker(tmp_path):
    frames_root = tmp_path / "frames"
    video_id = "vid-1"
    manifest = _write_frames(frames_root / video_id, 10)
    (frames_root / video_id / "frames.json").write_text(json.dumps(manifest), encoding="utf-8")
    (frames_root / video_id / "frames.complete").write_text("10", encoding="utf-8")

    extractor = FrameExtractor(frames_root)
    freed = extractor.discard_frames(video_id)

    assert freed > 0
    assert not (frames_root / video_id).exists()
    # The marker must go too: leaving it would tell the resume path that
    # extraction is complete while handing downstream stages dead paths.
    assert not (frames_root / video_id / "frames.complete").exists()


def test_discard_frames_is_safe_to_call_when_there_is_nothing_to_discard(tmp_path):
    assert FrameExtractor(tmp_path / "frames").discard_frames("never-existed") == 0


def test_extractor_writes_smaller_frames_than_opencv_defaults(tmp_path):
    """Quality 95 (cv2's default) is what made native-rate extraction run to
    tens of GB. Prove the override actually takes effect."""
    image = np.random.default_rng(0).integers(0, 255, (480, 640, 3), dtype=np.uint8)
    default_path = tmp_path / "default.jpg"
    tuned_path = tmp_path / "tuned.jpg"
    cv2.imwrite(str(default_path), image)
    cv2.imwrite(str(tuned_path), image, [int(cv2.IMWRITE_JPEG_QUALITY), FrameExtractor(tmp_path).jpeg_quality])

    assert tuned_path.stat().st_size < default_path.stat().st_size


def test_jpeg_quality_is_configurable_and_clamped(tmp_path, monkeypatch):
    monkeypatch.setenv("FRAME_JPEG_QUALITY", "55")
    assert FrameExtractor(tmp_path).jpeg_quality == 55
    assert FrameExtractor(tmp_path, jpeg_quality=999).jpeg_quality == 100
    assert FrameExtractor(tmp_path, jpeg_quality=0).jpeg_quality == 1
