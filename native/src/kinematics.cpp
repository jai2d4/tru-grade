#include "trugrade/kinematics.hpp"

#include <cmath>
#include <cstddef>

namespace trugrade {

std::optional<MovementMetrics> movement_metrics(std::span<const Position> positions) noexcept {
    if (positions.size() < 2) {
        return std::nullopt;
    }

    double max_speed = positions[0].speed_px;
    double min_direction = positions[0].direction;
    double max_direction = positions[0].direction;
    double confidence_total = 0.0;

    // Summed in sample order so the floating-point result matches the Python
    // sum() it replaces bit for bit.
    for (const Position& point : positions) {
        if (point.speed_px > max_speed) {
            max_speed = point.speed_px;
        }
        if (point.direction < min_direction) {
            min_direction = point.direction;
        }
        if (point.direction > max_direction) {
            max_direction = point.direction;
        }
        confidence_total += point.confidence;
    }

    // Frames sharing a timestamp contribute no acceleration sample rather than
    // an infinite one. With every sample skipped both extremes stay at zero,
    // matching `max(accelerations, default=0)`.
    double max_acceleration = 0.0;
    double max_deceleration = 0.0;
    bool sampled = false;
    for (std::size_t index = 0; index + 1 < positions.size(); ++index) {
        const Position& before = positions[index];
        const Position& after = positions[index + 1];
        const double elapsed = static_cast<double>(after.timestamp_ms - before.timestamp_ms) / 1000.0;
        if (elapsed <= 0.0) {
            continue;
        }
        const double acceleration = (after.speed_px - before.speed_px) / elapsed;
        if (!sampled) {
            max_acceleration = acceleration;
            max_deceleration = acceleration;
            sampled = true;
        } else if (acceleration > max_acceleration) {
            max_acceleration = acceleration;
        } else if (acceleration < max_deceleration) {
            max_deceleration = acceleration;
        }
    }

    const double displacement_x = positions.back().center_x - positions.front().center_x;
    const double displacement_y = positions.back().center_y - positions.front().center_y;

    return MovementMetrics{
        .max_speed_px = max_speed,
        .max_acceleration_px_s2 = max_acceleration,
        .max_deceleration_px_s2 = max_deceleration,
        .direction_change_deg = max_direction - min_direction,
        .displacement_px = std::hypot(displacement_x, displacement_y),
        .confidence = confidence_total / static_cast<double>(positions.size()),
    };
}

}  // namespace trugrade
