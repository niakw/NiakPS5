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
static inline int niak_json_hex4(const char **start,const char *end,
                                 unsigned *value) {
 if(!start||!*start||!value||end-*start<4)return 0;
 unsigned cp=0;
 for(unsigned i=0;i<4;++i) {
  const char c=(*start)[i];
  const unsigned digit=(c>='0'&&c<='9')?(unsigned)(c-'0'):
      (c>='a'&&c<='f')?(unsigned)(c-'a'+10):
      (c>='A'&&c<='F')?(unsigned)(c-'A'+10):16u;
  if(digit>15u)return 0;
  cp=(cp<<4u)|digit;
 }
 *start+=4;
 *value=cp;
 return 1;
}
/* JSON can contain raw UTF-8 or escaped Unicode. Preserve valid UTF-8
 * byte-for-byte: interpreting each byte as a code point mangles French names.
 */
static inline int niak_json_title_value(const char *value,
                                         char *out,size_t cap) {
 if(!value||!out||cap<2||*value!='"')return 0;
 const char *end=niak_json_string_end(value);
 if(!end)return 0;
 const char *limit=end-1;
 size_t n=0;
 for(const char *p=value+1;p<limit;++p) {
  unsigned cp=(unsigned char)*p;
  if(cp>=0x80u) {
   const unsigned char lead=(unsigned char)*p;
   unsigned bytes=0;
   if(lead>=0xC2u&&lead<=0xDFu)bytes=2;
   else if(lead>=0xE0u&&lead<=0xEFu)bytes=3;
   else if(lead>=0xF0u&&lead<=0xF4u)bytes=4;
   else return 0;
   if(limit-p<(ptrdiff_t)bytes || n+bytes>=cap)return 0;
   const unsigned char *part=(const unsigned char *)p;
   for(unsigned j=1;j<bytes;++j)
    if((part[j]&0xC0u)!=0x80u)return 0;
   if((lead==0xE0u&&part[1]<0xA0u)||
      (lead==0xEDu&&part[1]>=0xA0u)||
      (lead==0xF0u&&part[1]<0x90u)||
      (lead==0xF4u&&part[1]>=0x90u))return 0;
   memcpy(out+n,p,bytes);
   n+=bytes;
   p+=bytes-1;
   continue;
  }
  if(cp=='\\') {
   if(++p>=limit)return 0;
   if(*p=='u') {
    const char *digits=p+1;
    if(!niak_json_hex4(&digits,limit,&cp))return 0;
    p=digits-1;
    if(cp>=0xD800u&&cp<=0xDBFFu) {
     if(limit-p<7 || p[1]!='\\' || p[2]!='u')return 0;
     const char *low=p+3;
     unsigned lo=0;
     if(!niak_json_hex4(&low,limit,&lo)||lo<0xDC00u||lo>0xDFFFu)
      return 0;
     cp=0x10000u+((cp-0xD800u)<<10u)+(lo-0xDC00u);
     p=low-1;
    } else if(cp>=0xDC00u&&cp<=0xDFFFu)return 0;
   } else {
    switch(*p) {
     case '"':cp='"';break;
     case '\\':cp='\\';break;
     case '/':cp='/';break;
     case 'n':case 'r':case 't':case 'b':case 'f':cp=' ';break;
     default:return 0;
    }
   }
  }
  if(cp<32u||cp==127u||cp>0x10FFFFu)return 0;
  const unsigned bytes=cp<0x80u?1u:cp<0x800u?2u:cp<0x10000u?3u:4u;
  if(n+bytes>=cap)return 0;
  if(bytes==1)out[n++]=(char)cp;
  else if(bytes==2) {
   out[n++]=(char)(0xC0u|(cp>>6u));
   out[n++]=(char)(0x80u|(cp&63u));
  } else if(bytes==3) {
   out[n++]=(char)(0xE0u|(cp>>12u));
   out[n++]=(char)(0x80u|((cp>>6u)&63u));
   out[n++]=(char)(0x80u|(cp&63u));
  } else {
   out[n++]=(char)(0xF0u|(cp>>18u));
   out[n++]=(char)(0x80u|((cp>>12u)&63u));
   out[n++]=(char)(0x80u|((cp>>6u)&63u));
   out[n++]=(char)(0x80u|(cp&63u));
  }
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
