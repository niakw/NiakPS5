/* SPDX-License-Identifier: GPL-3.0-or-later
 * Fail-closed detection of Sony-installed media app categories.
 * The SDK param.json may represent applicationCategoryType as an integer
 * or a quoted decimal string. NPXS system/service categories stay blocked.
 */
#ifndef NIAK_TITLE_CATEGORY_H
#define NIAK_TITLE_CATEGORY_H
#include <ctype.h>
#include <string.h>

static inline int niak_is_installed_media_category(const char *json) {
    static const char key[]="\"applicationCategoryType\"";
    if(!json)return 0;
    const char *p=strstr(json,key);
    if(!p)return 0;
    p+=sizeof(key)-1;
    while(isspace((unsigned char)*p))++p;
    if(*p++!=':')return 0;
    while(isspace((unsigned char)*p))++p;
    const int quoted=*p=='"';
    if(quoted)++p;
    unsigned value=0,digits=0;
    while(*p>='0' && *p<='9') {
        if(++digits>6)return 0;
        value=value*10u+(unsigned)(*p-'0');
        ++p;
    }
    if(!digits)return 0;
    if(quoted) {
        if(*p++!='"')return 0;
    }
    if(*p!='\0' && *p!=',' && *p!='}' &&
       !isspace((unsigned char)*p))return 0;
    return value==65536u||value==65792u||value==66048u;
}
#endif
