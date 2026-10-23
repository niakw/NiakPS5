/* SPDX-License-Identifier: GPL-3.0-or-later
 * Classifies the latest PS5 launch result in a bounded, read-only log buffer.
 * SystemService can be refused with 0x80940005 while LncUtil succeeds.
 * This helper never confuses that successful fallback with a failed launch.
 */
#ifndef NIAK_LAUNCH_LOG_STATUS_H
#define NIAK_LAUNCH_LOG_STATUS_H
#include <string.h>

typedef enum {
    NIAK_LAUNCH_LOG_NO_PAYLOAD=0,
    NIAK_LAUNCH_LOG_NO_ATTEMPT,
    NIAK_LAUNCH_LOG_SYSTEM_OK,
    NIAK_LAUNCH_LOG_LNC_OK,
    NIAK_LAUNCH_LOG_SYSTEM_FAILED,
    NIAK_LAUNCH_LOG_LNC_FAILED
} NiakLaunchLogStatus;

static inline NiakLaunchLogStatus niak_last_launch_result(const char *buffer) {
    if(!buffer)return NIAK_LAUNCH_LOG_NO_PAYLOAD;
    const char *begin=0;
    for(const char *p=buffer;
        (p=strstr(p,"NiakPS5 optional autostart start"))!=0;++p)
        begin=p;
    if(!begin)return NIAK_LAUNCH_LOG_NO_PAYLOAD;
    const char *latest=0;
    for(const char *p=begin;
        (p=strstr(p,"sceSystemServiceLaunchApp rc="))!=0;++p)
        latest=p;
    if(!latest)return NIAK_LAUNCH_LOG_NO_ATTEMPT;
    if(strncmp(latest,"sceSystemServiceLaunchApp rc=0x00000000",
               sizeof("sceSystemServiceLaunchApp rc=0x00000000")-1)==0)
        return NIAK_LAUNCH_LOG_SYSTEM_OK;
    const char *accepted=strstr(latest,"sceLncUtilLaunchApp accepted app id rc=");
    const char *refused=strstr(latest,"sceLncUtilLaunchApp refused rc=");
    const char *invalid=strstr(latest,"sceLncUtilLaunchApp returned invalid app id rc=");
    if(accepted && (!refused || accepted>refused) &&
       (!invalid || accepted>invalid))return NIAK_LAUNCH_LOG_LNC_OK;
    if(refused || invalid)return NIAK_LAUNCH_LOG_LNC_FAILED;
    return NIAK_LAUNCH_LOG_SYSTEM_FAILED;
}
#endif
