/* SPDX-License-Identifier: GPL-3.0-or-later
 * Restricted, owner-initiated PS5 title launch policy.
 * A copied homebrew title can be visible as a folder without being
 * registered with the console's title service. No kernel modification,
 * app installation, process kill or system-process impersonation here.
 */
#ifndef NIAK_PS5_LAUNCH_POLICY_H
#define NIAK_PS5_LAUNCH_POLICY_H
#include <stdint.h>

typedef struct {
    uint32_t structsize;
    uint32_t user_id;
    uint32_t app_opt;
    uint64_t crash_report;
    uint32_t check_flag;
} NiakLaunchContext;
_Static_assert(sizeof(NiakLaunchContext)==32,
               "PS5 launch context must match the LncAppParam ABI");

typedef int (*NiakLaunchFunction)(const char*,const char**,NiakLaunchContext*);
enum { NIAK_LAUNCH_NOT_TRIED = -3 };
typedef struct {
    int result;      /* zero: accepted, negative: raw error */
    int system_rc;   /* raw sceSystemServiceLaunchApp result */
    int lnc_rc;      /* raw sceLncUtilLaunchApp result if called */
    unsigned method; /* 0 failed, 1 system service, 2 LncUtil */
} NiakLaunchResult;

/* SystemService returns 0 on success. LncUtil normally returns a positive
 * app_id on success; the caller's wire protocol needs both normalized to 0.
 * Other SystemService errors are NOT retried by a different API: a missing
 * registration needs installation, not blind elevation.
 */
static inline NiakLaunchResult niak_launch_with_fallback(
    const char *title,int user,NiakLaunchFunction system_launch,
    NiakLaunchFunction lnc_launch) {
    NiakLaunchResult result={NIAK_LAUNCH_NOT_TRIED,
                              NIAK_LAUNCH_NOT_TRIED,
                              NIAK_LAUNCH_NOT_TRIED,0};
    if(!title || user<0 || !system_launch)return result;
    NiakLaunchContext ctx={0};
    ctx.structsize=(uint32_t)sizeof(ctx);
    ctx.user_id=(uint32_t)user;
    result.system_rc=system_launch(title,0,&ctx);
    result.result=result.system_rc;
    if(result.system_rc==0) {
        result.method=1;
        return result;
    }
    /* PS5 mounted/fake titles may be refused by SystemService with
     * 0x80940005. Existing PS5 launchers use LncUtil for precisely this
     * case, but the fallback can still fail without title registration.
     */
    if((uint32_t)result.system_rc==0x80940005u && lnc_launch) {
        result.lnc_rc=lnc_launch(title,0,&ctx);
        result.result=result.lnc_rc;
        if(result.lnc_rc>=0) {
            result.method=2;
            result.result=0;
        }
    }
    return result;
}
#endif
