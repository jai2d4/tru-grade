/*
 * Internal boundary between the C validation layer (tg_abi.c) and the C++
 * implementation (capi.cpp). Not installed and not part of the public ABI.
 *
 * Every function here may assume its pointers are non-NULL and its counts are
 * non-negative: tg_abi.c has already checked. None of them throw - capi.cpp
 * catches everything and reports TG_ERR_INTERNAL.
 */
#ifndef TRUGRADE_IMPL_H
#define TRUGRADE_IMPL_H

#include "trugrade_core.h"

#ifdef __cplusplus
extern "C" {
#endif

double tg_impl_iou(const tg_bbox *a, const tg_bbox *b);

double tg_impl_torso_orientation_deg(double shoulder_x, double shoulder_y,
                                     double hip_x, double hip_y);

tg_status tg_impl_movement_metrics(const tg_position *positions, int32_t count,
                                   tg_movement_metrics *out_metrics);

tg_tracker *tg_impl_tracker_create(double high_threshold, double low_threshold,
                                   double match_iou, int32_t max_lost_frames);

void tg_impl_tracker_destroy(tg_tracker *tracker);

tg_status tg_impl_tracker_update(tg_tracker *tracker, const tg_detection *detections,
                                 int32_t count, int32_t frame, int64_t timestamp_ms,
                                 tg_track_point *out_points, int32_t capacity,
                                 int32_t *out_written);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* TRUGRADE_IMPL_H */
