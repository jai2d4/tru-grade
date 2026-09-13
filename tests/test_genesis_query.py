"""Genesis Search's natural-language layer: POST /api/v1/scout/genesis-query
parses a free-text query into structured roster filters via Gemini."""
import json
from unittest.mock import MagicMock

import pytest


def _mock_gemini_json(monkeypatch_target, payload: dict):
    import app.main as m

    fake_response = MagicMock()
    fake_response.text = json.dumps(payload)
    m.ai_client.models.generate_content = MagicMock(return_value=fake_response)


def test_genesis_query_parses_a_real_query_into_structured_filters(client, api_key_required):
    _mock_gemini_json(
        None,
        {
            "position": "OL",
            "weight_lbs_min": 300,
            "gpa_min": 3.0,
            "grad_year_min": None,
            "grad_year_max": None,
            "height_in_min": None,
            "height_in_max": None,
            "weight_lbs_max": None,
            "forty_s_max": None,
            "shuttle_s_max": None,
            "bench_lbs_min": None,
            "squat_lbs_min": None,
            "sat_min": None,
            "act_min": None,
            "state": None,
            "school_contains": None,
            "name_contains": None,
            "interpretation_note": "Searching for offensive linemen at least 300 lbs with a 3.0+ GPA.",
        },
    )

    r = client.post(
        "/api/v1/scout/genesis-query",
        json={"query": "offensive linemen over 300 lbs with a 3.0 GPA"},
        headers={"X-API-Key": api_key_required},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["position"] == "OL"
    assert body["weight_lbs_min"] == 300
    assert body["gpa_min"] == 3.0
    assert "300" in body["interpretation_note"]


def test_genesis_query_never_invents_unstated_criteria(client, api_key_required):
    """A vague query should come back with every field null except the note —
    the model must not fill in plausible-looking values it wasn't given."""
    _mock_gemini_json(
        None,
        {
            "position": None,
            "grad_year_min": None,
            "grad_year_max": None,
            "height_in_min": None,
            "height_in_max": None,
            "weight_lbs_min": None,
            "weight_lbs_max": None,
            "forty_s_max": None,
            "shuttle_s_max": None,
            "bench_lbs_min": None,
            "squat_lbs_min": None,
            "gpa_min": None,
            "sat_min": None,
            "act_min": None,
            "state": None,
            "school_contains": None,
            "name_contains": None,
            "interpretation_note": "No specific criteria were stated in this query.",
        },
    )

    r = client.post(
        "/api/v1/scout/genesis-query",
        json={"query": "show me some good players"},
        headers={"X-API-Key": api_key_required},
    )

    assert r.status_code == 200
    body = r.json()
    assert all(body[key] is None for key in body if key != "interpretation_note")


def test_genesis_query_502s_on_malformed_model_output(client, api_key_required):
    import app.main as m

    fake_response = MagicMock()
    fake_response.text = "not valid json at all"
    m.ai_client.models.generate_content = MagicMock(return_value=fake_response)

    r = client.post(
        "/api/v1/scout/genesis-query",
        json={"query": "quarterbacks"},
        headers={"X-API-Key": api_key_required},
    )

    assert r.status_code == 502
    assert "Could not parse" in r.json()["detail"]


def test_genesis_query_requires_the_api_key_when_configured(client, api_key_required):
    r = client.post("/api/v1/scout/genesis-query", json={"query": "quarterbacks"})
    assert r.status_code == 401
