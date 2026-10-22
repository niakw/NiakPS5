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

/* Inspect chunk boundaries without mutating a partial TCP read.
 * Re-run once complete and compact decoded data in-place. */
static inline int niak_shm_chunked(char *data,size_t size,int eof) {
 size_t pos=0,total=0;
 for(;;) {
  size_t line=pos;
  while(line+1<size && !(data[line]=='\r'&&data[line+1]=='\n'))++line;
  if(line+1>=size)return eof?-1:0;
  if(line-pos>96u)return -1;
  size_t count=0;int digits=0;
  for(size_t i=pos;i<line && data[i]!=';';++i) {
   const unsigned char c=(unsigned char)data[i];
   unsigned digit;
   if(c>='0'&&c<='9')digit=(unsigned)(c-'0');
   else if(c>='A'&&c<='F')digit=(unsigned)(c-'A'+10);
   else if(c>='a'&&c<='f')digit=(unsigned)(c-'a'+10);
   else return -1;
   if(count>(NIAK_SHADOWMOUNT_HTTP_CAP-digit)/16u)return -1;
   count=count*16u+digit;++digits;
  }
  if(!digits || count>NIAK_SHADOWMOUNT_HTTP_CAP-total)return -1;
  pos=line+2;
  if(count==0) {
   // Empty trailer block is CRLF. Optional named trailers are bounded.
   if(size-pos<2)return eof?-1:0;
   if(data[pos]=='\r'&&data[pos+1]=='\n')break;
   size_t trailer=pos;
   while(trailer+3<size &&
         !(data[trailer]=='\r'&&data[trailer+1]=='\n'&&
           data[trailer+2]=='\r'&&data[trailer+3]=='\n'))++trailer;
   if(trailer-pos>4096u)return -1;
   if(trailer+3>=size)return eof?-1:0;
   break;
  }
  if(size-pos<count+2)return eof?-1:0;
  if(data[pos+count]!='\r'||data[pos+count+1]!='\n')return -1;
  total+=count;pos+=count+2;
 }
 // Fully framed: compact only now, never on incomplete fragments.
 pos=0;size_t written=0;
 for(;;) {
  size_t line=pos;
  while(!(data[line]=='\r'&&data[line+1]=='\n'))++line;
  size_t count=0;
  for(size_t i=pos;i<line&&data[i]!=';';++i) {
   const unsigned char c=(unsigned char)data[i];
   count=count*16u+(unsigned)(c>='0'&&c<='9'?c-'0':
                     c>='A'&&c<='F'?c-'A'+10:c-'a'+10);
  }
  pos=line+2;
  if(count==0)break;
  memmove(data+written,data+pos,count);
  written+=count;pos+=count+2;
 }
 data[written]=0;
 return 1;
}

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
 int known_length=0,chunked=0;
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
   const char *encoding=line+18;
   while(encoding<end&&(*encoding==' '||*encoding=='\t'))++encoding;
   if(chunked || (size_t)(end-encoding)!=7u ||
      strncasecmp(encoding,"chunked",7)!=0)return -1;
   chunked=1;
  }
  line=end+2;
 }
 char *start=sep+4;
 const size_t payload=size-header_bytes;
 if(chunked) {
  if(known_length)return -1; // ambiguous body framing
  const int result=niak_shm_chunked(start,payload,eof);
  if(result==1)*body=start;
  return result;
 }
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
