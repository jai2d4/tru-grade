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


# test_phase9_ui_preserves_existing_app_and_adds_workspace used to live here,
# asserting literal strings ("Create Profile", 'id="v2Plays"', etc.) against
# frontend/index.html. The Phase 16 migration (cab29e9) replaced that file
# with a bare Vite shell — every screen, including the Film Analysis
# workspace this test was written for, now renders from React components
# instead. The assertion has failed on every branch descended from that
# migration ever since (it never causes a merge conflict, so nothing forced
# anyone to notice or update it). Real coverage for this UI now lives in
# frontend/tests/routes.test.tsx ("Film Analysis route"), which asserts
# against the actual rendered DOM rather than the pre-build source file.
