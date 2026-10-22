/* SPDX-License-Identifier: GPL-3.0-or-later
 * Bounded framing for ShadowMountPlus loopback JSON replies.
 * Valid Content-Length replies complete without waiting for socket EOF.
 * The API's close-delimited legacy replies are still supported.
 */
#ifndef NIAK_SHADOWMOUNT_HTTP_H
#define NIAK_SHADOWMOUNT_HTTP_H
#include <stddef.h>
#include <string.h>
#include <strings.h>
#define NIAK_SHADOWMOUNT_HTTP_CAP (2U*1024U*1024U)
#define NIAK_SHADOWMOUNT_HEADER_CAP 8192U

/* -1 rejected, 0 need more data, 1 complete.
 * wire points to cap+1 allocated bytes and is NUL-terminated by caller.
 * body is a pointer within wire, suitable for JSON parser after success. */
static inline int niak_shadowmount_http_json(
  char *wire,size_t size,int eof,const char **body) {
 if(!wire||!body||size>NIAK_SHADOWMOUNT_HTTP_CAP)return -1;
 wire[size]=0;
 char *sep=strstr(wire,"\r\n\r\n");
 if(!sep)return (size>NIAK_SHADOWMOUNT_HEADER_CAP||eof)?-1:0;
 size_t header_bytes=(size_t)(sep-wire)+4u;
 if(header_bytes>NIAK_SHADOWMOUNT_HEADER_CAP ||
    (strncmp(wire,"HTTP/1.1 200 ",13)!=0 &&
     strncmp(wire,"HTTP/1.0 200 ",13)!=0))return -1;
 int known_length=0;
 size_t length=0;
 char *line=strstr(wire,"\r\n");
 if(!line||line>sep)return -1;
 line+=2;
 while(line<sep) {
  char *end=strstr(line,"\r\n");
  if(!end||end>sep)return -1;
  const size_t bytes=(size_t)(end-line);
  if(bytes>=15u && strncasecmp(line,"Content-Length:",15)==0) {
   const char *number=line+15;
   while(number<end&&(*number==' '||*number=='\t'))++number;
   if(number==end)return -1;
   size_t value=0;
   int digits=0;
   while(number<end&&*number>='0'&&*number<='9') {
    size_t digit=(size_t)(*number-'0');
    if(value>(NIAK_SHADOWMOUNT_HTTP_CAP-digit)/10u)return -1;
    value=value*10u+digit;
    ++number;++digits;
   }
   while(number<end&&(*number==' '||*number=='\t'))++number;
   if(!digits||number!=end||value>NIAK_SHADOWMOUNT_HTTP_CAP-header_bytes ||
      (known_length&&value!=length))return -1;
   known_length=1;length=value;
  } else if(bytes>=18u && strncasecmp(line,"Transfer-Encoding:",18)==0) {
   /* Cannot safely pass chunk framing directly to the JSON parser. */
   return -1;
  }
  line=end+2;
 }
 char *start=sep+4;
 const size_t payload=size-header_bytes;
 if(known_length) {
  if(payload<length)return eof?-1:0;
  start[length]=0;
  *body=start;
  return 1;
 }
 if(!eof)return 0;
 *body=start;
 return 1;
}
#endif
