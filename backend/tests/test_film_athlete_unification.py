"""Verifies the V2 film pipeline (backend/api/videos.py, players.py) and
the athlete roster (app/routers/athletes.py) are genuinely one data model:
a video and a confirmed track identity both land in Postgres, linked by a
real athletes.id — not a parallel, disconnected store."""
import io

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


def _seed_track(client, video_id: str, track_id: int = 1) -> None:
    """Fabricates a tracks.json so /assign has a track to work with,
    without running the real YOLO detector."""
    import json
    import backend.api.players as players_module
    path = players_module._track_path(video_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([{"track_id": track_id, "frames": [0, 1], "positions": []}]))


def test_track_assignment_links_a_real_athlete(client):
    video_id = _upload_video(client)
    athlete_id = _make_athlete(client)
    _seed_track(client, video_id)

    # film_track_assignments.video_id is a real foreign key to
    # film_uploads.id — if /api/videos/upload only wrote local metadata (the
    # pre-unification behavior), this insert would fail its FK constraint
    # with a 500, not return 200. A clean 200 here is itself proof the
    # video row is real, not just this assignment's own athlete_id.
    response = client.post(
        f"/api/videos/{video_id}/tracks/1/assign",
        json={"athlete_id": athlete_id, "jersey_number": "12", "team": "Red",
              "position": "DB", "reason": "Scout confirmed jersey on film"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["athlete_id"] == athlete_id
    assert body["confirmed"] is True

    # Read it back on a separate request — proves it's persisted, not just
    # echoed from the write.
    tracks = client.get(f"/api/videos/{video_id}/tracks").json()
    assert tracks["assignments"]["1"]["athlete_id"] == athlete_id


def test_track_assignment_rejects_an_athlete_not_on_the_roster(client):
    video_id = _upload_video(client)
    _seed_track(client, video_id)

    response = client.post(
        f"/api/videos/{video_id}/tracks/1/assign",
        json={"athlete_id": "00000000-0000-0000-0000-000000000000", "jersey_number": "12", "reason": "test"},
    )
    assert response.status_code == 404


def test_track_can_be_assigned_without_a_roster_match(client):
    """Not every tracked player is a known prospect — scouting an opponent
    is a legitimate case with no athlete_id at all."""
    video_id = _upload_video(client)
    _seed_track(client, video_id)

    response = client.post(
        f"/api/videos/{video_id}/tracks/1/assign",
        json={"player_id": "opponent-12", "jersey_number": "12", "reason": "Opponent, not a prospect"},
    )
    assert response.status_code == 200
    assert response.json()["athlete_id"] is None
    assert response.json()["player_id"] == "opponent-12"


def test_reassigning_a_track_upserts_instead_of_duplicating(client):
    video_id = _upload_video(client)
    athlete_id = _make_athlete(client)
    _seed_track(client, video_id)

    client.post(f"/api/videos/{video_id}/tracks/1/assign",
                json={"athlete_id": athlete_id, "jersey_number": "12", "reason": "First pass"})
    second = client.post(f"/api/videos/{video_id}/tracks/1/assign",
                          json={"athlete_id": athlete_id, "jersey_number": "7", "reason": "Corrected number"})

    assert second.json()["jersey_number"] == "7"
    assert len(second.json()["history"]) == 2

    tracks = client.get(f"/api/videos/{video_id}/tracks").json()
    assert len(tracks["assignments"]) == 1
