// SPDX-License-Identifier: GPL-3.0-or-later
#include "niak/broker_catalog.hpp"
#include "niak/socket_guard.h"
#include "niak/loopback_connect.h"
#include "niak/broker_snapshot.h"
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
#include <cstdio>
#include <cstring>

static int niak_scan_broker_socket(NiakGame *games,std::size_t cap) {
 if(!games||!cap)return -1;
 const int fd=socket(AF_INET,SOCK_STREAM,0);
 if(fd<0)return -1;
 niak_socket_guard(fd);
 sockaddr_in address{};
 address.sin_family=AF_INET;
 address.sin_port=htons(19187);
 address.sin_addr.s_addr=htonl(0x7f000001u);
 if(niak_connect_bounded(fd,reinterpret_cast<sockaddr*>(&address),
                         sizeof(address),100)<0){close(fd);return -1;}
 timeval tv{0,300000};
 setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));
 setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&tv,sizeof(tv));
 if(niak_socket_send(fd,"GAMES\n",6)!=6){close(fd);return -1;}
 char response[8192]={};
 std::size_t got=0;
 while(got<sizeof(response)-1) {
  const ssize_t n=recv(fd,response+got,sizeof(response)-1-got,0);
  if(n<=0)break;
  got+=static_cast<std::size_t>(n);
  response[got]=0;
  if(std::strstr(response,"\nEND\n"))break;
 }
 close(fd);
 if(got<10||std::strncmp(response,"GAMES\n",6)!=0 ||
    !std::strstr(response,"\nEND\n"))return -1;
 std::size_t found=0;
 const char *p=response+6;
 while(*p && std::strncmp(p,"END\n",4)!=0) {
  const char *end=std::strchr(p,'\n');
  if(!end || end-p!=9)return -1;
  if(std::memcmp(p,"PPSA",4)!=0&&std::memcmp(p,"CUSA",4)!=0&&
     std::memcmp(p,"LAPY",4)!=0&&std::memcmp(p,"FAKE",4)!=0)return -1;
  for(int i=4;i<9;++i)if(p[i]<'0'||p[i]>'9')return -1;
  if(found<cap) {
   NiakGame &game=games[found++];
   std::memset(&game,0,sizeof(game));
   std::memcpy(game.id,p,9);
   std::memcpy(game.title,p,9);
  }
  p=end+1;
 }
 return std::strncmp(p,"END\n",4)==0?int(found):-1;
}

int niak_scan_broker_games(NiakGame *games,std::size_t cap) {
    if(!games || !cap)return -1;
    const int live=niak_scan_broker_socket(games,cap);
    if(live>=0)return live;
    // The PS5 title is sandboxed and may have no TCP/fcntl permissions.
    // The PLDmgr broker writes this small fixed-root inventory periodically;
    // file reading is read-only, checked for freshness, and never launches
    // code or accepts commands from untrusted clients.
    const int mounted=niak_snapshot_read(NIAK_SNAPSHOT_APP_FILE,games,cap);
    if(mounted>=0)return mounted;
    // Some PS5 title setups expose /data/homebrew directly rather than /app0.
    const int direct=niak_snapshot_read(NIAK_SNAPSHOT_APP_SOURCE,games,cap);
    if(direct>=0)return direct;
    return niak_snapshot_read(NIAK_SNAPSHOT_FILE,games,cap);
}
