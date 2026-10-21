/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "../ui_motion.h"
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
int main(void){
 NiakNavRepeat nav={0};
 assert(niak_nav_tick(&nav,1,100)==1);
 assert(niak_nav_tick(&nav,1,150)==0);
 assert(niak_nav_tick(&nav,1,430)==1);
 assert(niak_nav_tick(&nav,1,470)==0);
 assert(niak_nav_tick(&nav,1,550)==1);
 assert(niak_nav_tick(&nav,-1,560)==-1);
 assert(niak_nav_tick(&nav,0,600)==0);
 assert(niak_nav_tick(&nav,1,610)==1);
 /* Wrapped monotonic ticks do not block repeat. */
 nav=(NiakNavRepeat){0};
 assert(niak_nav_tick(&nav,1,UINT32_MAX-150)==1);
 assert(niak_nav_tick(&nav,1,250)==1);
 float v=0.0f;
 for(int i=0;i<100;i++){float next=niak_ease(v,100.0f,1.0f/60.0f,13.0f);assert(next>=v && next<=100.0f);v=next;}
 assert(fabsf(v-100.0f)<0.01f);
 assert(niak_ease(5.0f,7.0f,0.0f,12.0f)==5.0f);
 printf("motion/navigation: OK\n");
 return 0;
}
