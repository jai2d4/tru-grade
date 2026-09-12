"""Perspective field calibration with explicit confidence and honest fallback."""
from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field, model_validator


class KnownFieldPoint(BaseModel):
    pixel_x: float
    pixel_y: float
    x_yards: float
    y_yards: float


class FieldCalibration(BaseModel):
    points: list[KnownFieldPoint] = Field(min_length=2)
    confidence: float = Field(ge=0, le=1)
    method: str = "manual"

    @model_validator(mode="after")
    def distinct_points(self):
        first, last = self.points[0], self.points[-1]
        if first.pixel_x == last.pixel_x or first.pixel_y == last.pixel_y:
            raise ValueError("Calibration points must span both field axes")
        return self

    def pixel_to_field(self, pixel_x: float, pixel_y: float) -> tuple[float, float]:
        if len(self.points) >= 4:
            source = np.asarray([[point.pixel_x, point.pixel_y] for point in self.points], dtype=float)
            target = np.asarray([[point.x_yards, point.y_yards] for point in self.points], dtype=float)
            matrix = _homography(source, target)
            projected = matrix @ np.asarray([pixel_x, pixel_y, 1.0])
            if abs(projected[2]) < 1e-9:
                raise ValueError("Point cannot be projected by this field calibration")
            return round(float(projected[0] / projected[2]), 3), round(float(projected[1] / projected[2]), 3)
        first, last = self.points[0], self.points[-1]
        x_scale = (last.x_yards - first.x_yards) / (last.pixel_x - first.pixel_x)
        y_scale = (last.y_yards - first.y_yards) / (last.pixel_y - first.pixel_y)
        return (
            round(first.x_yards + (pixel_x - first.pixel_x) * x_scale, 3),
            round(first.y_yards + (pixel_y - first.pixel_y) * y_scale, 3),
        )


def _homography(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    rows = []
    for (x, y), (u, v) in zip(source, target):
        rows.extend(([x, y, 1, 0, 0, 0, -u * x, -u * y, -u],
                     [0, 0, 0, x, y, 1, -v * x, -v * y, -v]))
    _, _, vh = np.linalg.svd(np.asarray(rows, dtype=float))
    matrix = vh[-1].reshape(3, 3)
    return matrix / matrix[2, 2]


def automatic_field_calibration(frame) -> FieldCalibration | dict:
    """Estimate the visible field quadrilateral; reject weak geometry."""
    import cv2

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([25, 25, 20]), np.array([100, 255, 255]))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return automatic_calibration_unavailable("No field-colored region was detected.")
    contour = max(contours, key=cv2.contourArea)
    frame_area = frame.shape[0] * frame.shape[1]
    coverage = cv2.contourArea(contour) / max(frame_area, 1)
    epsilon = .025 * cv2.arcLength(contour, True)
    polygon = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
    if len(polygon) != 4 or coverage < .25:
        return automatic_calibration_unavailable("The visible field boundary was not complete enough.")
    ordered = _order_corners(polygon.astype(float))
    destinations = ((0, 0), (100, 0), (100, 53.3), (0, 53.3))
    confidence = min(.8, round(.45 + coverage * .35, 3))
    return FieldCalibration(points=[
        KnownFieldPoint(pixel_x=float(pixel[0]), pixel_y=float(pixel[1]),
                        x_yards=field[0], y_yards=field[1])
        for pixel, field in zip(ordered, destinations)
    ], confidence=confidence, method="automatic_visible_field_estimate")


def _order_corners(points: np.ndarray) -> np.ndarray:
    total, delta = points.sum(axis=1), np.diff(points, axis=1).reshape(-1)
    return np.asarray([points[np.argmin(total)], points[np.argmin(delta)],
                       points[np.argmax(total)], points[np.argmax(delta)]])


def automatic_calibration_unavailable(reason: str = "Manual field points are required.") -> dict:
    return {"method": "automatic", "status": "needs_manual_points", "confidence": 0.0, "reason": reason}
