"""Measured accuracy of automatic field calibration.

`automatic_field_calibration` had no test coverage at all, so its accuracy
was an open question — it reports a `confidence` derived purely from how
much green fills the frame, which says nothing about whether the resulting
yard numbers are right.

These tests answer it properly: build a synthetic field whose true
geometry is known by construction, warp it through a chosen camera
homography, run calibration on the result, and measure the error in YARDS
at points the calibration never saw. Synthetic footage is a friendly case
— no lens distortion, no players occluding the boundary, no stadium in
frame — so treat the numbers here as an upper bound on real accuracy, not
a promise about game film.
"""
from __future__ import annotations

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from backend.vision.field_calibration import automatic_field_calibration  # noqa: E402

FIELD_LENGTH_YD = 100.0
FIELD_WIDTH_YD = 53.3
GRASS_BGR = (58, 132, 74)  # a plausible turf green in BGR


def _synthetic_field_view(image_size=(1280, 720), inset=0.10, tilt=0.22, noise=0):
    """Render a field seen from a raised sideline camera.

    Returns (image, world_to_pixel) where world_to_pixel maps
    (x_yards, y_yards) to pixel coordinates — the ground truth the
    calibration is being scored against.
    """
    width, height = image_size
    # Field corners in the image: a trapezoid, wider at the bottom, which
    # is what a raised camera actually sees.
    margin_x, margin_y = width * inset, height * inset
    top_squeeze = width * tilt * 0.5
    dst = np.float32([
        [margin_x + top_squeeze, margin_y],                    # far-left
        [width - margin_x - top_squeeze, margin_y],            # far-right
        [width - margin_x, height - margin_y],                 # near-right
        [margin_x, height - margin_y],                         # near-left
    ])
    # Same corner order in field coordinates.
    src = np.float32([
        [0.0, 0.0], [FIELD_LENGTH_YD, 0.0],
        [FIELD_LENGTH_YD, FIELD_WIDTH_YD], [0.0, FIELD_WIDTH_YD],
    ])
    world_to_pixel = cv2.getPerspectiveTransform(src, dst)

    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = (35, 35, 35)  # dark surround: stands, track, sky
    cv2.fillConvexPoly(image, dst.astype(np.int32), GRASS_BGR)
    if noise:
        image = np.clip(
            image.astype(np.int16) + np.random.default_rng(0).integers(-noise, noise, image.shape),
            0, 255,
        ).astype(np.uint8)
    return image, world_to_pixel


def _project(world_to_pixel, x_yd, y_yd):
    point = world_to_pixel @ np.array([x_yd, y_yd, 1.0])
    return float(point[0] / point[2]), float(point[1] / point[2])


def _yard_errors(calibration, world_to_pixel, samples):
    """Error in yards at each sample point, via the calibration's own
    pixel->field mapping."""
    errors = []
    for x_yd, y_yd in samples:
        px, py = _project(world_to_pixel, x_yd, y_yd)
        est_x, est_y = calibration.pixel_to_field(px, py)
        errors.append(float(np.hypot(est_x - x_yd, est_y - y_yd)))
    return errors


# Interior points, deliberately not the corners the calibration fits to.
INTERIOR_SAMPLES = [
    (25.0, 13.3), (50.0, 26.65), (75.0, 40.0),
    (10.0, 45.0), (90.0, 8.0), (50.0, 5.0), (50.0, 48.0),
]


def test_clean_field_view_calibrates_and_is_accurate_to_within_a_yard():
    """The friendly case: whole field visible, no occlusion, no noise."""
    image, world_to_pixel = _synthetic_field_view()
    result = automatic_field_calibration(image)

    assert not isinstance(result, dict), f"expected a calibration, got {result}"
    errors = _yard_errors(result, world_to_pixel, INTERIOR_SAMPLES)
    worst = max(errors)
    # Sub-yard on synthetic input. This is the ceiling, not the
    # expectation for real footage.
    assert worst < 1.0, f"worst interior error {worst:.2f} yd, all={[round(e, 2) for e in errors]}"


@pytest.mark.parametrize("noise", [0, 8, 18, 30])
def test_under_noise_it_is_either_accurate_or_it_declines_never_confidently_wrong(noise):
    """The invariant that actually matters.

    Whether noise defeats detection is a detail; what must never happen is
    a calibration that looks confident and is wrong, because every speed
    and distance downstream inherits that error. So: calibrate within
    tolerance, or decline. Nothing in between.
    """
    image, world_to_pixel = _synthetic_field_view(noise=noise)
    result = automatic_field_calibration(image)

    if isinstance(result, dict):
        assert result["status"] == "needs_manual_points"
        assert result["confidence"] == 0.0
        return

    worst = max(_yard_errors(result, world_to_pixel, INTERIOR_SAMPLES))
    assert worst < 2.0, (
        f"calibration reported confidence {result.confidence} but is off by "
        f"{worst:.2f} yd at noise={noise} — confidently wrong is the one "
        f"outcome this must never produce"
    )


def test_a_partial_field_view_is_refused_rather_than_silently_mis_scaled():
    """The important honesty case.

    Calibration maps whatever quadrilateral it finds onto the FULL
    100x53.3 yard field. If only part of the field is visible — which is
    typical of phone footage shot from the sideline — that assumption is
    wrong and every yard number derived from it would be wrong too. It
    must decline rather than produce confident nonsense.
    """
    image, _ = _synthetic_field_view()
    # Keep the left third: a plausible "camera pointed at one end" crop.
    cropped = image[:, : image.shape[1] // 3].copy()
    result = automatic_field_calibration(cropped)
    assert isinstance(result, dict), (
        "a partial field view produced a calibration; its yardage would be "
        "silently wrong because the visible region is not the whole field"
    )
    assert result["status"] == "needs_manual_points"
    assert result["confidence"] == 0.0


def test_a_frame_with_no_field_is_refused():
    blank = np.full((480, 640, 3), (40, 40, 40), dtype=np.uint8)
    result = automatic_field_calibration(blank)
    assert isinstance(result, dict)
    assert result["status"] == "needs_manual_points"
    assert result["confidence"] == 0.0


def test_reported_confidence_is_a_coverage_heuristic_not_an_accuracy_claim():
    """Pins the meaning of `confidence` so it can't be mistaken for an
    accuracy figure: it is derived from how much of the frame is green and
    is capped at 0.8, regardless of how exact the geometry turns out to be."""
    image, world_to_pixel = _synthetic_field_view()
    result = automatic_field_calibration(image)
    assert not isinstance(result, dict)
    assert 0 < result.confidence <= 0.8
    assert result.method == "automatic_visible_field_estimate"
    # Near-perfect geometry, yet confidence stays capped — evidence that
    # the number describes detection coverage, not measurement error.
    assert max(_yard_errors(result, world_to_pixel, INTERIOR_SAMPLES)) < 1.0
