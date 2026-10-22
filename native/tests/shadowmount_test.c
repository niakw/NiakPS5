/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "../shadowmount_api.h"
#include "../shadowmount_http.h"
#include <stdlib.h>
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
 char bad_transfer[256]="HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n";
 assert(niak_shadowmount_http_json(bad_transfer,strlen(bad_transfer),0,&body)==-1);
 puts("ShadowMountPlus readonly API JSON: OK");
 return 0;
}
