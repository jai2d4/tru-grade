/*
 * TruGrade native core - public C ABI.
 *
 * This header is plain C11 and is the only surface Python binds to. Everything
 * behind it is C++; nothing C++ leaks through. That split is deliberate:
 *
 *   - no exception may cross this boundary (the C++ bridge swallows them and
 *     returns a tg_status instead),
 *   - no C++ type appears in a signature, so the shared library keeps a stable
 *     ABI across compilers and standard-library versions,
 *   - argument validation lives in C (tg_abi.c) ahead of any C++ call, so a
 *     malformed pointer from ctypes is rejected rather than dereferenced.
 *
 * All geometry is in pixel space. All returned values are UNROUNDED: the Python
 * binding owns rounding so that the native and pure-Python paths cannot drift
 * apart in the last decimal place. See docs/NATIVE_CORE.md.
 */
#ifndef TRUGRADE_CORE_H
#define TRUGRADE_CORE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Bumped only for a breaking change to a struct layout or signature below.
   The Python loader refuses a library that does not report this value. */
#define TG_ABI_VERSION 1u

typedef enum tg_status {
    TG_OK = 0,
    TG_ERR_NULL_ARGUMENT = -1,
    TG_ERR_INVALID_COUNT = -2,
    TG_ERR_INSUFFICIENT_POINTS = -3,
    TG_ERR_BUFFER_TOO_SMALL = -4,
    TG_ERR_INTERNAL = -5
} tg_status;

/* Axis-aligned box: (x1,y1) top-left, (x2,y2) bottom-right. */
typedef struct tg_bbox {
    double x1;
    double y1;
    double x2;
    double y2;
} tg_bbox;

typedef struct tg_detection {
    tg_bbox bbox;
    double confidence;
} tg_detection;

typedef struct tg_track_point {
    int32_t track_id;
    double center_x;
    double center_y;
    double velocity_x;
    double velocity_y;
    double speed_px;
    double direction;
} tg_track_point;

typedef struct tg_position {
    double center_x;
    double center_y;
    int64_t timestamp_ms;
    double speed_px;
    double direction;
    double confidence;
} tg_position;

typedef struct tg_movement_metrics {
    double max_speed_px;
    double max_acceleration_px_s2;
    double max_deceleration_px_s2;
    double direction_change_deg;
    double displacement_px;
    double confidence;
} tg_movement_metrics;

/* Opaque tracker handle. Not thread-safe: one tracker belongs to one video. */
typedef struct tg_tracker tg_tracker;

uint32_t tg_abi_version(void);
const char *tg_version_string(void);

tg_status tg_iou(const tg_bbox *a, const tg_bbox *b, double *out_iou);

tg_status tg_torso_orientation_deg(double shoulder_x, double shoulder_y,
                                   double hip_x, double hip_y, double *out_degrees);

/* Returns TG_ERR_INSUFFICIENT_POINTS for count < 2 so the caller can report an
   unknown result rather than a measured zero. */
tg_status tg_movement_metrics_compute(const tg_position *positions, int32_t count,
                                      tg_movement_metrics *out_metrics);

tg_tracker *tg_tracker_create(double high_threshold, double low_threshold,
                              double match_iou, int32_t max_lost_frames);

void tg_tracker_destroy(tg_tracker *tracker);

/* Associates one frame. At most `count` points are produced (one per detection
   that clears the low threshold), so a buffer of `count` entries always fits.
   Points are ordered high-confidence pass first. */
tg_status tg_tracker_update(tg_tracker *tracker, const tg_detection *detections, int32_t count,
                            int32_t frame, int64_t timestamp_ms, tg_track_point *out_points,
                            int32_t capacity, int32_t *out_written);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TRUGRADE_CORE_H */
