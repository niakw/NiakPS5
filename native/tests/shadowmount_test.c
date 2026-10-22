/* SPDX-License-Identifier: GPL-3.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include "../shadowmount_api.h"
#include "../shadowmount_http.h"
#include <stdlib.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
int main(void){
 NiakGame g[5]={0};
 const char *json="{\"status\": 0,\"count\":3,\"games\":["
 "{\"title_id\":\"PPSA00001\",\"name\":\"Jeu PS5\",\"path\":\"/data/homebrew/PPSA00001\"},"
 "{\"title_id\":\"CUSA00222\",\"name\":\"PS4\"},"
 "{\"title_id\":\"PPSA99999/../\",\"name\":\"Bad\"}]}";
 int n=niak_parse_shadowmount_games(json,g,5);
 assert(n==2);assert(strcmp(g[0].title,"Jeu PS5")==0);
 assert(g[0].is_homebrew==1);assert(g[1].is_homebrew==0);
 assert(strcmp(g[1].id,"CUSA00222")==0);
 assert(niak_parse_shadowmount_games("{\"status\": 13,\"games\":[]}",g,5)==-1);
 assert(niak_parse_shadowmount_games("{\"status\":0,\"games\":[]}",g,5)==0);
 assert(niak_parse_shadowmount_games("{\"status\":0,\"games\":[{\"title_id\":\"PPSA00001\",\"name\":\"a\"},{\"title_id\":\"PPSA00001\",\"name\":\"b\"}]}",g,5)==1);
 // ShadowMountPlus may JSON-escape accented names and emoji.
 const char *escaped="{\"status\":0,\"games\":["
    "{\"title_id\":\"PPSA12345\",\"name\":\"Jeu \\u00e9dition \\uD83C\\uDFAE\"}]}";
 assert(niak_parse_shadowmount_games(escaped,g,5)==1);
 assert(strcmp(g[0].title,"Jeu \xc3\xa9" "dition \xf0\x9f\x8e\xae")==0);
 // A malformed UTF-16 surrogate is rejected; fallback is the exact title ID.
 const char *bad_unicode="{\"status\":0,\"games\":["
    "{\"title_id\":\"CUSA22334\",\"name\":\"\\uD83C\"}]}";
 assert(niak_parse_shadowmount_games(bad_unicode,g,5)==1);
 assert(strcmp(g[0].title,"CUSA22334")==0);

 // HTTP/1.1 persistent connection: do not wait for EOF after body length.
 char raw[256]="HTTP/1.1 200 OK\r\nContent-Length: 23\r\n"
               "Connection: keep-alive\r\n\r\n{\"status\":0,\"games\":[]}";
 const char *body=NULL;
 size_t len=strlen(raw);
 assert(niak_shadowmount_http_json(raw,len,0,&body)==1);
 assert(body && strcmp(body,"{\"status\":0,\"games\":[]}") == 0);
 assert(niak_shadowmount_http_json(raw,len-4,0,&body)==0);
 assert(niak_shadowmount_http_json(raw,len-4,1,&body)==-1);
 char invalid[256]="HTTP/1.1 200 OK\r\nContent-Length: 99999999999999\r\n\r\n{}";
 assert(niak_shadowmount_http_json(invalid,strlen(invalid),0,&body)==-1);
 char chunked[256]="HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n"
                   "Connection: keep-alive\r\n\r\n"
                   "9\r\n{\"status\"\r\n"
                   "E\r\n:0,\"games\":[]}\r\n0\r\n\r\n";
 size_t chunk_size=strlen(chunked);
 // The parser NUL-terminates the supplied view; keep the complete test
 // frame untouched while examining a deliberately truncated snapshot.
 char fragment[256];
 memcpy(fragment,chunked,chunk_size+1);
 assert(niak_shadowmount_http_json(fragment,chunk_size-2,0,&body)==0);
 assert(niak_shadowmount_http_json(chunked,chunk_size,0,&body)==1);
 assert(strcmp(body,"{\"status\":0,\"games\":[]}") == 0);
 char bad_transfer[256]="HTTP/1.1 200 OK\r\nTransfer-Encoding: gzip\r\n\r\n0\r\n\r\n";
 assert(niak_shadowmount_http_json(bad_transfer,strlen(bad_transfer),0,&body)==-1);
 char ambiguous[256]="HTTP/1.1 200 OK\r\nContent-Length: 23\r\n"
                     "Transfer-Encoding: chunked\r\n\r\n0\r\n\r\n";
 assert(niak_shadowmount_http_json(ambiguous,strlen(ambiguous),0,&body)==-1);
 // End-to-end loopback test: an HTTP/1.1 server can keep its socket
 // open after the complete JSON. The scanner must NOT wait for close.
 int server=socket(AF_INET,SOCK_STREAM,0);
 assert(server>=0);
 struct sockaddr_in bound={0};
 bound.sin_family=AF_INET;
 bound.sin_port=0;
 bound.sin_addr.s_addr=htonl(0x7f000001u);
 assert(bind(server,(struct sockaddr*)&bound,sizeof(bound))==0);
 assert(listen(server,1)==0);
 socklen_t addrlen=sizeof(bound);
 assert(getsockname(server,(struct sockaddr*)&bound,&addrlen)==0);
 char port[12];
 snprintf(port,sizeof(port),"%u",(unsigned)ntohs(bound.sin_port));
 assert(setenv("NIAK_SHADOWMOUNT_PORT",port,1)==0);
 pid_t child=fork();
 assert(child>=0);
 if(child==0) {
  int client=accept(server,NULL,NULL);
  if(client<0)_exit(2);
  char request[512]={0};
  ssize_t received=recv(client,request,sizeof(request)-1,0);
  if(received<=0 || !strstr(request,"POST /api/v1/games"))_exit(3);
  const char *json="{\"status\":0,\"games\":[{\"title_id\":\"PPSA12345\","
                   "\"name\":\"Local API\"}]}";
  char answer[512];
  int bytes=snprintf(answer,sizeof(answer),
      "HTTP/1.1 200 OK\r\nContent-Length: %zu\r\n"
      "Connection: keep-alive\r\n\r\n%s",strlen(json),json);
  if(bytes<1||bytes>=(int)sizeof(answer))_exit(4);
  if(send(client,answer,(size_t)bytes,0)!=bytes)_exit(5);
  struct timespec pause_for={2,0};
  nanosleep(&pause_for,NULL);
  close(client);close(server);_exit(0);
 }
 struct timespec before,after;
 assert(clock_gettime(CLOCK_MONOTONIC,&before)==0);
 memset(g,0,sizeof(g));
 assert(niak_scan_shadowmount(g,5)==1);
 assert(strcmp(g[0].id,"PPSA12345")==0);
 assert(clock_gettime(CLOCK_MONOTONIC,&after)==0);
 long elapsed=(after.tv_sec-before.tv_sec)*1000L+
              (after.tv_nsec-before.tv_nsec)/1000000L;
 assert(elapsed>=0&&elapsed<1500); // 2-second server hold must not block
 int status=0;
 assert(waitpid(child,&status,0)==child);
 assert(WIFEXITED(status)&&WEXITSTATUS(status)==0);
 assert(unsetenv("NIAK_SHADOWMOUNT_PORT")==0);
 close(server);
 puts("ShadowMountPlus readonly API JSON and keep-alive: OK");
 return 0;
}
