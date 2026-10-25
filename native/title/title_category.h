/* SPDX-License-Identifier: GPL-3.0-or-later
 * Fail closed: allow only a top-level, unique, correctly formatted
 * applicationCategoryType in an installed PS5 param.json.
 * Strings, nested metadata and duplicate keys must not authorize NPXS apps.
 */
#ifndef NIAK_TITLE_CATEGORY_H
#define NIAK_TITLE_CATEGORY_H
#include <ctype.h>
#include <stddef.h>
#include <string.h>

static inline const char *niak_json_space(const char *p) {
    while(*p && isspace((unsigned char)*p))++p;
    return p;
}
static inline const char *niak_json_string_end(const char *p) {
    if(*p++!='"')return NULL;
    while(*p) {
        if((unsigned char)*p<32u)return NULL;
        if(*p=='"')return p+1;
        if(*p=='\\') {
            ++p;
            if(!*p)return NULL;
        }
        ++p;
    }
    return NULL;
}
/* Skip an arbitrary non-category value without treating an inner object's
 * applicationCategoryType as a top-level property. A small stack rejects
 * unbalanced nested structures, and the caller checks the next delimiter. */
static inline const char *niak_json_skip_value(const char *p) {
    const char *start=p;
    char closing[32];
    unsigned depth=0;
    while(*p) {
        if(*p=='"') {
            p=niak_json_string_end(p);
            if(!p)return NULL;
            continue;
        }
        if(*p=='{' || *p=='[') {
            if(depth==sizeof(closing))return NULL;
            closing[depth++]=(*p=='{' ? '}' : ']');
            ++p;
            continue;
        }
        if(*p=='}' || *p==']') {
            if(!depth) {
                if(*p=='}')break;
                return NULL;
            }
            if(closing[depth-1]!=*p)return NULL;
            --depth;++p;
            continue;
        }
        if(*p==',' && !depth)break;
        ++p;
    }
    return depth==0 && niak_json_space(start)!=p?p:NULL;
}
static inline int niak_installed_category_for_title(
    const char *json,const char *expected_title) {
    static const char key[]="applicationCategoryType";
    static const char title_key[]="titleId";
    if(!json)return 0;
    const char *p=niak_json_space(json);
    if(*p++!='{')return 0;
    int found=0,category=0,found_title=0;
    for(;;) {
        p=niak_json_space(p);
        if(*p=='}') {
            p=niak_json_space(p+1);
            return !*p && found ? category : 0;
        }
        if(*p!='"')return 0;
        const char *begin=p+1;
        const char *end=niak_json_string_end(p);
        if(!end)return 0;
        const size_t key_len=(size_t)((end-1)-begin);
        const int is_category=key_len==sizeof(key)-1 &&
                              memcmp(begin,key,sizeof(key)-1)==0;
        const int is_title=key_len==sizeof(title_key)-1 &&
                            memcmp(begin,title_key,sizeof(title_key)-1)==0;
        p=niak_json_space(end);
        if(*p++!=':')return 0;
        p=niak_json_space(p);
        if(is_category) {
            if(found++)return 0; // duplicate, possibly contradictory key
            const int quoted=*p=='"';
            if(quoted)++p;
            unsigned value=0,digits=0;
            while(*p>='0'&&*p<='9') {
                if(++digits>6)return 0;
                value=value*10u+(unsigned)(*p-'0');
                ++p;
            }
            if(!digits)return 0;
            if(quoted) {
                if(*p++!='"')return 0;
            }
            p=niak_json_space(p);
            category=value==0u?1:(value==65536u||value==65792u||value==66048u)?2:0;
        } else if(is_title && expected_title) {
            if(found_title++)return 0; // conflicting title identity
            const char *end_value=niak_json_string_end(p);
            if(!end_value)return 0;
            const size_t length=(size_t)(end_value-p-2);
            if(length!=9 || memcmp(p+1,expected_title,9)!=0)return 0;
            p=niak_json_space(end_value);
        } else {
            p=niak_json_skip_value(p);
            if(!p)return 0;
            p=niak_json_space(p);
        }
        if(*p==',') {
            p=niak_json_space(p+1);
            if(*p=='}')return 0; // invalid trailing comma
            continue;
        }
        if(*p!='}')return 0;
    }
}
/* Only validated media manifests authorize NPXS shell-facing titles. */
static inline int niak_is_installed_media_category_for_title(
    const char *json,const char *expected_title) {
 return niak_installed_category_for_title(json,expected_title)==2;
}
/* Legacy category-only wrapper, used by standalone parser tests. */
static inline int niak_is_installed_media_category(const char *json) {
    return niak_is_installed_media_category_for_title(json,NULL);
}
#endif
