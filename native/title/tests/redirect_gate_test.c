#include "../redirect_gate.h"
#include <assert.h>
int main(void){
 NiakRedirectGate g;
 assert(!niak_redirect_arm_after_launch(&g,0,1,314,0));
 assert(!niak_redirect_arm_after_launch(&g,1,0,314,0));
 assert(!niak_redirect_arm_after_launch(&g,1,1,-1,0));
 assert(!niak_redirect_arm_after_launch(&g,1,1,314,-2));
 assert(niak_redirect_same_user(100,100));
 assert(!niak_redirect_same_user(100,200));
 assert(!niak_redirect_same_user(-1,100));
 assert(niak_redirect_arm_after_launch(&g,1,1,314,0));
 // First launcher, Sony dashboard, no game: never redirect/loop.
 for(int i=0;i<50;++i)assert(!niak_redirect_tick(&g,0));
 assert(!niak_redirect_tick(&g,314));
 // Games running, PS Control Center shown: bigapp still running.
 for(int i=0;i<100;++i)assert(!niak_redirect_tick(&g,21));
 // Unknown error is not a home event.
 for(int i=0;i<15;++i)assert(!niak_redirect_tick(&g,-1));
 // Game exits; five stable polls required (2s cadence, >=10s).
 for(int i=0;i<4;++i)assert(!niak_redirect_tick(&g,0));
 assert(niak_redirect_tick(&g,0));
 for(int i=0;i<30;++i)assert(!niak_redirect_tick(&g,0));
 assert(niak_redirect_arm_after_launch(&g,1,1,314,0));
 niak_redirect_tick(&g,18);
 niak_redirect_tick(&g,0);
 niak_redirect_tick(&g,0);
 // A game came back before grace period: don't redirect.
 assert(!niak_redirect_tick(&g,18));
 for(int i=0;i<4;++i)assert(!niak_redirect_tick(&g,0));
 assert(niak_redirect_tick(&g,0));
 niak_redirect_init(&g,314);
 niak_redirect_tick(&g,20);
 niak_redirect_tick(&g,314);
 for(int i=0;i<20;++i)assert(!niak_redirect_tick(&g,0));
}
