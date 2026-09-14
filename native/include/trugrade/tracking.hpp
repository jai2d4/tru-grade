// Two-stage ByteTrack-style association.
#pragma once

#include <cstdint>
#include <span>
#include <vector>

#include "trugrade/geometry.hpp"

namespace trugrade {

/// A candidate detection for one frame. The class label is filtered in Python:
/// it is a string comparison done once per detection, and keeping it out of the
/// ABI means no string ever crosses the boundary.
struct Detection {
    BBox bbox{};
    double confidence{};
};

/// The association result for one detection.
struct TrackPoint {
    std::int32_t track_id{};
    double center_x{};
    double center_y{};
    double velocity_x{};
    double velocity_y{};
    double speed_px{};
    double direction{};
};

/// Greedy IoU association, high-confidence detections first.
///
/// The tracker owns only what association needs — last box, last frame, last
/// timestamp. Full point history stays in Python, which is what `export_tracks`
/// serialises; duplicating it here would mean two copies to keep in step for no
/// gain, since history is written once per frame and read once at the end.
class ByteTracker {
public:
    ByteTracker(double high_threshold, double low_threshold, double match_iou,
                std::int32_t max_lost_frames) noexcept;

    /// Associate one frame's detections. Detections are split on
    /// `high_threshold` and associated in two passes over a shared claim set,
    /// so a low-confidence box can only recover a track no strong box wanted.
    /// Returns one point per surviving detection, high-confidence pass first.
    [[nodiscard]] std::vector<TrackPoint> update(std::span<const Detection> detections,
                                                 std::int32_t frame,
                                                 std::int64_t timestamp_ms);

    [[nodiscard]] std::size_t track_count() const noexcept { return tracks_.size(); }

private:
    struct Track {
        std::int32_t track_id{};
        BBox bbox{};
        std::int32_t last_frame{};
        std::int64_t last_timestamp_ms{};
        bool has_history{};
    };

    void associate(std::span<const Detection> detections, std::int32_t frame,
                   std::int64_t timestamp_ms, std::vector<bool>& claimed,
                   std::vector<TrackPoint>& output);

    double high_threshold_;
    double low_threshold_;
    double match_iou_;
    std::int32_t max_lost_frames_;
    // Insertion-ordered: the Python original iterated a dict and took the first
    // maximum on a tie, so candidate order is part of the observable behaviour.
    std::vector<Track> tracks_;
    std::int32_t next_id_{1};
};

}  // namespace trugrade
