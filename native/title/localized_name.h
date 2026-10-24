/* SPDX-License-Identifier: GPL-3.0-or-later
 * Source-backed names: use the actual installed PS5 param.json, not a
 * game-name translation service or guessed mappings.
 */
#ifndef NIAK_LOCALIZED_NAME_H
#define NIAK_LOCALIZED_NAME_H
#include <stddef.h>
#include <string.h>
#include "title_category.h"
/* Return a DIRECT key's value; never accidentally enter a nested description
 * or select a string inside an unrelated JSON object. */
static inline const char *niak_json_direct(const char *json,const char *key) {
 if(!json||!key)return NULL;
 const char *p=niak_json_space(json);
 if(*p++!='{')return NULL;
 const size_t wanted=strlen(key);
 for(unsigned count=0;count<512;++count) {
  p=niak_json_space(p);
  if(*p=='}')return NULL;
  const char *end=niak_json_string_end(p);
  if(!end)return NULL;
  const int found=(size_t)(end-p-2)==wanted &&
      memcmp(p+1,key,wanted)==0;
  p=niak_json_space(end);
  if(*p++!=':')return NULL;
  const char *value=niak_json_space(p);
  if(found)return value;
  p=niak_json_skip_value(value);
  if(!p)return NULL;
  p=niak_json_space(p);
  if(*p=='}')return NULL;
  if(*p++!=',')return NULL;
 }
 return NULL;
}
static inline int niak_json_title_value(const char *value,
                                         char *out,size_t cap) {
 if(!value||!out||cap<2||*value!='"')return 0;
 const char *end=niak_json_string_end(value);
 if(!end)return 0;
 size_t n=0;
 for(const char *p=value+1;p<end-1;++p) {
  unsigned cp=(unsigned char)*p;
  if(cp=='\\') {
   if(++p>=end-1)return 0;
   if(*p=='u') {
    cp=0;
    for(int i=0;i<4;++i) {
     if(++p>=end-1)return 0;
     unsigned digit=(*p>='0'&&*p<='9')?(unsigned)(*p-'0'):
       (*p>='a'&&*p<='f')?(unsigned)(*p-'a'+10):
       (*p>='A'&&*p<='F')?(unsigned)(*p-'A'+10):16u;
     if(digit>15)return 0;
     cp=(cp<<4u)|digit;
    }
    if(cp>=0xD800u && cp<=0xDFFFu)return 0;
   } else {
    switch(*p) {
     case '"':cp='"';break;
     case '\\':cp='\\';break;
     case '/':cp='/';break;
     case 'n':case 'r':case 't':cp=' ';break;
     default:return 0;
    }
   }
  }
  if(cp<32u||cp==127u)return 0;
  if(cp<0x80u) {
   if(n+1>=cap)return 0;
   out[n++]=(char)cp;
  } else if(cp<0x800u) {
   if(n+2>=cap)return 0;
   out[n++]=(char)(0xC0u|(cp>>6u));
   out[n++]=(char)(0x80u|(cp&63u));
  } else if(cp<0x10000u) {
   if(n+3>=cap)return 0;
   out[n++]=(char)(0xE0u|(cp>>12u));
   out[n++]=(char)(0x80u|((cp>>6u)&63u));
   out[n++]=(char)(0x80u|(cp&63u));
  } else return 0;
 }
 out[n]=0;
 return n>0;
}
/* FR official manifest display name, EN fallback, never a fake translation. */
static inline int niak_manifest_localized_title(const char *json,
                                                char *out,size_t cap) {
 const char *langs=niak_json_direct(json,"localizedParameters");
 if(!langs)return 0;
 static const char *const codes[]={"fr-FR","fr-CA","fr",
                                    "en-US","en-GB",NULL};
 for(unsigned i=0;codes[i];++i) {
  const char *localized=niak_json_direct(langs,codes[i]);
  const char *title=niak_json_direct(localized,"titleName");
  if(niak_json_title_value(title,out,cap))return 1;
 }
 return 0;
}
#endif
