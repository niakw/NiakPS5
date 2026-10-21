/* SPDX-License-Identifier: GPL-3.0-or-later
 * Optional read-only ShadowMountPlus v1.7 API catalog.
 * Bounded HTTP/1.1 over PS5 loopback only, never Internet or system files.
 */
#define _POSIX_C_SOURCE 200809L
#include "shadowmount_api.h"
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define NIAK_HTTP_LIMIT (2U*1024U*1024U)
static void skip_ws(const char **p) {
 while(**p==' '||**p=='\t'||**p=='\n'||**p=='\r') ++*p;
}
static int match_key(const char **p,const char *key) {
 skip_ws(p);
 if(**p!='"')return 0;
 ++*p;size_t n=strlen(key);
 if(strncmp(*p,key,n)!=0||(*p)[n]!='"')return 0;
 *p+=n+1;skip_ws(p);if(**p!=':')return 0;++*p;
 skip_ws(p);return 1;
}
static int read_json_string(const char **p,char *dst,size_t cap) {
 if(!cap || **p!='"')return 0;
 ++*p;
 size_t used=0;
 while(**p&&**p!='"'){
  unsigned char c=(unsigned char)*(*p)++;
  if(c=='\\'){
   c=(unsigned char)*(*p)++;
   if(c==0)return 0;
   if(c=='u'){for(int i=0;i<4;i++){if(!**p)return 0;++*p;}c='?';}
   else if(c=='n'||c=='t'||c=='r')c=' ';
   else if(c!='"'&&c!='\\'&&c!='/')c='?';
  }
  if(c<32)return 0;
  if(used+1<cap)dst[used++]=(char)c;
 }
 if(**p!='"')return 0;
 ++*p;
 dst[used]=0;
 return 1;
}
static int member_string(const char *from,const char *end,const char *key,
                         char *dest,size_t cap) {
 const char *p=from;
 while(p<end&&*p) {
  if(*p=='"'){
   const char *candidate=p;
   if(match_key(&candidate,key) && candidate<end)
    return read_json_string(&candidate,dest,cap);
   ++p;
   /* Skip quoted strings to avoid seeing key names inside string values. */
   while(p<end&&*p) {
    if(*p=='\\'&&p+1<end){p+=2;continue;}
    if(*p++=='"')break;
   }
   continue;
  }
  ++p;
 }
 return 0;
}
static int array_bounds(const char *json,const char **begin,const char **end) {
 const char *p=json;
 while(*p) {
  if(*p=='"'){
   const char *probe=p;
   if(match_key(&probe,"games")&&*probe=='['){*begin=probe+1;break;}
   ++p;
   while(*p){
    if(*p=='\\'&&p[1]){p+=2;continue;}
    if(*p++=='"')break;
   }
  }else ++p;
 }
 if(!*begin)return 0;
 int depth=1;int quoted=0,esc=0;
 for(p=*begin;*p;p++){
  if(quoted){if(esc)esc=0;else if(*p=='\\')esc=1;else if(*p=='"')quoted=0;continue;}
  if(*p=='"'){quoted=1;continue;}
  if(*p=='[')++depth;
  else if(*p==']'&&--depth==0){*end=p;return 1;}
 }
 return 0;
}
int niak_parse_shadowmount_games(const char *json,NiakGame *games,size_t capacity) {
 if(!json||!games||capacity==0||strlen(json)>NIAK_HTTP_LIMIT)return -1;
 const char *p=json;skip_ws(&p);if(*p!='{')return -1;
 const char *status=p;char tmp[16];
 if(!member_string(p,p+strlen(p),"error",tmp,sizeof(tmp))) {
  /* An error string is optional; status is required. */
 }
 /* Robust numeric status read even with arbitrary whitespace. */
 const char *st=strstr(status,"\"status\"");
 if(!st)return -1;
 st+=8;
 skip_ws(&st);
 if(*st++!=':')return -1;
 skip_ws(&st);if(*st++!='0'||(*st>='0'&&*st<='9'))return -1;
 const char *start=NULL,*finish=NULL;
 if(!array_bounds(json,&start,&finish))return -1;
 size_t count=0;
 p=start;
 while(p<finish&&count<capacity){
  while(p<finish&&*p!='{')++p;
  if(p>=finish)break;
  const char *begin=p;int depth=0,quoted=0,escape=0;
  for(;p<finish;p++){
   char c=*p;
   if(quoted){if(escape)escape=0;else if(c=='\\')escape=1;else if(c=='"')quoted=0;continue;}
   if(c=='"'){quoted=1;continue;}
   if(c=='{')++depth;
   if(c=='}'&&--depth==0){++p;break;}
  }
  if(depth!=0)return -1;
  NiakGame game={0};
  if(!member_string(begin,p,"title_id",game.id,sizeof(game.id))||
      !niak_valid_title_id(game.id))continue;
  if(!member_string(begin,p,"name",game.title,sizeof(game.title))||!game.title[0])
   snprintf(game.title,sizeof(game.title),"%s",game.id);
  game.discovered_from_homebrew=2;
  int duplicate=0;
  for(size_t i=0;i<count;i++)if(strcmp(games[i].id,game.id)==0)duplicate=1;
  if(!duplicate)games[count++]=game;
 }
 return (int)count;
}
int niak_scan_shadowmount(NiakGame *games,size_t capacity){
 if(!games||!capacity)return -1;
 int fd=socket(AF_INET,SOCK_STREAM,0);
 if(fd<0)return -1;
 struct timeval tv={1,500000};
 setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));
 setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&tv,sizeof(tv));
 int port=10101;
#ifndef __PS5__
 const char *override=getenv("NIAK_SHADOWMOUNT_PORT");
 if(override){int n=atoi(override);if(n>0&&n<65536)port=n;}
#endif
 struct sockaddr_in address={0};
 address.sin_family=AF_INET;address.sin_port=htons((unsigned short)port);
 address.sin_addr.s_addr=htonl(0x7f000001u); /* 127.0.0.1; PS5 SDK lacks INADDR_LOOPBACK */
 if(connect(fd,(struct sockaddr*)&address,sizeof(address))!=0){close(fd);return -1;}
 static const char request[]=
 "POST /api/v1/games HTTP/1.1\r\n"
 "Host: 127.0.0.1\r\nContent-Type: application/json\r\n"
 "Content-Length: 2\r\nConnection: close\r\n\r\n{}";
 size_t sent=0,total_request=sizeof(request)-1;
 while(sent<total_request){
  ssize_t result=send(fd,request+sent,total_request-sent,0);
  if(result<=0){close(fd);return -1;}sent+=(size_t)result;
 }
 char *response=(char*)malloc(NIAK_HTTP_LIMIT+1);
 if(!response){close(fd);return -1;}
 size_t size=0;ssize_t n;
 while(size<NIAK_HTTP_LIMIT &&
       (n=recv(fd,response+size,NIAK_HTTP_LIMIT-size,0))>0)size+=(size_t)n;
 close(fd);
 response[size]=0;
 if(n<0||size==NIAK_HTTP_LIMIT||strncmp(response,"HTTP/1.1 200",12)!=0){
  free(response);return -1;
 }
 char *body=strstr(response,"\r\n\r\n");
 if(!body){free(response);return -1;}body+=4;
 int count=niak_parse_shadowmount_games(body,games,capacity);
 free(response);return count;
}
