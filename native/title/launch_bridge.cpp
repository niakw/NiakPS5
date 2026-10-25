// SPDX-License-Identifier: GPL-3.0-or-later
#define _POSIX_C_SOURCE 200809L
// Connect only to NiakPS5's opt-in PLDmgr local launch broker.
// A sandboxed title must not claim sceSystemServiceLaunchApp works here.
#include "niak/launch_bridge.hpp"
#include "niak/socket_guard.h"
#include "niak/loopback_connect.h"
#include "niak/broker_snapshot.h"
#include <arpa/inet.h>
#include <netinet/in.h>
#include <cerrno>
#include <cstdint>
#include <time.h>
#include <ctime>
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

namespace {
int kProbeStage=0;
int kProbeError=0;
void mark_probe(int stage,int error) {
    kProbeStage=stage;
    kProbeError=error;
}
}

const char *niak_launch_broker_diagnostic() {
    static char message[196];
    const char *step="non testé";
    switch(kProbeStage) {
    case 1:step="socket";break;
    case 2:step="ioctl FIONBIO";break;
    case 3:step="connect";break;
    case 4:step="send";break;
    case 5:step="recv";break;
    case 6:step="PONG invalide";break;
    case 7:step="PONG confirme";break;
    default:break;
    }
    if(kProbeStage==7)return "PING confirme : service joignable";
    // Settings redraws every frame. Cache filesystem snapshot checks so
    // a denied /app0 or /data read cannot stall the GPU/dual-sense UI at 60 Hz.
    static bool catalogue_readable=false;
    static int snapshot_errors[3]{};
    static std::time_t snapshot_checked_at=0;
    const std::time_t now=std::time(nullptr);
    if(!snapshot_checked_at || now<snapshot_checked_at ||
       now-snapshot_checked_at>=3) {
        NiakGame probe{};
        const char *const sources[]={
            NIAK_SNAPSHOT_APP_FILE,NIAK_SNAPSHOT_APP_SOURCE,
            NIAK_SNAPSHOT_FILE};
        catalogue_readable=false;
        for(int i=0;i<3;++i) {
            errno=0;
            const int result=niak_snapshot_read(sources[i],&probe,1);
            snapshot_errors[i]=result>=0?-1:errno;
            catalogue_readable|=result>=0;
        }
        snapshot_checked_at=now;
    }
    if(catalogue_readable)
        std::snprintf(message,sizeof(message),
                      "PING %s (errno %d); catalogue local lisible",
                      step,kProbeError);
    else
        std::snprintf(message,sizeof(message),
                      "PING %s (errno %d); snapshots app0:%d source:%d data:%d",
                      step,kProbeError,snapshot_errors[0],
                      snapshot_errors[1],snapshot_errors[2]);
    // A readable catalogue does NOT imply that launching games over TCP works.
    return message;
}

bool niak_launch_broker_ready() {
    // A bounded probe only on a cached settings repaint. 30/40 ms was too
    // aggressive on a console busy mounting games: allow 120 ms for each
    // connect/read without waiting for OS TCP retries or blocking each frame.
    static std::uint64_t checked_at_ms=0;
    static bool previous=false,checked=false;
    struct timespec stamp{};
    const bool timed=clock_gettime(CLOCK_MONOTONIC,&stamp)==0;
    const std::uint64_t now_ms=timed?
        static_cast<std::uint64_t>(stamp.tv_sec)*1000u+
        static_cast<std::uint64_t>(stamp.tv_nsec)/1000000u:0u;
    if(timed && checked && now_ms>=checked_at_ms &&
       now_ms-checked_at_ms<1000u)return previous;
    checked_at_ms=now_ms;
    checked=timed;
    previous=false; // Fail closed; never infer liveness from stale logs.
    int fd=::socket(AF_INET,SOCK_STREAM,0);
    if(fd<0){mark_probe(1,errno);return false;}
    niak_socket_guard(fd);
    sockaddr_in peer{};
    peer.sin_family=AF_INET;
    peer.sin_port=htons(kPort);
    peer.sin_addr.s_addr=htonl(0x7f000001u);
    int stage=2;
    if(niak_connect_bounded_ex(fd,reinterpret_cast<sockaddr*>(&peer),
                               sizeof(peer),120,&stage)<0) {
        const int issue=errno;
        ::close(fd);mark_probe(stage,issue);return false;
    }
    timeval io_timeout{0,120000};
    (void)::setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&io_timeout,sizeof(io_timeout));
    (void)::setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&io_timeout,sizeof(io_timeout));
    if(niak_socket_send(fd,"PING\n",5)!=5) {
        const int error=errno;
        ::close(fd);mark_probe(4,error);return false;
    }
    char answer[5]{};
    std::size_t received=0;
    while(received<sizeof(answer)) {
        const ssize_t n=::recv(fd,answer+received,
                               sizeof(answer)-received,0);
        if(n<=0) {
            const int error=n==0?ECONNRESET:errno;
            ::close(fd);mark_probe(5,error);return false;
        }
        received+=static_cast<std::size_t>(n);
    }
    ::close(fd);
    previous=std::memcmp(answer,"PONG\n",5)==0;
    mark_probe(previous?7:6,0);
    return previous;
}

