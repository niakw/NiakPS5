#include "../launch_policy.h"
#include <assert.h>
#include <string.h>
static unsigned system_calls=0,lnc_calls=0;
static int system_value=0,lnc_value=0;
static int expected_user=0x1234;
static int call_system(const char *title,const char **args,NiakLaunchContext *ctx) {
    ++system_calls;
    assert(title && strcmp(title,"PPSA99386")==0 && args==0);
    assert(ctx && ctx->structsize==sizeof(*ctx));
    assert(ctx->user_id==(unsigned)expected_user);
    assert(ctx->app_opt==0 && ctx->crash_report==0 && ctx->check_flag==0);
    return system_value;
}
static int call_lnc(const char *title,const char **args,NiakLaunchContext *ctx) {
    ++lnc_calls;
    assert(title && strcmp(title,"PPSA99386")==0 && args==0);
    assert(ctx && ctx->structsize==sizeof(*ctx));
    assert(ctx->user_id==(unsigned)expected_user);
    return lnc_value;
}
int main(void) {
    NiakLaunchResult r=niak_launch_with_fallback(
        "PPSA99386",expected_user,call_system,call_lnc);
    assert(r.result==0 && r.method==1 && system_calls==1 && lnc_calls==0);
    system_value=(int)0x80940005u;lnc_value=0x60010001;
    r=niak_launch_with_fallback("PPSA99386",expected_user,
                                call_system,call_lnc);
    assert(r.result==0 && r.method==2 && r.lnc_rc==lnc_value);
    assert(system_calls==2 && lnc_calls==1);
    lnc_value=0;
    r=niak_launch_with_fallback("PPSA99386",expected_user,
                                call_system,call_lnc);
    assert(r.method==0 && r.result<0 && r.lnc_rc==0);
    lnc_value=(int)0x80940031u;
    r=niak_launch_with_fallback("PPSA99386",expected_user,
                                call_system,call_lnc);
    assert((unsigned)r.result==0x80940031u && r.method==0);
    assert(lnc_calls==3);
    system_value=(int)0x80940031u;
    r=niak_launch_with_fallback("PPSA99386",expected_user,
                                call_system,call_lnc);
    assert((unsigned)r.result==0x80940031u && r.method==0);
    assert(lnc_calls==3); /* never retry 'not installed' with LncUtil */
    unsigned before=system_calls;
    r=niak_launch_with_fallback("PPSA99386",-1,call_system,call_lnc);
    assert(r.method==0 && system_calls==before);
    r=niak_launch_with_fallback(0,expected_user,call_system,call_lnc);
    assert(r.method==0 && system_calls==before);
    return 0;
}
