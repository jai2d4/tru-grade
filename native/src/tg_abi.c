/*
 * Public ABI entry points - pure C11.
 *
 * Every pointer that arrives from ctypes is checked here before any C++ code
 * sees it. Python can hand us a NULL as easily as a valid buffer (an empty
 * numpy slice, a failed allocation, a bug in a caller), and a null dereference
 * inside the C++ layer would take the whole uvicorn worker down rather than
 * raise something catchable. Failing with a status code keeps a bad call a
 * Python-level exception.
 */
#include "trugrade_core.h"
#include "trugrade_impl.h"

#include <stddef.h>

/* Kept in step with the project version in native/CMakeLists.txt. */
static const char TG_VERSION_STRING[] = "0.1.0";

uint32_t tg_abi_version(void)
{
    return TG_ABI_VERSION;
}

const char *tg_version_string(void)
{
    return TG_VERSION_STRING;
}

tg_status tg_iou(const tg_bbox *a, const tg_bbox *b, double *out_iou)
{
    if (a == NULL || b == NULL || out_iou == NULL) {
        return TG_ERR_NULL_ARGUMENT;
    }
    *out_iou = tg_impl_iou(a, b);
    return TG_OK;
}

tg_status tg_torso_orientation_deg(double shoulder_x, double shoulder_y,
                                   double hip_x, double hip_y, double *out_degrees)
{
    if (out_degrees == NULL) {
        return TG_ERR_NULL_ARGUMENT;
    }
    *out_degrees = tg_impl_torso_orientation_deg(shoulder_x, shoulder_y, hip_x, hip_y);
    return TG_OK;
}

tg_status tg_movement_metrics_compute(const tg_position *positions, int32_t count,
                                      tg_movement_metrics *out_metrics)
{
    if (out_metrics == NULL) {
        return TG_ERR_NULL_ARGUMENT;
    }
    if (count < 0) {
        return TG_ERR_INVALID_COUNT;
    }
    /* A count of 0 or 1 is a legitimate short track, not a caller error, so it
       reports insufficient points even when the pointer is NULL. */
    if (count < 2) {
        return TG_ERR_INSUFFICIENT_POINTS;
    }
    if (positions == NULL) {
        return TG_ERR_NULL_ARGUMENT;
    }
    return tg_impl_movement_metrics(positions, count, out_metrics);
}

tg_tracker *tg_tracker_create(double high_threshold, double low_threshold,
                              double match_iou, int32_t max_lost_frames)
{
    return tg_impl_tracker_create(high_threshold, low_threshold, match_iou, max_lost_frames);
}

void tg_tracker_destroy(tg_tracker *tracker)
{
    /* Mirrors free(): destroying NULL is a no-op, so the Python finaliser does
       not have to guard a tracker whose construction failed. */
    if (tracker == NULL) {
        return;
    }
    tg_impl_tracker_destroy(tracker);
}

tg_status tg_tracker_update(tg_tracker *tracker, const tg_detection *detections, int32_t count,
                            int32_t frame, int64_t timestamp_ms, tg_track_point *out_points,
                            int32_t capacity, int32_t *out_written)
{
    if (tracker == NULL || out_written == NULL) {
        return TG_ERR_NULL_ARGUMENT;
    }
    if (count < 0 || capacity < 0) {
        return TG_ERR_INVALID_COUNT;
    }
    if (count > 0 && detections == NULL) {
        return TG_ERR_NULL_ARGUMENT;
    }
    if (capacity > 0 && out_points == NULL) {
        return TG_ERR_NULL_ARGUMENT;
    }
    /* One detection yields at most one point, so anything short of `count` can
       overflow and is rejected before the association runs. */
    if (capacity < count) {
        return TG_ERR_BUFFER_TOO_SMALL;
    }

    *out_written = 0;
    /* A frame with no detections still advances nothing and allocates nothing;
       short-circuiting keeps that the cheapest possible call. */
    if (count == 0) {
        return TG_OK;
    }
    return tg_impl_tracker_update(tracker, detections, count, frame, timestamp_ms,
                                  out_points, capacity, out_written);
}
