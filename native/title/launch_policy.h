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

/* SystemService can return a NONNEGATIVE app/process identifier (as
 * observed on PS5 with 0x18 and 0x2018), not just zero. Negative values with
 * the high bit set represent errors. Normalize API acceptance to zero for
 * our existing wire protocol, but do not claim the app is fully running.
 * LncUtil also returns a positive app ID on acceptance.
 * The LncUtil fallback is intentionally limited to error 0x80940005.
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
    if(result.system_rc>=0) {
        result.method=1;
        result.result=0; // API accepted; physical launch still unverified.
        return result;
    }
    /* PS5 mounted/fake titles may be refused by SystemService with
     * 0x80940005. Existing PS5 launchers use LncUtil for precisely this
     * case, but the fallback can still fail without title registration.
     */
    if((uint32_t)result.system_rc==0x80940005u && lnc_launch) {
        result.lnc_rc=lnc_launch(title,0,&ctx);
        result.result=result.lnc_rc;
        // LncUtil's success value is an actual positive app ID, not
        // SystemService's zero-on-success convention. An app ID of zero
        // cannot identify a launched process, so fail closed.
        if(result.lnc_rc>0) {
            result.method=2;
            result.result=0;
        } else if(result.lnc_rc==0) {
            result.result=-1; // no valid app ID, do not report success
        }
    }
    return result;
}
#endif