unsigned niak_launch_broker_pid() {
    int fd=::socket(AF_INET,SOCK_STREAM,0);
    if(fd<0)return 0;
    niak_socket_guard(fd);
    sockaddr_in peer{};
    peer.sin_family=AF_INET;
    peer.sin_port=htons(kPort);
    peer.sin_addr.s_addr=htonl(0x7f000001u);
    if(niak_connect_bounded(fd,reinterpret_cast<sockaddr*>(&peer),
                            sizeof(peer),100)<0) {
        ::close(fd);return 0;
    }
    timeval tv{0,150000};
    (void)::setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));
    (void)::setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&tv,sizeof(tv));
    if(niak_socket_send(fd,"STATUS\n",7)!=7){::close(fd);return 0;}
    char reply[13]{};
    std::size_t have=0;
    while(have<sizeof(reply)) {
        const ssize_t n=::recv(fd,reply+have,sizeof(reply)-have,0);
        if(n<=0)break;
        have+=static_cast<std::size_t>(n);
    }
    ::close(fd);
    if(have!=sizeof(reply)||std::memcmp(reply,"PID ",4)!=0||
       reply[12]!='\n')return 0;
    unsigned pid=0;
    for(unsigned i=4;i<12;++i) {
        const unsigned char c=static_cast<unsigned char>(reply[i]);
        if(c>='0'&&c<='9')pid=(pid<<4)|(c-'0');
        else if(c>='A'&&c<='F')pid=(pid<<4)|(c-'A'+10);
        else if(c>='a'&&c<='f')pid=(pid<<4)|(c-'a'+10);
        else return 0;
    }
    return pid;
}

static int niak_open_system_settings_broker() {
    int fd=::socket(AF_INET,SOCK_STREAM,0);
    if(fd<0)return -2;
    niak_socket_guard(fd);
    sockaddr_in address{};
    address.sin_family=AF_INET;
    address.sin_port=htons(kPort);
    address.sin_addr.s_addr=htonl(0x7f000001u);
    if(niak_connect_bounded(fd,reinterpret_cast<sockaddr*>(&address),
                            sizeof(address),100)<0) {
        ::close(fd);return -2;
    }
    timeval timeout{0,350000};
    (void)::setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
    (void)::setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
    if(niak_socket_send(fd,"SETTINGS\n",9)!=9){::close(fd);return -2;}
    char reply[12]{};
    std::size_t have=0;
    while(have<sizeof(reply)) {
        const auto n=::recv(fd,reply+have,sizeof(reply)-have,0);
        if(n<=0)break;
        have+=static_cast<std::size_t>(n);
    }
    ::close(fd);
    if(have!=sizeof(reply)||std::memcmp(reply,"RC ",3)!=0||
       reply[11]!='\n')return -2;
    for(int i=3;i<11;++i) {
        const char ch=reply[i];
        if(!((ch>='0'&&ch<='9')||(ch>='a'&&ch<='f')||
             (ch>='A'&&ch<='F')))return -2;
    }
    unsigned status=0;
    if(std::sscanf(reply+3,"%8x",&status)!=1)return -2;
    return static_cast<int>(status);
}
#if defined(__PROSPERO__)
extern "C" int sceKernelLoadStartModule(const char *path,std::size_t argc,
    const void *argv,std::uint32_t flags,std::uint32_t options,int *result);
extern "C" int sceKernelDlsym(int handle,const char *name,void **address);
extern "C" int sceUserServiceGetForegroundUser(int *user);
struct NiakShellUriArgs { std::uint32_t size,user; };
#endif
int niak_open_system_settings() {
    // First ask the existing, opt-in PLDmgr broker. Its system context
    // may launch ShellUI even where this application's sandbox is denied.
    const int broker_rc=niak_open_system_settings_broker();
    if(broker_rc==0)return 0;
#if defined(__PROSPERO__)
    // Even a reachable broker can receive a firmware-specific ShellUI denial.
    // Its error should not preclude the existing direct, fixed-URI API.
    // Neither path escalates this process or edits console configuration.
    // A PlayStation URI is NOT an Internet URL. The WebBrowser service
    // rejects pssettings:, as confirmed on hardware. Itemzflow/etaHEN use
    // ShellUIUtilLaunchByUri instead; resolve dynamically to avoid assuming
    // the sandbox grants this private service.
    const int direct_rc=[&]() -> int {
        int module_result=0;
        const int module=sceKernelLoadStartModule(
            "/system_ex/common_ex/lib/libSceShellUIUtil.sprx",
            0,nullptr,0,0,&module_result);
        if(module<0)return module;
        using Initialize=int(*)();
        using Launch=int(*)(const char*,NiakShellUriArgs*);
        Initialize init=nullptr;
        Launch launch=nullptr;
        void *resolved=nullptr;
        if(sceKernelDlsym(module,"sceShellUIUtilInitialize",&resolved)<0 ||
           !resolved)return -10;
        init=reinterpret_cast<Initialize>(resolved);
        resolved=nullptr;
        if(sceKernelDlsym(module,"sceShellUIUtilLaunchByUri",&resolved)<0 ||
           !resolved)return -11;
        launch=reinterpret_cast<Launch>(resolved);
        int user=-1;
        if(sceUserServiceGetForegroundUser(&user)<0 || user<0)return -12;
        const int initialized=init();
        if(initialized<0)return initialized;
        NiakShellUriArgs args{sizeof(NiakShellUriArgs),
                               static_cast<std::uint32_t>(user)};
        // Fixed root settings URI, not debug settings or an editable URL.
        return launch("pssettings:play?mode=settings",&args);
    }();
    // Retain the actual privileged-broker rejection rather than concealing
    // it behind a secondary sandbox failure; direct success still wins.
    return direct_rc==0 ? 0 : broker_rc!=-2 ? broker_rc : direct_rc;
#else
    return broker_rc;
#endif
}
