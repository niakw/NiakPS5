/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef NIAKPS5_UI_MOTION_H
#define NIAKPS5_UI_MOTION_H
#include <stdint.h>
typedef struct {int direction; uint32_t started_ms; uint32_t last_step_ms; unsigned repeats;} NiakNavRepeat;
/* 1 for navigation step; 0 for no step. direction -1/0/+1. */
int niak_nav_tick(NiakNavRepeat *state, int direction, uint32_t now_ms);
/* Frame-rate-independent ease, clamped to avoid extrapolation after stalls. */
float niak_ease(float current, float target, float dt_seconds, float response);
#endif
