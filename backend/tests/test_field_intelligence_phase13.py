import numpy as np

from backend.football.movement import movement_metrics
from backend.vision.field_calibration import FieldCalibration, KnownFieldPoint


def perspective_calibration():
    return FieldCalibration(points=[
        KnownFieldPoint(pixel_x=100, pixel_y=100, x_yards=0, y_yards=0),
        KnownFieldPoint(pixel_x=900, pixel_y=100, x_yards=100, y_yards=0),
        KnownFieldPoint(pixel_x=1100, pixel_y=600, x_yards=100, y_yards=53.3),
        KnownFieldPoint(pixel_x=0, pixel_y=600, x_yards=0, y_yards=53.3),
    ], confidence=.8, method="manual")


def test_four_point_homography_maps_field_corners():
    calibration = perspective_calibration()
    assert calibration.pixel_to_field(100, 100) == (0.0, 0.0)
    assert calibration.pixel_to_field(1100, 600) == (100.0, 53.3)
    # Intersection of the image-space diagonals maps to field center.
    center = calibration.pixel_to_field(521.0526, 310.5263)
    assert np.allclose(center, (50, 26.65), atol=.01)


def test_calibrated_movement_reports_yards_speed_and_mph():
    calibration = FieldCalibration(points=[
        KnownFieldPoint(pixel_x=0, pixel_y=0, x_yards=0, y_yards=0),
        KnownFieldPoint(pixel_x=100, pixel_y=100, x_yards=10, y_yards=10),
    ], confidence=.9)
    result = movement_metrics([
        {"timestamp_ms": 0, "center_x": 0, "center_y": 0, "speed_px": 0, "direction": 0, "confidence": 1},
        {"timestamp_ms": 1000, "center_x": 30, "center_y": 40, "speed_px": 50, "direction": 45, "confidence": 1},
    ], calibration)
    assert result["displacement_yards"] == 5
    assert result["max_speed_yards_per_second"] == 5
    assert result["field_speed_mph"] == 10.23
    assert result["confidence"] == .9
