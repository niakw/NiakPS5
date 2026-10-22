/* SPDX-License-Identifier: GPL-3.0-or-later
 * One-shot "return to Niak" gate, inspired by NiakTV HomeRedirectGate.
 * PS button is NOT visible to payloads: observe only bigapp lifecycle.
 * App IDs <= -1 are errors, never interpreted as Sony Home.
 */
#ifndef NIAK_REDIRECT_GATE_H
#define NIAK_REDIRECT_GATE_H
typedef struct {
  int own_app;
  int previous_game;
  unsigned stable_home_ticks;
  unsigned engaged;
  unsigned completed;
} NiakRedirectGate;
static inline void niak_redirect_init(NiakRedirectGate *gate,int own_app) {
 gate->own_app=own_app;gate->previous_game=0;gate->stable_home_ticks=0;
 gate->engaged=0;gate->completed=0;
}
/* Returns 1 exactly once after observing a genuine different bigapp, followed
 * by >= 5 consecutive empty ticks. Never requests redirect while a game runs.
 */
static inline int niak_redirect_tick(NiakRedirectGate *g,int running_app) {
 if(g->completed || running_app<0)return 0;
 if(running_app==g->own_app) {
   g->previous_game=0;g->stable_home_ticks=0;g->engaged=0;
   return 0;
 }
 if(running_app>0) {
   g->previous_game=running_app;g->engaged=1;g->stable_home_ticks=0;
   return 0;
 }
 if(!g->engaged)return 0;
 if(++g->stable_home_ticks<5)return 0;
 g->completed=1;
 return 1;
}
/* Arm only for a launch that actually succeeded from the Niak home title.
 * In particular, discovering an arbitrary active application at startup
 * must never become the user's automatic return target. */
static inline int niak_redirect_arm_after_launch(
    NiakRedirectGate *gate,int launcher_started,int resume_enabled,
    int source_app,int launch_rc) {
 if(!gate || !launcher_started || !resume_enabled ||
    source_app<=0 || launch_rc!=0)return 0;
 niak_redirect_init(gate,source_app);
 return 1;
}
#endif
