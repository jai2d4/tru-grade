import json
import sys
from types import SimpleNamespace

import pytest

from backend.api.analysis import _analysis_fps
from backend.video.frame_extractor import FrameExtractor
from backend.vision.detector import DetectorUnavailable, FootballDetector


def fake_cv2(frame_count=5, fps=30):
    frames = [SimpleNamespace(shape=(720, 1280, 3)) for _ in range(frame_count)]

    class Capture:
        def __init__(self, _): self.index = 0
        def isOpened(self): return True
        def get(self, prop): return fps if prop == 1 else frame_count
        def read(self):
            if self.index == frame_count: return False, None
            frame = frames[self.index]
            self.index += 1
            return True, frame
        def release(self): pass

    return SimpleNamespace(CAP_PROP_FPS=1, CAP_PROP_FRAME_COUNT=2,
                           VideoCapture=Capture, imwrite=lambda path, frame: True)


def test_native_mode_extracts_every_source_frame(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2())
    result = FrameExtractor(tmp_path, analysis_fps=None, checkpoint_every=2).extract("game", tmp_path / "film.mp4")
    assert [frame["frame_number"] for frame in result] == [0, 1, 2, 3, 4]
    assert json.loads((tmp_path / "game" / "frames.json").read_text()) == result
    assert (tmp_path / "game" / "frames.complete").read_text() == "5"


def test_numeric_fps_remains_available_for_preview(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2(frame_count=6, fps=30))
    result = FrameExtractor(tmp_path, analysis_fps=10).extract("preview", tmp_path / "film.mp4")
    assert [frame["frame_number"] for frame in result] == [0, 3]


def test_analysis_fps_defaults_to_native(monkeypatch):
    monkeypatch.delenv("ANALYSIS_FPS", raising=False)
    assert _analysis_fps() is None
    monkeypatch.setenv("ANALYSIS_FPS", "15")
    assert _analysis_fps() == 15


def test_requested_gpu_must_exist(monkeypatch):
    monkeypatch.setenv("TRUGRADE_DEVICE", "cuda:0")
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=lambda _: object()))
    with pytest.raises(DetectorUnavailable, match="unavailable"):
        FootballDetector().load_model()
