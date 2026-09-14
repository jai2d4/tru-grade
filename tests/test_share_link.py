"""Public Rating — coach-issued share links and the anonymous public view
they unlock. Real DB — mirrors test_board.py."""
import pytest


@pytest.fixture(autouse=True)
def _skip_without_db(db_available):
    available, reason = db_available
    if not available:
        pytest.skip(f"No PostgreSQL reachable — set POSTGRES_* env vars to run these tests. ({reason})")


def _make_athlete(client, api_key_required, **overrides):
    headers = {"X-API-Key": api_key_required}
    payload = {"first_name": "Share", "last_name": "Link", "position": "DB", **overrides}
    r = client.post("/api/v1/athletes", json=payload, headers=headers)
    assert r.status_code == 201
    return r.json()["id"], headers


def test_share_link_defaults_to_none_then_issues_and_revokes(client, api_key_required):
    athlete_id, headers = _make_athlete(client, api_key_required)

    r = client.get(f"/api/v1/athletes/{athlete_id}/share-link", headers=headers)
    assert r.status_code == 200
    assert r.json() is None

    r = client.post(f"/api/v1/athletes/{athlete_id}/share-link", headers=headers)
    assert r.status_code == 201
    first_token = r.json()["token"]
    assert first_token

    r = client.get(f"/api/v1/athletes/{athlete_id}/share-link", headers=headers)
    assert r.status_code == 200
    assert r.json()["token"] == first_token

    # Regenerating is an upsert — a new token, invalidating the old one.
    r = client.post(f"/api/v1/athletes/{athlete_id}/share-link", headers=headers)
    assert r.status_code == 201
    second_token = r.json()["token"]
    assert second_token != first_token

    r = client.get(f"/api/v1/public/athletes/{first_token}")
    assert r.status_code == 404

    r = client.get(f"/api/v1/public/athletes/{second_token}")
    assert r.status_code == 200

    r = client.delete(f"/api/v1/athletes/{athlete_id}/share-link", headers=headers)
    assert r.status_code == 204

    r = client.get(f"/api/v1/athletes/{athlete_id}/share-link", headers=headers)
    assert r.json() is None

    r = client.get(f"/api/v1/public/athletes/{second_token}")
    assert r.status_code == 404


def test_share_link_requires_real_athlete(client, api_key_required):
    headers = {"X-API-Key": api_key_required}
    r = client.post(
        "/api/v1/athletes/00000000-0000-0000-0000-000000000000/share-link",
        headers=headers,
    )
    assert r.status_code == 404


def test_public_view_requires_no_api_key_and_hides_private_fields(client, api_key_required):
    athlete_id, headers = _make_athlete(client, api_key_required, school="Central HS", grad_year=2027)

    r = client.post(f"/api/v1/athletes/{athlete_id}/share-link", headers=headers)
    token = r.json()["token"]

    # No X-API-Key at all — this is the whole point of a public link.
    r = client.get(f"/api/v1/public/athletes/{token}")
    assert r.status_code == 200
    body = r.json()
    assert body["first_name"] == "Share"
    assert body["last_name"] == "Link"
    assert body["position"] == "DB"
    assert body["school"] == "Central HS"
    assert body["grad_year"] == 2027
    # No projected tier yet — never fabricate one for an unevaluated athlete.
    assert body["projected_tier"] is None
    assert body["is_game_changer"] is False
    # Deliberately narrow — hard metrics, notes, fit scores, and film must
    # never appear on the public payload.
    forbidden = {
        "height_in", "weight_lbs", "forty_s", "shuttle_s", "bench_lbs", "squat_lbs",
        "gpa", "sat", "act", "notes", "scheme_fit", "culture_fit", "need_match",
        "development", "film_grades", "film_analysis", "metric_sieve_results",
    }
    assert forbidden.isdisjoint(body.keys())


def test_public_view_rejects_unknown_token(client):
    r = client.get("/api/v1/public/athletes/not-a-real-token")
    assert r.status_code == 404
