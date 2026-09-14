// Per-track kinematics derived only from tracked coordinates.
#pragma once

#include <cstdint>
#include <optional>
#include <span>

namespace trugrade {

/// One sampled position on a track. `speed_px` and `direction` are carried in
/// rather than recomputed: the tracker already rounded them when it emitted the
/// point, and the Python implementation reads those rounded values back out of
/// the track history. Recomputing from the raw centres here would silently
/// disagree with it in the last decimal place.
struct Position {
    double center_x{};
    double center_y{};
    std::int64_t timestamp_ms{};
    double speed_px{};
    double direction{};
    double confidence{};
};

/// Pixel-space movement summary. Values are deliberately unrounded — the Python
/// binding applies `round()` so that one rounding policy governs both the native
/// and the fallback path. See docs/NATIVE_CORE.md.
struct MovementMetrics {
    double max_speed_px{};
    double max_acceleration_px_s2{};
    double max_deceleration_px_s2{};
    double direction_change_deg{};
    double displacement_px{};
    double confidence{};
};

/// Summarise a track's movement.
///
/// Returns nullopt for fewer than two points, which is the caller's cue to emit
/// the "Insufficient tracked points." result rather than a zeroed one — an
/// unknown speed and a measured zero are different claims about an athlete.
[[nodiscard]] std::optional<MovementMetrics> movement_metrics(std::span<const Position> positions) noexcept;

}  // namespace trugrade
