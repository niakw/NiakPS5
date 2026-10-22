/* SPDX-License-Identifier: GPL-3.0-or-later
 * One-shot "return to Niak" gate, inspired by NiakTV HomeRedirectGate.
 * PS button is NOT visible to payloads: observe only bigapp lifecycle.
 * App IDs <= -1 are errors, never interpreted as Sony Home.
 */
#ifndef NIAK_REDIRECT_GATE_H
#define NIAK_REDIRECT_GATE_H
#include <stdint.h>
typedef struct {
  int own_app;
  int previous_game;
  uint64_t home_since_ms;
  unsigned engaged;
  unsigned in_home;
  unsigned completed;
} NiakRedirectGate;
static inline void niak_redirect_init(NiakRedirectGate *gate,int own_app) {
 gate->own_app=own_app;gate->previous_game=0;gate->home_since_ms=0;
 gate->engaged=0;gate->in_home=0;gate->completed=0;
}
/* Returns 1 exactly once after observing the launched bigapp and a REAL
 * >=10 seconds of uninterrupted Sony Home, on a monotonic clock.
 * Fast successive broker requests must never shorten this delay. */
static inline int niak_redirect_tick(NiakRedirectGate *g,int running_app,
                                      uint64_t now_ms) {
 if(!g || g->completed || !now_ms)return 0;
 if(running_app<0) {
   g->in_home=0; // Unknown observation interrupts the stable-home period.
   return 0;
 }
 if(running_app==g->own_app) {
   g->previous_game=0;g->in_home=0;g->engaged=0;
   return 0;
 }
 if(running_app>0) {
   g->previous_game=running_app;g->engaged=1;g->in_home=0;
   return 0;
 }
 if(!g->engaged)return 0;
 if(!g->in_home || now_ms<g->home_since_ms) {
   g->in_home=1;g->home_since_ms=now_ms;
   return 0;
 }
 if(now_ms-g->home_since_ms<10000u)return 0;
 g->completed=1;
 return 1;
}
/* Arm only for an explicit successful NiakPS5 launch request, including
 * when the user opened the title manually after an unsuccessful autostart.
 * Discovering an arbitrary application at boot never arms the gate. */
static inline int niak_redirect_arm_after_launch(
    NiakRedirectGate *gate,int resume_enabled,
    int source_app,int launch_rc) {
 if(!gate || !resume_enabled ||
    source_app<=0 || launch_rc!=0)return 0;
 niak_redirect_init(gate,source_app);
 return 1;
}
/* If the active PS5 user changed while a game was running, cancelling the
 * optional return is safer than bringing a different user's Niak home forward. */
static inline int niak_redirect_same_user(int original,int current) {
 return original>=0 && original==current;
}
#endif
