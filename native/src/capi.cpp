// C++ side of the ABI bridge. Each entry point is extern "C", takes only POD,
// and is noexcept in effect: anything thrown is converted to a tg_status before
// it can unwind into C.
#include "trugrade_impl.h"

#include <new>
#include <span>
#include <vector>

#include "trugrade/geometry.hpp"
#include "trugrade/kinematics.hpp"
#include "trugrade/tracking.hpp"

namespace {

trugrade::BBox to_bbox(const tg_bbox& box) noexcept {
    return trugrade::BBox{.x1 = box.x1, .y1 = box.y1, .x2 = box.x2, .y2 = box.y2};
}

}  // namespace

// The opaque handle is completed here, so the C layer only ever holds a pointer
// to an incomplete type and cannot accidentally copy or inspect tracker state.
struct tg_tracker {
    explicit tg_tracker(double high, double low, double match_iou, std::int32_t max_lost)
        : tracker(high, low, match_iou, max_lost) {}

    trugrade::ByteTracker tracker;
    // Reused across frames so a per-frame association does not allocate.
    std::vector<trugrade::Detection> scratch;
};

extern "C" {

double tg_impl_iou(const tg_bbox* a, const tg_bbox* b) {
    return trugrade::iou(to_bbox(*a), to_bbox(*b));
}

double tg_impl_torso_orientation_deg(double shoulder_x, double shoulder_y,
                                     double hip_x, double hip_y) {
    return trugrade::torso_orientation_deg(shoulder_x, shoulder_y, hip_x, hip_y);
}

tg_status tg_impl_movement_metrics(const tg_position* positions, std::int32_t count,
                                   tg_movement_metrics* out_metrics) {
    try {
        std::vector<trugrade::Position> samples;
        samples.reserve(static_cast<std::size_t>(count));
        for (std::int32_t index = 0; index < count; ++index) {
            const tg_position& source = positions[index];
            samples.push_back(trugrade::Position{
                .center_x = source.center_x,
                .center_y = source.center_y,
                .timestamp_ms = source.timestamp_ms,
                .speed_px = source.speed_px,
                .direction = source.direction,
                .confidence = source.confidence,
            });
        }

        const auto metrics = trugrade::movement_metrics(samples);
        if (!metrics) {
            return TG_ERR_INSUFFICIENT_POINTS;
        }

        out_metrics->max_speed_px = metrics->max_speed_px;
        out_metrics->max_acceleration_px_s2 = metrics->max_acceleration_px_s2;
        out_metrics->max_deceleration_px_s2 = metrics->max_deceleration_px_s2;
        out_metrics->direction_change_deg = metrics->direction_change_deg;
        out_metrics->displacement_px = metrics->displacement_px;
        out_metrics->confidence = metrics->confidence;
        return TG_OK;
    } catch (...) {
        return TG_ERR_INTERNAL;
    }
}

tg_tracker* tg_impl_tracker_create(double high_threshold, double low_threshold,
                                   double match_iou, std::int32_t max_lost_frames) {
    return new (std::nothrow) tg_tracker(high_threshold, low_threshold, match_iou, max_lost_frames);
}

void tg_impl_tracker_destroy(tg_tracker* tracker) {
    delete tracker;
}

tg_status tg_impl_tracker_update(tg_tracker* tracker, const tg_detection* detections,
                                 std::int32_t count, std::int32_t frame, std::int64_t timestamp_ms,
                                 tg_track_point* out_points, std::int32_t capacity,
                                 std::int32_t* out_written) {
    try {
        tracker->scratch.clear();
        tracker->scratch.reserve(static_cast<std::size_t>(count));
        for (std::int32_t index = 0; index < count; ++index) {
            tracker->scratch.push_back(trugrade::Detection{
                .bbox = to_bbox(detections[index].bbox),
                .confidence = detections[index].confidence,
            });
        }

        const std::vector<trugrade::TrackPoint> points =
            tracker->tracker.update(tracker->scratch, frame, timestamp_ms);

        if (points.size() > static_cast<std::size_t>(capacity)) {
            return TG_ERR_BUFFER_TOO_SMALL;
        }

        for (std::size_t index = 0; index < points.size(); ++index) {
            const trugrade::TrackPoint& point = points[index];
            out_points[index] = tg_track_point{
                .track_id = point.track_id,
                .center_x = point.center_x,
                .center_y = point.center_y,
                .velocity_x = point.velocity_x,
                .velocity_y = point.velocity_y,
                .speed_px = point.speed_px,
                .direction = point.direction,
            };
        }

        *out_written = static_cast<std::int32_t>(points.size());
        return TG_OK;
    } catch (...) {
        return TG_ERR_INTERNAL;
    }
}

}  // extern "C"
