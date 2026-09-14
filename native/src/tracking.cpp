#include "trugrade/tracking.hpp"

#include <cmath>
#include <cstddef>

namespace trugrade {
namespace {

/// Never let a zero interval divide: two detections can share a timestamp when
/// frames were extracted faster than the source's millisecond resolution.
constexpr double kMinElapsedSeconds = 1e-6;

}  // namespace

ByteTracker::ByteTracker(double high_threshold, double low_threshold, double match_iou,
                         std::int32_t max_lost_frames) noexcept
    : high_threshold_(high_threshold),
      low_threshold_(low_threshold),
      match_iou_(match_iou),
      max_lost_frames_(max_lost_frames) {}

void ByteTracker::associate(std::span<const Detection> detections, std::int32_t frame,
                            std::int64_t timestamp_ms, std::vector<bool>& claimed,
                            std::vector<TrackPoint>& output) {
    claimed.resize(tracks_.size(), false);

    for (const Detection& detection : detections) {
        std::size_t best_index = 0;
        double best_score = 0.0;
        bool matched = false;

        // Strictly-greater keeps the first of any tied pair, which is what
        // max() over an insertion-ordered dict did.
        for (std::size_t index = 0; index < tracks_.size(); ++index) {
            if (claimed[index] || frame - tracks_[index].last_frame > max_lost_frames_) {
                continue;
            }
            const double score = iou(tracks_[index].bbox, detection.bbox);
            if (!matched || score > best_score) {
                best_index = index;
                best_score = score;
                matched = true;
            }
        }

        if (!matched || best_score < match_iou_) {
            tracks_.push_back(Track{
                .track_id = next_id_++,
                .bbox = detection.bbox,
                .last_frame = frame,
                .last_timestamp_ms = timestamp_ms,
                .has_history = false,
            });
            claimed.resize(tracks_.size(), false);
            best_index = tracks_.size() - 1;
        }

        Track& track = tracks_[best_index];

        // Displacement is measured against the box the track held coming in, so
        // this has to be read before the track is moved onto the new detection.
        const double previous_x = track.bbox.center_x();
        const double previous_y = track.bbox.center_y();
        const double center_x = detection.bbox.center_x();
        const double center_y = detection.bbox.center_y();

        double velocity_x = 0.0;
        double velocity_y = 0.0;
        if (track.has_history) {
            double elapsed = static_cast<double>(timestamp_ms - track.last_timestamp_ms) / 1000.0;
            if (elapsed < kMinElapsedSeconds) {
                elapsed = kMinElapsedSeconds;
            }
            velocity_x = (center_x - previous_x) / elapsed;
            velocity_y = (center_y - previous_y) / elapsed;
        }

        track.bbox = detection.bbox;
        track.last_frame = frame;
        track.last_timestamp_ms = timestamp_ms;
        track.has_history = true;
        claimed[best_index] = true;

        output.push_back(TrackPoint{
            .track_id = track.track_id,
            .center_x = center_x,
            .center_y = center_y,
            .velocity_x = velocity_x,
            .velocity_y = velocity_y,
            .speed_px = std::hypot(velocity_x, velocity_y),
            .direction = std::atan2(velocity_y, velocity_x) * 180.0 / M_PI,
        });
    }
}

std::vector<TrackPoint> ByteTracker::update(std::span<const Detection> detections,
                                            std::int32_t frame, std::int64_t timestamp_ms) {
    std::vector<Detection> high;
    std::vector<Detection> low;
    high.reserve(detections.size());
    low.reserve(detections.size());

    for (const Detection& detection : detections) {
        if (detection.confidence < low_threshold_) {
            continue;
        }
        (detection.confidence >= high_threshold_ ? high : low).push_back(detection);
    }

    std::vector<TrackPoint> output;
    output.reserve(high.size() + low.size());

    // One claim set spans both passes: a weak detection may only pick up a track
    // that no strong detection wanted.
    std::vector<bool> claimed(tracks_.size(), false);
    associate(high, frame, timestamp_ms, claimed, output);
    associate(low, frame, timestamp_ms, claimed, output);
    return output;
}

}  // namespace trugrade
