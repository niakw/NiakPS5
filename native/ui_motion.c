/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "ui_motion.h"
#include <math.h>
int niak_nav_tick(NiakNavRepeat *s,int direction,uint32_t now){
 if(!s) return 0;
 if(direction<-1)direction=-1;
 if(direction>1)direction=1;
 if(direction==0){s->direction=0;s->repeats=0;return 0;}
 if(s->direction!=direction){s->direction=direction;s->started_ms=now;s->last_step_ms=now;s->repeats=0;return direction;}
 uint32_t elapsed=now-s->started_ms;
 uint32_t since=now-s->last_step_ms;
 uint32_t interval=s->repeats>=6?55u:115u;
 if(elapsed<330u || (s->repeats>0 && since<interval))return 0;
 s->last_step_ms=now;s->repeats++;
 return direction;
}
float niak_ease(float value,float target,float dt,float response){
 if(!isfinite(value)||!isfinite(target))return target;
 if(!isfinite(dt)||dt<=0.0f)return value;
 if(dt>0.05f)dt=0.05f;
 if(!isfinite(response)||response<=0.0f)return target;
 return value+(target-value)*(1.0f-expf(-response*dt));
}
