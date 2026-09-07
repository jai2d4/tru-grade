from pathlib import Path

from backend.main import app


def test_phase9_api_routes_are_registered():
    # FastAPI may retain included routers lazily in ``app.routes``. The OpenAPI
    # schema is the authoritative flattened list of publicly usable endpoints.
    paths = set(app.openapi()["paths"])
    assert "/api/videos/upload" in paths
    assert "/api/videos/{video_id}/content" in paths
    assert "/api/videos/{video_id}/tracks" in paths
    assert "/api/videos/{video_id}/detections" in paths
    assert "/api/videos/{video_id}/plays" in paths
    assert "/api/players/{player_id}/grades" in paths


def test_phase9_ui_preserves_existing_app_and_adds_workspace():
    html = (Path(__file__).parents[2] / "frontend" / "index.html").read_text(encoding="utf-8")
    for existing in ("Create Profile", "AI TRUTH REPORT", "Dashboard", "Recruitment Board"):
        assert existing in html
    for addition in ("FILM ANALYSIS", "Tracking overlay"):
        assert addition in html
    # These headings contain styled spans, so assert their stable workspace IDs
    # instead of expecting the rendered words to be contiguous in source HTML.
    for workspace_id in ('id="v2Plays"', 'id="v2Evidence"', 'id="v2Grade"'):
        assert workspace_id in html
