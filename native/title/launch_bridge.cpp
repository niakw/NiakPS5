// SPDX-License-Identifier: GPL-3.0-or-later
// Connect only to NiakPS5's opt-in PLDmgr local launch broker.
// A sandboxed title must not claim sceSystemServiceLaunchApp works here.
#include "niak/launch_bridge.hpp"
#include <arpa/inet.h>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

namespace {
constexpr unsigned short kPort=19187;
bool valid(const char *id) {
    if(!id || std::strlen(id)!=9)return false;
    if(std::strncmp(id,"PPSA",4)&&std::strncmp(id,"CUSA",4)&&
       std::strncmp(id,"LAPY",4)&&std::strncmp(id,"FAKE",4)&&
       std::strncmp(id,"NPXS",4))return false;
    for(int i=4;i<9;++i)if(id[i]<'0'||id[i]>'9')return false;
    return true;
}
}
int niak_launch_registered_title(const char *title_id) {
    if(!valid(title_id))return -3;
    int fd=::socket(AF_INET,SOCK_STREAM,0);
    if(fd<0)return -2;
    timeval tv{2,0};
    ::setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));
    ::setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&tv,sizeof(tv));
    sockaddr_in peer{};
    peer.sin_family=AF_INET;
    peer.sin_port=htons(kPort);
    peer.sin_addr.s_addr=htonl(0x7f000001u);
    if(::connect(fd,reinterpret_cast<sockaddr*>(&peer),sizeof(peer))<0) {
        ::close(fd);return -2;
    }
    char request[24]{};
    const int len=std::snprintf(request,sizeof(request),"LAUNCH %.9s\n",title_id);
    if(len<=0 || len>=int(sizeof(request))) {::close(fd);return -3;}
    int sent=0;
    while(sent<len) {
        const ssize_t n=::send(fd,request+sent,std::size_t(len-sent),0);
        if(n<=0){::close(fd);return -2;}
        sent+=int(n);
    }
    char response[32]{};
    const ssize_t n=::recv(fd,response,sizeof(response)-1,0);
    ::close(fd);
    if(n<=0)return -2;
    response[n]=0;
    unsigned code=0;
    if(std::sscanf(response,"RC %8x",&code)!=1)return -3;
    return static_cast<int>(code);
}
