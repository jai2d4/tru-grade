from types import SimpleNamespace

from backend.vision.detector import FootballDetector
from backend.vision.tracker import ByteTrackTracker


class Scalar:
    def __init__(self, value): self.value = value
    def item(self): return self.value


class Coordinates:
    def __init__(self, values): self.values = values
    def __getitem__(self, _): return self
    def tolist(self): return self.values


def test_detector_returns_stable_football_json():
    boxes = [
        SimpleNamespace(cls=Scalar(0), conf=Scalar(.91), xyxy=Coordinates([1, 2, 11, 22])),
        SimpleNamespace(cls=Scalar(32), conf=Scalar(.73), xyxy=Coordinates([20, 30, 25, 35])),
        SimpleNamespace(cls=Scalar(2), conf=Scalar(.99), xyxy=Coordinates([0, 0, 5, 5])),
    ]
    result = SimpleNamespace(names={0: "person", 32: "sports ball", 2: "car"}, boxes=boxes)
    model = SimpleNamespace(predict=lambda *args, **kwargs: [result])
    detection = FootballDetector(model=model).detect_frame(object(), 123, 4100)
    assert detection == {"frame": 123, "timestamp_ms": 4100, "detections": [
        {"class": "player", "confidence": .91, "bbox": [1.0, 2.0, 11.0, 22.0]},
        {"class": "football", "confidence": .73, "bbox": [20.0, 30.0, 25.0, 35.0]},
    ]}


def test_tracker_persists_id_and_exports_required_motion_fields():
    tracker = ByteTrackTracker(match_iou=.2)
    first = tracker.update({"frame": 1, "timestamp_ms": 100, "detections": [
        {"class": "player", "confidence": .9, "bbox": [0, 0, 20, 20]}
    ]})
    second = tracker.update({"frame": 2, "timestamp_ms": 200, "detections": [
        {"class": "player", "confidence": .8, "bbox": [2, 0, 22, 20]}
    ]})
    assert first[0]["track_id"] == second[0]["track_id"] == 1
    assert second[0]["center_x"] == 12
    assert second[0]["velocity_x"] == 20
    exported = tracker.export_tracks()[0]
    assert exported["frames"] == [1, 2]
    assert exported["start_time"] == 100
    assert exported["end_time"] == 200


def test_tracker_does_not_assume_detection_order_is_identity():
    tracker = ByteTrackTracker(match_iou=.2)
    tracker.update({"frame": 1, "timestamp_ms": 0, "detections": [
        {"class": "player", "confidence": .9, "bbox": [0, 0, 10, 10]},
        {"class": "player", "confidence": .9, "bbox": [100, 0, 110, 10]},
    ]})
    reordered = tracker.update({"frame": 2, "timestamp_ms": 100, "detections": [
        {"class": "player", "confidence": .9, "bbox": [101, 0, 111, 10]},
        {"class": "player", "confidence": .9, "bbox": [1, 0, 11, 10]},
    ]})
    assert [item["track_id"] for item in reordered] == [2, 1]



# ---------- batching ----------


def test_detection_batches_frames_instead_of_one_call_each(monkeypatch, tmp_path):
    """One model call per frame leaves a GPU mostly idle on transfer and
    launch overhead. This pins that frames actually arrive in batches."""
    import sys
    from types import SimpleNamespace

    import numpy as np

    batch_sizes = []

    class FakeResult:
        names = {0: "person"}
        boxes = []

    class FakeModel:
        def predict(self, source, **kwargs):
            frames = source if isinstance(source, list) else [source]
            batch_sizes.append(len(frames))
            return [FakeResult() for _ in frames]

    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace(
        imread=lambda path: np.zeros((8, 8, 3), dtype=np.uint8)))
    monkeypatch.setenv("DETECT_BATCH_SIZE", "4")

    from backend.vision import pipeline
    from backend.vision.detector import FootballDetector

    detector = FootballDetector(model=FakeModel())
    monkeypatch.setattr(pipeline, "FootballDetector", lambda *a, **k: detector)

    frames = [{"file_path": f"/frame-{n}.jpg", "frame_number": n, "timestamp_ms": n * 33}
              for n in range(10)]
    pipeline.analyze_frames("vid", frames, tmp_path)

    assert batch_sizes, "the model was never called"
    assert max(batch_sizes) > 1, f"frames were still sent one at a time: {batch_sizes}"
    assert sum(batch_sizes) == 10, "every frame must still be detected exactly once"


def test_a_detector_without_batching_still_works(monkeypatch, tmp_path):
    """detect_batch is an optimisation, not part of the adapter contract —
    a custom detector implementing only detect_frame must keep working."""
    import sys
    from types import SimpleNamespace

    import numpy as np

    seen = []

    class FrameOnlyDetector:
        def detect_frame(self, frame, frame_number, timestamp_ms):
            seen.append(frame_number)
            return {"frame": frame_number, "timestamp_ms": timestamp_ms, "detections": []}

    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace(
        imread=lambda path: np.zeros((8, 8, 3), dtype=np.uint8)))

    from backend.vision import pipeline
    monkeypatch.setattr(pipeline, "FootballDetector", lambda *a, **k: FrameOnlyDetector())

    frames = [{"file_path": f"/f-{n}.jpg", "frame_number": n, "timestamp_ms": n * 33}
              for n in range(5)]
    pipeline.analyze_frames("vid", frames, tmp_path)

    assert seen == [0, 1, 2, 3, 4], "frames must still be processed, and in order"
