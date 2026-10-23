/* SPDX-License-Identifier: GPL-3.0-or-later
 * Classifies the latest PS5 launch result in a bounded, read-only log buffer.
 * SystemService can be refused with 0x80940005 while LncUtil succeeds.
 * This helper never confuses that successful fallback with a failed launch.
 */
#ifndef NIAK_LAUNCH_LOG_STATUS_H
#define NIAK_LAUNCH_LOG_STATUS_H
#include <string.h>
#include <stdint.h>

typedef enum {
    NIAK_LAUNCH_LOG_NO_PAYLOAD=0,
    NIAK_LAUNCH_LOG_NO_ATTEMPT,
    NIAK_LAUNCH_LOG_SYSTEM_OK,
    NIAK_LAUNCH_LOG_LNC_OK,
    NIAK_LAUNCH_LOG_SYSTEM_FAILED,
    NIAK_LAUNCH_LOG_LNC_FAILED
} NiakLaunchLogStatus;

/* Classify the raw API return without assuming success must equal zero.
 * Require exactly eight hexadecimal digits to avoid accepting truncated
 * or malformed journal lines as evidence of an accepted call.
 */
static inline int niak_launch_log_nonnegative(const char *line) {
    static const char tag[]="sceSystemServiceLaunchApp rc=0x";
    const size_t prefix=sizeof(tag)-1;
    if(!line || strncmp(line,tag,prefix)!=0)return 0;
    uint32_t value=0;
    for(size_t i=0;i<8;++i) {
        const unsigned char c=(unsigned char)line[prefix+i];
        unsigned nibble;
        if(c>='0'&&c<='9')nibble=(unsigned)(c-'0');
        else if(c>='a'&&c<='f')nibble=(unsigned)(c-'a'+10);
        else if(c>='A'&&c<='F')nibble=(unsigned)(c-'A'+10);
        else return 0;
        value=(value<<4)|nibble;
    }
    return (line[prefix+8]=='\n' || line[prefix+8]=='\0') &&
           (value & 0x80000000u)==0;
}

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
    if(niak_launch_log_nonnegative(latest))
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
