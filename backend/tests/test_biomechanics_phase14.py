from types import SimpleNamespace

from backend.vision.biomechanics import BallTracker, PoseEstimator, body_orientation, contact_geometry


class Values:
    def __init__(self, value): self.value = value
    def tolist(self): return self.value


def test_pose_adapter_exports_keypoints_and_body_orientation():
    points = [[0, 0] for _ in range(17)]
    points[5], points[6], points[11], points[12] = [4, 2], [6, 2], [4, 8], [6, 8]
    result = SimpleNamespace(
        keypoints=SimpleNamespace(xy=Values([points]), conf=Values([[.9] * 17])),
        boxes=SimpleNamespace(xyxy=Values([[0, 0, 10, 20]])),
    )
    model = SimpleNamespace(predict=lambda *args, **kwargs: [result])
    payload = PoseEstimator(model=model).estimate(object(), 10, 500)
    assert payload["poses"][0]["orientation_deg"] == -90
    assert len(payload["poses"][0]["keypoints"]) == 17


def test_body_orientation_is_unknown_without_required_landmarks():
    assert body_orientation([{"index": 5, "x": 1, "y": 1}]) is None


def test_ball_tracker_rejects_impossible_jump():
    tracker = BallTracker(max_jump_px=20)
    tracker.update({"frame": 1, "timestamp_ms": 0, "detections": [
        {"class": "football", "confidence": .9, "bbox": [0, 0, 4, 4]}]})
    result = tracker.update({"frame": 2, "timestamp_ms": 100, "detections": [
        {"class": "football", "confidence": .9, "bbox": [100, 100, 104, 104]}]})
    assert result is None
    assert len(tracker.export()["positions"]) == 1


def test_contact_geometry_emits_candidate_not_claimed_tackle():
    tracks = [
        {"track_id": 1, "positions": [{"frame": 1, "timestamp_ms": 100, "bbox": [0, 0, 20, 40], "confidence": .9}]},
        {"track_id": 2, "positions": [{"frame": 1, "timestamp_ms": 100, "bbox": [18, 0, 38, 40], "confidence": .8}]},
    ]
    events = contact_geometry(tracks)
    assert events[0]["track_ids"] == [1, 2]
    assert events[0]["status"] == "contact_candidate"
    assert "tackle" not in events[0]
