// Bounding-box geometry. Header-only where the maths is small enough that a
// call through the ABI would cost more than the arithmetic it performs.
#pragma once

#include <array>
#include <cmath>

namespace trugrade {

/// Axis-aligned box in pixel space, ordered (x1, y1) top-left, (x2, y2) bottom-right.
struct BBox {
    double x1{};
    double y1{};
    double x2{};
    double y2{};

    [[nodiscard]] constexpr double width() const noexcept { return x2 - x1; }
    [[nodiscard]] constexpr double height() const noexcept { return y2 - y1; }
    [[nodiscard]] constexpr double center_x() const noexcept { return (x1 + x2) / 2; }
    [[nodiscard]] constexpr double center_y() const noexcept { return (y1 + y2) / 2; }
};

/// Intersection over union.
///
/// A degenerate box gives a zero or negative union. Python's `_iou` guarded only
/// the exactly-zero case (`if union else 0.0`) and let a negative union through
/// as a negative score, which then loses every `max()` comparison in the
/// associator. That behaviour is load-bearing for boxes with inverted corners,
/// so it is reproduced rather than "fixed" here.
[[nodiscard]] constexpr double iou(const BBox& a, const BBox& b) noexcept {
    const double x1 = a.x1 > b.x1 ? a.x1 : b.x1;
    const double y1 = a.y1 > b.y1 ? a.y1 : b.y1;
    const double x2 = a.x2 < b.x2 ? a.x2 : b.x2;
    const double y2 = a.y2 < b.y2 ? a.y2 : b.y2;

    const double overlap_w = (x2 - x1) > 0 ? (x2 - x1) : 0.0;
    const double overlap_h = (y2 - y1) > 0 ? (y2 - y1) : 0.0;
    const double intersection = overlap_w * overlap_h;

    const double area_a = (a.width() > 0 ? a.width() : 0.0) * (a.height() > 0 ? a.height() : 0.0);
    const double area_b = (b.width() > 0 ? b.width() : 0.0) * (b.height() > 0 ? b.height() : 0.0);
    const double denominator = area_a + area_b - intersection;

    return denominator != 0.0 ? intersection / denominator : 0.0;
}

/// Torso angle in degrees from the shoulder and hip midpoints.
///
/// Mirrors `body_orientation` in backend/vision/biomechanics.py: the caller has
/// already resolved COCO keypoints 5/6 (shoulders) and 11/12 (hips) into their
/// midpoints, because deciding whether those keypoints are present at all is a
/// dictionary question, not an arithmetic one.
[[nodiscard]] inline double torso_orientation_deg(double shoulder_x, double shoulder_y,
                                                  double hip_x, double hip_y) noexcept {
    return std::atan2(shoulder_y - hip_y, shoulder_x - hip_x) * 180.0 / M_PI;
}

}  // namespace trugrade
