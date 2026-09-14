// Native self-tests, driven entirely through the public C ABI.
//
// Going through trugrade_core.h rather than the C++ headers means these also
// prove the header is includable from C++ and that the C validation layer is
// wired to the C++ implementation the way the Python binding assumes.
#include "trugrade_core.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

namespace {

int g_failures = 0;

void check(bool condition, const char* what) {
    if (!condition) {
        std::printf("  FAIL: %s\n", what);
        ++g_failures;
    }
}

void check_close(double actual, double expected, const char* what) {
    if (std::fabs(actual - expected) > 1e-9) {
        std::printf("  FAIL: %s (got %.12f, wanted %.12f)\n", what, actual, expected);
        ++g_failures;
    }
}

void test_iou() {
    std::printf("iou\n");
    const tg_bbox a{0, 0, 10, 10};
    const tg_bbox identical{0, 0, 10, 10};
    const tg_bbox disjoint{20, 20, 30, 30};
    const tg_bbox half{5, 0, 15, 10};
    const tg_bbox degenerate{5, 5, 5, 5};

    double value = -1;
    check(tg_iou(&a, &identical, &value) == TG_OK, "identical boxes return TG_OK");
    check_close(value, 1.0, "identical boxes score 1");

    check(tg_iou(&a, &disjoint, &value) == TG_OK, "disjoint boxes return TG_OK");
    check_close(value, 0.0, "disjoint boxes score 0");

    // 50 wide of overlap against a union of 150.
    check(tg_iou(&a, &half, &value) == TG_OK, "half-overlap returns TG_OK");
    check_close(value, 50.0 / 150.0, "half overlap scores 1/3");

    check(tg_iou(&degenerate, &degenerate, &value) == TG_OK, "zero-area box returns TG_OK");
    check_close(value, 0.0, "zero union scores 0 rather than dividing");

    check(tg_iou(nullptr, &a, &value) == TG_ERR_NULL_ARGUMENT, "null box is rejected");
    check(tg_iou(&a, &a, nullptr) == TG_ERR_NULL_ARGUMENT, "null out pointer is rejected");
}

void test_orientation() {
    std::printf("torso orientation\n");
    double degrees = 0;
    // Shoulders directly above hips: the torso axis points along -y, which is
    // -90 degrees in image coordinates where y grows downward.
    check(tg_torso_orientation_deg(100, 50, 100, 150, &degrees) == TG_OK, "orientation returns TG_OK");
    check_close(degrees, -90.0, "upright torso reads -90 degrees");

    check(tg_torso_orientation_deg(150, 100, 100, 100, &degrees) == TG_OK, "horizontal returns TG_OK");
    check_close(degrees, 0.0, "horizontal torso reads 0 degrees");

    check(tg_torso_orientation_deg(0, 0, 0, 0, nullptr) == TG_ERR_NULL_ARGUMENT, "null out is rejected");
}

void test_movement_metrics() {
    std::printf("movement metrics\n");
    tg_movement_metrics metrics{};

    check(tg_movement_metrics_compute(nullptr, 0, &metrics) == TG_ERR_INSUFFICIENT_POINTS,
          "an empty track is insufficient, not a null-argument error");
    check(tg_movement_metrics_compute(nullptr, 1, &metrics) == TG_ERR_INSUFFICIENT_POINTS,
          "a single point is insufficient");
    check(tg_movement_metrics_compute(nullptr, 2, &metrics) == TG_ERR_NULL_ARGUMENT,
          "a null buffer with a real count is rejected");
    check(tg_movement_metrics_compute(nullptr, -1, &metrics) == TG_ERR_INVALID_COUNT,
          "a negative count is rejected");

    // Two points one second apart: 10px right, speed rising 4 -> 10.
    const std::vector<tg_position> positions{
        {0.0, 0.0, 0, 4.0, 0.0, 0.9},
        {10.0, 0.0, 1000, 10.0, 90.0, 0.7},
    };
    check(tg_movement_metrics_compute(positions.data(), 2, &metrics) == TG_OK, "two points compute");
    check_close(metrics.max_speed_px, 10.0, "max speed is the larger sample");
    check_close(metrics.max_acceleration_px_s2, 6.0, "acceleration is 6 px/s^2");
    check_close(metrics.max_deceleration_px_s2, 6.0, "with one sample both extremes are that sample");
    check_close(metrics.direction_change_deg, 90.0, "direction spans 90 degrees");
    check_close(metrics.displacement_px, 10.0, "displacement is 10px");
    check_close(metrics.confidence, 0.8, "confidence is the mean");

    // Two points sharing a timestamp contribute no acceleration sample.
    const std::vector<tg_position> simultaneous{
        {0.0, 0.0, 500, 4.0, 0.0, 1.0},
        {3.0, 4.0, 500, 10.0, 0.0, 1.0},
    };
    check(tg_movement_metrics_compute(simultaneous.data(), 2, &metrics) == TG_OK, "simultaneous points compute");
    check_close(metrics.max_acceleration_px_s2, 0.0, "no interval means no acceleration");
    check_close(metrics.max_deceleration_px_s2, 0.0, "no interval means no deceleration");
    check_close(metrics.displacement_px, 5.0, "displacement still measures 3-4-5");
}

void test_tracker() {
    std::printf("tracker\n");
    tg_tracker* tracker = tg_tracker_create(0.5, 0.1, 0.3, 30);
    check(tracker != nullptr, "tracker is created");

    std::vector<tg_track_point> points(4);
    std::int32_t written = -1;

    // Frame 0: one strong detection opens a track with no velocity yet.
    const std::vector<tg_detection> first{{{0, 0, 10, 20}, 0.9}};
    check(tg_tracker_update(tracker, first.data(), 1, 0, 0, points.data(), 4, &written) == TG_OK,
          "first frame associates");
    check(written == 1, "one detection yields one point");
    check(points[0].track_id == 1, "ids start at 1");
    check_close(points[0].center_x, 5.0, "centre x is the box midpoint");
    check_close(points[0].center_y, 10.0, "centre y is the box midpoint");
    check_close(points[0].speed_px, 0.0, "a track's first sighting has no speed");

    // Frame 1, 100ms later, box shifted 2px right: same track, real velocity.
    const std::vector<tg_detection> second{{{2, 0, 12, 20}, 0.9}};
    check(tg_tracker_update(tracker, second.data(), 1, 1, 100, points.data(), 4, &written) == TG_OK,
          "second frame associates");
    check(written == 1, "still one point");
    check(points[0].track_id == 1, "the overlapping box keeps its track");
    check_close(points[0].velocity_x, 20.0, "2px over 0.1s is 20px/s");
    check_close(points[0].velocity_y, 0.0, "no vertical motion");
    check_close(points[0].direction, 0.0, "moving right reads 0 degrees");

    // A box nowhere near the track opens a second one.
    const std::vector<tg_detection> elsewhere{{{500, 500, 510, 520}, 0.9}};
    check(tg_tracker_update(tracker, elsewhere.data(), 1, 2, 200, points.data(), 4, &written) == TG_OK,
          "third frame associates");
    check(points[0].track_id == 2, "a non-overlapping box opens a new track");

    // Below the low threshold the detection is dropped entirely.
    const std::vector<tg_detection> faint{{{2, 0, 12, 20}, 0.05}};
    check(tg_tracker_update(tracker, faint.data(), 1, 3, 300, points.data(), 4, &written) == TG_OK,
          "faint frame associates");
    check(written == 0, "a detection under the low threshold is discarded");

    check(tg_tracker_update(tracker, first.data(), 1, 4, 400, points.data(), 0, &written)
              == TG_ERR_BUFFER_TOO_SMALL,
          "a buffer smaller than the detection count is refused");
    check(tg_tracker_update(nullptr, first.data(), 1, 4, 400, points.data(), 4, &written)
              == TG_ERR_NULL_ARGUMENT,
          "a null tracker is rejected");

    tg_tracker_destroy(tracker);
    tg_tracker_destroy(nullptr);  // must be a no-op, like free()
}

void test_version() {
    std::printf("version\n");
    check(tg_abi_version() == TG_ABI_VERSION, "the library reports the header's ABI version");
    check(tg_version_string() != nullptr, "a version string is available");
}

}  // namespace

int main() {
    test_version();
    test_iou();
    test_orientation();
    test_movement_metrics();
    test_tracker();

    if (g_failures > 0) {
        std::printf("\n%d check(s) failed\n", g_failures);
        return EXIT_FAILURE;
    }
    std::printf("\nall native checks passed\n");
    return EXIT_SUCCESS;
}
