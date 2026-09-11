"""Module 7 — Coach Recruitment Board, Team Needs, coach notes/fit scores,
and the /offer-probability endpoint. Real DB — mirrors test_persistence.py."""
import pytest


@pytest.fixture(autouse=True)
def _skip_without_db(db_available):
    available, reason = db_available
    if not available:
        pytest.skip(f"No PostgreSQL reachable — set POSTGRES_* env vars to run these tests. ({reason})")


def _make_athlete(client, api_key_required, **overrides):
    headers = {"X-API-Key": api_key_required}
    payload = {"first_name": "Board", "last_name": "Test", "position": "DB", **overrides}
    r = client.post("/api/v1/athletes", json=payload, headers=headers)
    assert r.status_code == 201
    return r.json()["id"], headers


def test_add_move_and_remove_board_entry(client, api_key_required):
    athlete_id, headers = _make_athlete(client, api_key_required)

    r = client.put(f"/api/v1/board/{athlete_id}", json={"stage": "watchlist"}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "watchlist"
    assert body["first_name"] == "Board"

    # Moving is the same endpoint (upsert), not a duplicate card
    r = client.put(f"/api/v1/board/{athlete_id}", json={"stage": "offer_board", "notes": "High priority"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["stage"] == "offer_board"
    assert r.json()["notes"] == "High priority"

    r = client.get("/api/v1/board", headers=headers)
    assert r.status_code == 200
    ids = [e["athlete_id"] for e in r.json()]
    assert athlete_id in ids

    r = client.get("/api/v1/board", params={"stage": "offer_board"}, headers=headers)
    assert any(e["athlete_id"] == athlete_id for e in r.json())
    r = client.get("/api/v1/board", params={"stage": "watchlist"}, headers=headers)
    assert not any(e["athlete_id"] == athlete_id for e in r.json())

    r = client.delete(f"/api/v1/board/{athlete_id}", headers=headers)
    assert r.status_code == 204
    r = client.get("/api/v1/board", headers=headers)
    assert not any(e["athlete_id"] == athlete_id for e in r.json())


def test_board_entry_requires_real_athlete(client, api_key_required):
    headers = {"X-API-Key": api_key_required}
    r = client.put(
        "/api/v1/board/00000000-0000-0000-0000-000000000000",
        json={"stage": "watchlist"}, headers=headers,
    )
    assert r.status_code == 404


def test_set_and_list_team_needs(client, api_key_required):
    headers = {"X-API-Key": api_key_required}
    r = client.put("/api/v1/team-needs/QB", json={"priority": 5}, headers=headers)
    assert r.status_code == 200
    assert r.json()["priority"] == 5

    r = client.put("/api/v1/team-needs/QB", json={"priority": 2}, headers=headers)
    assert r.json()["priority"] == 2  # upsert, not a duplicate row

    r = client.get("/api/v1/team-needs", headers=headers)
    assert r.status_code == 200
    qb = next(n for n in r.json() if n["position"] == "QB")
    assert qb["priority"] == 2


def test_coach_notes(client, api_key_required):
    athlete_id, headers = _make_athlete(client, api_key_required)

    r = client.post(f"/api/v1/athletes/{athlete_id}/notes", json={"note": "Great tape.", "author": "Coach T"}, headers=headers)
    assert r.status_code == 201
    assert r.json()["note"] == "Great tape."

    r = client.get(f"/api/v1/athletes/{athlete_id}/notes", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["author"] == "Coach T"


def test_fit_scores_default_to_null_then_upsert(client, api_key_required):
    athlete_id, headers = _make_athlete(client, api_key_required)

    r = client.get(f"/api/v1/athletes/{athlete_id}/fit-scores", headers=headers)
    assert r.status_code == 200
    assert r.json()["scheme_fit"] is None

    r = client.put(f"/api/v1/athletes/{athlete_id}/fit-scores", json={"scheme_fit": 4, "culture_fit": 5}, headers=headers)
    assert r.status_code == 200
    assert r.json()["scheme_fit"] == 4
    assert r.json()["culture_fit"] == 5

    r = client.get(f"/api/v1/athletes/{athlete_id}/fit-scores", headers=headers)
    assert r.json()["scheme_fit"] == 4


def test_coach_dashboard_aggregates_real_counts(client, api_key_required):
    headers = {"X-API-Key": api_key_required}
    athlete_id, _ = _make_athlete(client, api_key_required)
    client.put(f"/api/v1/board/{athlete_id}", json={"stage": "watchlist"}, headers=headers)

    r = client.get("/api/v1/coach/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_athletes"] >= 1
    assert body["board_counts"]["watchlist"] >= 1
    assert set(body["board_counts"].keys()) == {"watchlist", "evaluating", "offer_board", "development", "follow_up"}
