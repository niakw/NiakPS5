// SPDX-License-Identifier: GPL-3.0-or-later
#define _POSIX_C_SOURCE 200809L
// Connect only to NiakPS5's opt-in PLDmgr local launch broker.
// A sandboxed title must not claim sceSystemServiceLaunchApp works here.
#include "niak/launch_bridge.hpp"
#include "niak/socket_guard.h"
#include "niak/loopback_connect.h"
#include <arpa/inet.h>
#include <netinet/in.h>
#include <cerrno>
#include <cstdint>
#include <time.h>
#include <fcntl.h>
#include <sys/select.h>
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
    niak_socket_guard(fd);
    timeval tv{2,0};
    ::setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));
    ::setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&tv,sizeof(tv));
    sockaddr_in peer{};
    peer.sin_family=AF_INET;
    peer.sin_port=htons(kPort);
    peer.sin_addr.s_addr=htonl(0x7f000001u);
    // The user pressing Jouer must not wait for a missing broker to time out.
    if(niak_connect_bounded(fd,reinterpret_cast<sockaddr*>(&peer),sizeof(peer),100)<0) {
        ::close(fd);return -2;
    }
    char request[24]{};
    const int len=std::snprintf(request,sizeof(request),"LAUNCH %.9s\n",title_id);
    if(len<=0 || len>=int(sizeof(request))) {::close(fd);return -3;}
    int sent=0;
    while(sent<len) {
        const ssize_t n=niak_socket_send(fd,request+sent,std::size_t(len-sent));
        if(n<=0){::close(fd);return -2;}
        sent+=int(n);
    }
    // TCP is a byte stream. Reject partial or malformed RC messages.
    char response[12]{};
    std::size_t received=0;
    while(received<sizeof(response)) {
        const ssize_t n=::recv(fd,response+received,
                               sizeof(response)-received,0);
        if(n<=0){::close(fd);return -2;}
        received+=static_cast<std::size_t>(n);
    }
    ::close(fd);
    if(std::memcmp(response,"RC ",3)!=0 || response[11]!='\n')return -3;
    for(std::size_t i=3;i<11;++i) {
        const char c=response[i];
        if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')||
             (c>='A'&&c<='F')))return -3;
    }
    unsigned code=0;
    if(std::sscanf(response+3,"%8x",&code)!=1)return -3;
    return static_cast<int>(code);
}

bool niak_launch_broker_ready() {
    // Called during Settings rendering. One PING each frame would spend up
    // to 70ms/frame waiting for a hung local broker. Cache briefly, with a
    // monotonic clock so wall-clock adjustments cannot prolong that delay.
    static std::uint64_t checked_at_ms=0;
    static bool previous=false,checked=false;
    struct timespec stamp{};
    // A failed clock query must not use a stale cached health result.
    const bool timed=clock_gettime(CLOCK_MONOTONIC,&stamp)==0;
    const std::uint64_t now_ms=timed?
        static_cast<std::uint64_t>(stamp.tv_sec)*1000u+
        static_cast<std::uint64_t>(stamp.tv_nsec)/1000000u:0u;
    if(timed && checked && now_ms>=checked_at_ms &&
       now_ms-checked_at_ms<1000u)return previous;
    checked_at_ms=now_ms;
    checked=timed;
    previous=false; // Fail closed when the broker stops responding.
    int fd=::socket(AF_INET,SOCK_STREAM,0);
    if(fd<0)return false;
    niak_socket_guard(fd);
    const int flags=::fcntl(fd,F_GETFL,0);
    if(flags<0 || ::fcntl(fd,F_SETFL,flags|O_NONBLOCK)<0) {
        ::close(fd);
        return false;
    }
    sockaddr_in peer{};
    peer.sin_family=AF_INET;
    peer.sin_port=htons(kPort);
    peer.sin_addr.s_addr=htonl(0x7f000001u);
    int result=::connect(fd,reinterpret_cast<sockaddr*>(&peer),sizeof(peer));
    if(result!=0 && errno==EINPROGRESS) {
        fd_set writable;FD_ZERO(&writable);FD_SET(fd,&writable);
        timeval connect_timeout{0,30000}; // at most 30ms on loopback
        const int selected=::select(fd+1,nullptr,&writable,nullptr,&connect_timeout);
        int error=0;socklen_t error_size=sizeof(error);
        if(selected==1 && FD_ISSET(fd,&writable) &&
           ::getsockopt(fd,SOL_SOCKET,SO_ERROR,&error,&error_size)==0 &&
           error==0)result=0;
    }
    if(result!=0 || ::fcntl(fd,F_SETFL,flags)<0) {
        ::close(fd);
        return false;
    }
    // Short, finite reads still accept fragmented local TCP replies.
    timeval io_timeout{0,40000};
    (void)::setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&io_timeout,sizeof(io_timeout));
    (void)::setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&io_timeout,sizeof(io_timeout));
    char answer[5]{};
    std::size_t received=0;
    if(niak_socket_send(fd,"PING\n",5)==5) {
        while(received<sizeof(answer)) {
            const ssize_t n=::recv(fd,answer+received,
                                   sizeof(answer)-received,0);
            if(n<=0)break;
            received+=static_cast<std::size_t>(n);
        }
    }
    ::close(fd);
    previous=received==sizeof(answer) && std::memcmp(answer,"PONG\n",5)==0;
    return previous;
}
