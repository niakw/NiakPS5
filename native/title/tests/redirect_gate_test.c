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
 // Running own UI and Sony Home with no intervening game never returns.
 for(unsigned i=0;i<50;++i)
     assert(!niak_redirect_tick(&g,0,1000u+i));
 assert(!niak_redirect_tick(&g,314,2000));
 // A real game engages the gate.
 for(unsigned i=0;i<100;++i)
     assert(!niak_redirect_tick(&g,21,3000u+i));
 // Empty observations 200ms apart must NOT count as ten seconds.
 for(unsigned i=0;i<100;++i)
     assert(!niak_redirect_tick(&g,0,3200u+i*2));
 assert(!niak_redirect_tick(&g,0,13199));
 assert(niak_redirect_tick(&g,0,13200));
 for(unsigned i=0;i<30;++i)
     assert(!niak_redirect_tick(&g,0,16000u+i));
 // Disconnected/unknown observations reset the stable-home timer.
 assert(niak_redirect_arm_after_launch(&g,1,1,314,0));
 assert(!niak_redirect_tick(&g,18,20000));
 assert(!niak_redirect_tick(&g,0,21000));
 assert(!niak_redirect_tick(&g,-1,30000));
 assert(!niak_redirect_tick(&g,0,31000));
 assert(!niak_redirect_tick(&g,0,40000));
 assert(niak_redirect_tick(&g,0,41000));
 // Another title resumes before grace period; the countdown restarts.
 assert(niak_redirect_arm_after_launch(&g,1,1,314,0));
 assert(!niak_redirect_tick(&g,18,50000));
 assert(!niak_redirect_tick(&g,0,51000));
 assert(!niak_redirect_tick(&g,0,60999));
 assert(!niak_redirect_tick(&g,18,61000));
 assert(!niak_redirect_tick(&g,0,62000));
 assert(!niak_redirect_tick(&g,0,71999));
 assert(niak_redirect_tick(&g,0,72000));
 // Clock failures and resets cannot trigger an early redirect.
 assert(niak_redirect_arm_after_launch(&g,1,1,314,0));
 assert(!niak_redirect_tick(&g,18,80000));
 assert(!niak_redirect_tick(&g,0,82000));
 assert(!niak_redirect_tick(&g,0,0));
 assert(!niak_redirect_tick(&g,0,1000));
 assert(!niak_redirect_tick(&g,0,10999));
 assert(niak_redirect_tick(&g,0,11000));
 // Returning to our own title cancels a pending game-exit redirect.
 niak_redirect_init(&g,314);
 niak_redirect_tick(&g,20,30000);
 niak_redirect_tick(&g,314,31000);
 for(unsigned i=0;i<20;++i)
     assert(!niak_redirect_tick(&g,0,42000u+i*1000));
 return 0;
}
