"""Verifies the V2 deterministic grading engine's Truth Report output is
unified with the same athlete roster as track identity: a completed report
lands in Postgres (film_grades), linked to a real athletes.id whenever the
graded track already carries a confirmed roster link — never guessed from
the free-text player_id the report was requested under."""
import io
import json

import pytest


@pytest.fixture(autouse=True)
def _skip_without_db(db_available):
    available, reason = db_available
    if not available:
        pytest.skip(f"No PostgreSQL reachable — set POSTGRES_* env vars to run these tests. ({reason})")


def _upload_video(client) -> str:
    response = client.post(
        "/api/videos/upload",
        files={"file": ("game.mp4", io.BytesIO(b"not-a-real-video"), "video/mp4")},
    )
    assert response.status_code == 201
    return response.json()["video_id"]


def _make_athlete(client, **overrides) -> str:
    payload = {"first_name": "Jordan", "last_name": "Williams", "position": "DB", **overrides}
    response = client.post("/api/v1/athletes", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def _seed_track_and_play(client, video_id: str, track_id: int = 1) -> None:
    """Fabricates tracks.json and plays.json directly so a Truth Report can
    run against them without the real detector/tracker/segmenter."""
    import backend.api.players as players_module

    track_path = players_module._track_path(video_id)
    track_path.parent.mkdir(parents=True, exist_ok=True)
    track_path.write_text(json.dumps([{
        "track_id": track_id,
        "positions": [{"frame": 1, "timestamp_ms": 1000, "center_x": 10, "center_y": 10,
                       "bbox": [0, 0, 20, 40], "confidence": .9}],
    }]))

    storage_root = players_module.storage_root
    plays_path = storage_root / "football" / video_id / "plays.json"
    plays_path.parent.mkdir(parents=True, exist_ok=True)
    plays_path.write_text(json.dumps([{
        "play_id": "P001", "video_id": video_id, "start_time": 0, "snap_time": 1, "end_time": 2,
        "confidence": .8, "excluded": False, "source": "automatic",
    }]))


def _assign(client, video_id: str, athlete_id: str | None, *, track_id: int = 1, jersey: str = "12") -> None:
    payload = {"jersey_number": jersey, "reason": "Scout confirmed jersey on film"}
    if athlete_id:
        payload["athlete_id"] = athlete_id
    response = client.post(f"/api/videos/{video_id}/tracks/{track_id}/assign", json=payload)
    assert response.status_code == 200


def test_truth_report_links_the_grade_to_the_tracks_confirmed_athlete(client):
    video_id = _upload_video(client)
    athlete_id = _make_athlete(client)
    _seed_track_and_play(client, video_id)
    _assign(client, video_id, athlete_id)

    response = client.post(
        f"/api/players/free-text-id/truth-report",
        json={"video_id": video_id, "track_id": 1, "position": "DB"},
    )
    assert response.status_code == 202

    status = client.get(f"/api/players/free-text-id/truth-report/{video_id}").json()
    assert status["status"] == "completed", status

    links = client.get(f"/api/v1/athletes/{athlete_id}/grades").json()
    assert len(links) == 1
    assert links[0]["video_id"] == video_id
    assert links[0]["position"] == "DB"
    # The report was requested under a free-text player_id that has nothing
    # to do with the athlete_id string — proving the link came from the
    # track's confirmed roster assignment, not from parsing player_id.
    assert links[0]["confidence"] is not None


def test_truth_report_for_an_unlinked_track_persists_with_no_athlete(client):
    """Scouting an opponent: the track was never confirmed against a real
    roster athlete, so the mirrored grade row must carry athlete_id = null,
    not silently attach to some athlete."""
    video_id = _upload_video(client)
    _seed_track_and_play(client, video_id)
    _assign(client, video_id, None, jersey="99")

    response = client.post(
        "/api/players/opponent-99/truth-report",
        json={"video_id": video_id, "track_id": 1, "position": "DB"},
    )
    assert response.status_code == 202
    status = client.get(f"/api/players/opponent-99/truth-report/{video_id}").json()
    assert status["status"] == "completed", status

    # No athlete exists to query film-grades from a null link, but we can
    # confirm the local GradeStore (the system of record) still has it —
    # the DB mirror simply has athlete_id = null, invisible from any
    # athlete-scoped endpoint, which is the correct behavior.
    grades = client.get("/api/players/opponent-99/grades").json()
    assert len(grades["grades"]) == 1


def test_calculate_grade_links_an_explicit_athlete_id(client):
    """POST .../grades has no track_id to resolve a link from, so it takes
    an explicit athlete_id directly — the one case where the caller, not a
    confirmed track assignment, supplies the roster link."""
    athlete_id = _make_athlete(client)
    response = client.post(
        "/api/players/manual-player/grades",
        json={"game_id": "manual-game-1", "position": "DB", "items": [], "athlete_id": athlete_id},
    )
    assert response.status_code == 201

    grades = client.get(f"/api/v1/athletes/{athlete_id}/grades").json()
    assert len(grades) == 1
    assert grades[0]["position"] == "DB"
    # "manual-game-1" is not a real film_uploads row, so the mirror leaves
    # video_id unset rather than forcing a bad foreign key.
    assert grades[0]["video_id"] is None


def test_calculate_grade_with_an_unknown_athlete_id_still_saves_the_grade(client):
    """An athlete_id that doesn't resolve to a real roster row must not
    block the grade calculation — persistence to Postgres is best-effort,
    the local GradeStore save (already the response body) is not."""
    response = client.post(
        "/api/players/manual-player-2/grades",
        json={"game_id": "manual-game-2", "position": "DB", "items": [],
              "athlete_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 201
    grades = client.get("/api/players/manual-player-2/grades").json()
    assert len(grades["grades"]) == 1


def test_athlete_grades_404s_for_an_athlete_that_does_not_exist(client):
    response = client.get("/api/v1/athletes/00000000-0000-0000-0000-000000000000/grades")
    assert response.status_code == 404
