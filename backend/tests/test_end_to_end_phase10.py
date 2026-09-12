"""Phase 10: prove the complete film-to-report contract without external services."""
import asyncio
import json
import sys
from io import BytesIO
from types import SimpleNamespace

from fastapi import UploadFile

from backend.ai.football_reasoner import FootballReasoner
from backend.ai.provider import AIProvider
from backend.football.evidence import EvidenceStore
from backend.football.observations import FootballObservation, ObservationDatum
from backend.football.play_segmenter import PlaySegmenter
from backend.grading.models import Evidence
from backend.grading.service import GradeStore, calculate_official_grade
from backend.video.frame_extractor import FrameExtractor
from backend.video.ingestion import VideoStore
from backend.vision.jersey_identifier import TrackIdentity, confirm_identity
from backend.vision.pipeline import analyze_frames


class EvidenceOnlyProvider(AIProvider):
    """Deterministic provider fixture; it reasons but never supplies a final grade."""

    async def generate_json(self, prompt, schema):
        assert "official TruGrade score" in prompt
        assert "grade" not in schema.get("properties", {})
        return {"observations": [{
            "trait": "read_react",
            "value": "positive_execution",
            "confidence": .8,
            "evidence_timestamp": 0.1,
            "reason": "Player reacts downhill after the snap.",
        }]}


def test_upload_to_evidence_backed_truth_report(monkeypatch, tmp_path):
    # Upload film.
    store = VideoStore(tmp_path / "storage")
    uploaded = asyncio.run(store.save(
        UploadFile(filename="game-film.mp4", file=BytesIO(b"test-football-film"))
    ))
    video_id = uploaded["video_id"]

    # Extract timestamped frames without requiring a real codec in CI.
    frames = [SimpleNamespace(shape=(720, 1280, 3)) for _ in range(3)]

    class Capture:
        def __init__(self, _): self.index = 0
        def isOpened(self): return True
        def get(self, prop): return 10 if prop == 1 else len(frames)
        def read(self):
            if self.index == len(frames): return False, None
            frame = frames[self.index]
            self.index += 1
            return True, frame
        def release(self): pass

    fake_cv2 = SimpleNamespace(
        CAP_PROP_FPS=1,
        CAP_PROP_FRAME_COUNT=2,
        VideoCapture=Capture,
        imwrite=lambda path, frame: True,
        imread=lambda path: object(),
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    manifest = FrameExtractor(tmp_path / "frames", analysis_fps=10).extract(
        video_id, uploaded["file_path"]
    )

    # Detect and track one player with stable identity.
    class Detector:
        def detect_frame(self, image, frame, timestamp_ms):
            x = frame * 2
            return {"frame": frame, "timestamp_ms": timestamp_ms, "detections": [{
                "class": "player", "confidence": .9, "bbox": [x, 0, x + 20, 20],
            }]}

    monkeypatch.setattr("backend.vision.pipeline.FootballDetector", Detector)
    detections, tracks = analyze_frames(video_id, manifest, tmp_path / "vision")
    assert len(detections) == 3
    assert len(tracks) == 1

    # Segment plays and require a human-confirmed player assignment.
    plays = PlaySegmenter().segment(video_id, tracks)
    identity, audit = confirm_identity(
        TrackIdentity(track_id=tracks[0]["track_id"], confidence=0),
        player_id="player-12",
        jersey_number="12",
        team="red",
        position="LB",
        reason="Scout confirmed jersey 12.",
    )
    assert identity.confirmed and audit["source"] == "human"

    # Create an evidence-linked observation, then let AI reason about the trait.
    play = plays[0]
    evidence = Evidence(
        video_id=video_id,
        play_id=play.play_id,
        timestamp_start=play.snap_time,
        timestamp_end=play.end_time,
        frame_ids=tracks[0]["frames"],
        track_id=tracks[0]["track_id"],
        player_id=identity.player_id,
        description="Jersey 12 reads the play and attacks downhill.",
    )
    observation = FootballObservation(
        observation_id="OBS-1",
        play_id=play.play_id,
        player_id=identity.player_id,
        position=identity.position,
        movement={"reaction": ObservationDatum(
            value="downhill",
            confidence=.8,
            evidence_timestamp=play.snap_time,
            reason="Tracked movement begins after the snap.",
        )},
        evidence=[evidence],
    )
    reasoning = asyncio.run(FootballReasoner(EvidenceOnlyProvider()).reason(observation))

    # Only the deterministic TruGrade engine calculates the official grade.
    grade, events = calculate_official_grade(identity.position, [(observation, reasoning)])
    assert grade.grade == 53
    assert grade.confidence == .8
    assert events[0].evidence == evidence

    # Persist evidence and the final Truth Report payload.
    evidence_store = EvidenceStore(tmp_path / "evidence")
    evidence_store.save(evidence)
    report = GradeStore(tmp_path / "grades").save(identity.player_id, video_id, grade, events)
    assert report["game_grade"] == 53
    assert report["confidence"] == .8
    assert report["events"][0]["evidence"]["play_id"] == play.play_id
    assert json.loads((tmp_path / "grades" / "player-12.json").read_text())[0] == report
    assert evidence_store.for_player("player-12")[0]["video_id"] == video_id
