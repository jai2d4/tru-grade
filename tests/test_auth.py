"""Phase 21 — real accounts: signup, login, logout, session cookie, and
athlete-roster linking. Real DB — mirrors test_board.py."""
import pytest


@pytest.fixture(autouse=True)
def _skip_without_db(db_available):
    available, reason = db_available
    if not available:
        pytest.skip(f"No PostgreSQL reachable — set POSTGRES_* env vars to run these tests. ({reason})")


def _headers(api_key_required):
    return {"X-API-Key": api_key_required}


def test_coach_signup_sets_a_session_and_me_reflects_it(client, api_key_required):
    headers = _headers(api_key_required)
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "Coach@Example.com", "password": "hunter22", "full_name": "Coach T", "role": "coach"},
        headers=headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "coach@example.com"  # normalized lowercase
    assert body["role"] == "coach"
    assert body["athlete_id"] is None
    assert "trugrade_session" in r.cookies

    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "coach@example.com"


def test_signup_rejects_a_duplicate_email(client, api_key_required):
    headers = _headers(api_key_required)
    payload = {"email": "dupe@example.com", "password": "hunter22", "full_name": "A", "role": "coach"}
    r = client.post("/api/v1/auth/signup", json=payload, headers=headers)
    assert r.status_code == 201

    r = client.post("/api/v1/auth/signup", json={**payload, "full_name": "B"}, headers=headers)
    assert r.status_code == 409


def test_athlete_signup_without_a_matching_roster_row_creates_one(client, api_key_required):
    headers = _headers(api_key_required)
    r = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "newkid@example.com", "password": "hunter22", "full_name": "Newkid Rookie",
            "role": "athlete", "position": "WR",
        },
        headers=headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["athlete_id"] is not None

    r = client.get(f"/api/v1/athletes/{body['athlete_id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["first_name"] == "Newkid"
    assert r.json()["last_name"] == "Rookie"
    assert r.json()["position"] == "WR"


def test_athlete_signup_links_a_single_matching_unclaimed_roster_row(client, api_key_required):
    headers = _headers(api_key_required)
    r = client.post(
        "/api/v1/athletes",
        json={"first_name": "Jordan", "last_name": "Williams", "position": "DB"},
        headers=headers,
    )
    assert r.status_code == 201
    existing_id = r.json()["id"]

    r = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "jordan@example.com", "password": "hunter22", "full_name": "Jordan Williams",
            "role": "athlete", "position": "DB",
        },
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["athlete_id"] == existing_id


def test_athlete_signup_with_an_ambiguous_match_creates_a_new_row_instead_of_guessing(client, api_key_required):
    headers = _headers(api_key_required)
    for _ in range(2):
        r = client.post(
            "/api/v1/athletes",
            json={"first_name": "Sam", "last_name": "Lee", "position": "RB"},
            headers=headers,
        )
        assert r.status_code == 201

    r = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "samlee@example.com", "password": "hunter22", "full_name": "Sam Lee",
            "role": "athlete", "position": "RB",
        },
        headers=headers,
    )
    assert r.status_code == 201
    new_id = r.json()["athlete_id"]

    r = client.get("/api/v1/athletes", params={"position": "RB"}, headers=headers)
    sam_lees = [a for a in r.json() if a["first_name"] == "Sam" and a["last_name"] == "Lee"]
    assert len(sam_lees) == 3  # the two originals plus a fresh one, never a silent guess
    assert new_id in {a["id"] for a in sam_lees}


def test_athlete_signup_requires_a_position(client, api_key_required):
    headers = _headers(api_key_required)
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "noposition@example.com", "password": "hunter22", "full_name": "No Position", "role": "athlete"},
        headers=headers,
    )
    assert r.status_code == 422


def test_login_rejects_wrong_password_with_a_generic_message(client, api_key_required):
    headers = _headers(api_key_required)
    client.post(
        "/api/v1/auth/signup",
        json={"email": "login@example.com", "password": "correct-horse", "full_name": "Login Test", "role": "coach"},
        headers=headers,
    )

    r = client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "wrong"}, headers=headers)
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid email or password."}

    r = client.post(
        "/api/v1/auth/login", json={"email": "unknown@example.com", "password": "wrong"}, headers=headers,
    )
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid email or password."}


def test_login_succeeds_and_logout_ends_the_session(client, api_key_required):
    headers = _headers(api_key_required)
    client.post(
        "/api/v1/auth/signup",
        json={"email": "session@example.com", "password": "correct-horse", "full_name": "Session Test", "role": "coach"},
        headers=headers,
    )
    client.cookies.clear()

    r = client.post(
        "/api/v1/auth/login", json={"email": "session@example.com", "password": "correct-horse"}, headers=headers,
    )
    assert r.status_code == 200

    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200

    r = client.post("/api/v1/auth/logout", headers=headers)
    assert r.status_code == 204

    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 401


def test_me_without_a_session_is_401_not_an_error(client, api_key_required):
    r = client.get("/api/v1/auth/me", headers=_headers(api_key_required))
    assert r.status_code == 401
    assert r.json() == {"detail": "Not signed in."}
