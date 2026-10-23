/* SPDX-License-Identifier: GPL-3.0-or-later
 * NiakPS5 optional autostart payload for the already-jailbroken console.
 * NOT a ShellUI replacement, memory patch, hbldr, SceSysCore hook, or GUI.
 * Opt-in only. The homebrew title remains a normal app with a normal exit.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/stat.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <sys/time.h>
#include <time.h>
#include "redirect_gate.h"
#include "title_permissions.h"
#include "socket_guard.h"
#include "broker_inventory.h"

#define NIAK_TITLE "PPSA99386"
/* Legacy marker is tolerated but no longer required: PLDmgr's explicit
 * autoload.txt entry is itself the opt-in. A freshly dropped payload must
 * not silently exit merely because ftp_install.py was never executed. */
#define NIAK_ENABLED "/data/niakps5-autostart.enabled"
#define NIAK_DISABLED "/data/niakps5-autostart.disable"
#define NIAK_LOG "/data/niakps5-autostart.log"

extern int sceKernelUsleep(unsigned int microseconds);
extern int sceUserServiceGetForegroundUser(int *user_id);
extern int sceSystemServiceLaunchApp(const char *title_id,
                                     const char **arguments, void *params);
extern int sceSystemServiceGetAppIdOfRunningBigApp(void);

static int is_regular_file(const char *path) {
    struct stat st;
    return lstat(path,&st)==0 && S_ISREG(st.st_mode);
}
static void report(const char *msg,int result) {
    FILE *out=fopen(NIAK_LOG,"a");
    if(out) {
        fprintf(out,"%s rc=0x%08x\n",msg,(unsigned)result);
        fclose(out);
    }
}
#define NIAK_RESUME "/data/niakps5-return-after-game.enabled"

/* Import only the foreground user's existing PNG, if one exists.
 * Never collect accounts, credentials, PSN tokens or any other user's media.
 * Source is the local PS5 profile cache; destination is one private app asset.
 */
static int copy_profile_image(const char *source,const char *dest,
                              const unsigned char *magic,size_t signature_size) {
    FILE *in=fopen(source,"rb");
    if(!in)return 0;
    struct stat st;
    if(fstat(fileno(in),&st)!=0||!S_ISREG(st.st_mode)||
       st.st_size<144||st.st_size>2*1024*1024) {fclose(in);return 0;}
    const size_t size=(size_t)st.st_size;
    unsigned char *data=(unsigned char*)malloc(size);
    if(!data){fclose(in);return 0;}
    int ok=fread(data,1,size,in)==size && memcmp(data,magic,signature_size)==0;
    fclose(in);
    if(ok) {
        struct stat folder;
        if(lstat("/data/homebrew/PPSA99386/assets",&folder)==0 &&
           S_ISDIR(folder.st_mode)) {
            char temp[256];
            const int label=snprintf(temp,sizeof(temp),"%s.XXXXXX",dest);
            if(label<=0 || label>=(int)sizeof(temp))ok=0;
            else {
                // mkstemp creates a fresh O_EXCL file for each attempt.
                // Fixed *.tmp names could permanently block later updates.
                const int fd=mkstemp(temp);
                if(fd<0)ok=0;
                else {
                    size_t written=0;
                    while(written<size) {
                        const ssize_t n=write(fd,data+written,size-written);
                        if(n<0 && errno==EINTR)continue;
                        if(n<=0)break;
                        written+=(size_t)n;
                    }
                    ok=written==size && fchmod(fd,0644)==0 && fsync(fd)==0;
                    if(close(fd)!=0)ok=0;
                    if(ok)ok=rename(temp,dest)==0;
                    if(!ok)unlink(temp);
                }
            }
        }else ok=0;
    }
    free(data);return ok;
}
/* Bind each cached avatar to the actual local foreground account and image
 * type. No PSN identifier or personal image leaves this console. */
static void mark_profile_asset(int user,const char *format) {
    if(user<0 || !format)return;
    const char *dst="/data/homebrew/PPSA99386/assets/niak-profile-source.txt";
    char temp[]="/data/homebrew/PPSA99386/assets/.niak-profile-source-XXXXXX";
    int fd=mkstemp(temp);
    if(fd<0)return;
    char identity[32];
    const int n=snprintf(identity,sizeof(identity),"0x%08X %s\n",
                         (unsigned)user,format);
    int ok=n>0 && n<(int)sizeof(identity) &&
           write(fd,identity,(size_t)n)==n &&
           fchmod(fd,0644)==0 && fsync(fd)==0;
    if(close(fd)!=0)ok=0;
    if(!ok || rename(temp,dst)!=0)unlink(temp);
}
/* Invalidate the generic file's owner BEFORE replacing its bytes.
 * If permissions prevent invalidation, do not overwrite the old image:
 * another profile could otherwise inherit a mismatched owner marker. */
static int invalidate_profile_asset(void) {
    const char *path="/data/homebrew/PPSA99386/assets/niak-profile-source.txt";
    const int fd=open(path,O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW,0600);
    if(fd<0)return 0;
    const int ok=fchmod(fd,0644)==0 && fsync(fd)==0;
    return close(fd)==0 && ok;
}
static void copy_current_avatar_png(int user) {
    if(user<0)return;
    if(!invalidate_profile_asset()) {
        report("Avatar owner invalidation denied", -1);
        return;
    }
    char profile[256],source[320];
    snprintf(profile,sizeof(profile),
             "/system_data/priv/cache/profile/0x%08X",(unsigned)user);
    static const unsigned char png[8]={137,80,78,71,13,10,26,10};
    static const unsigned char dds[4]={'D','D','S',' '};
    snprintf(source,sizeof(source),"%s/avatar.png",profile);
    if(copy_profile_image(source,"/data/homebrew/PPSA99386/assets/niak-profile.png",png,8)) {
        mark_profile_asset(user,"png");
        report("Current user PNG avatar staged",0);
        return;
    }
    for(int i=0;i<3;++i) {
        const char *name=i==0?"avatar128.dds":i==1?"avatar260.dds":"avatar64.dds";
        snprintf(source,sizeof(source),"%s/%s",profile,name);
        if(copy_profile_image(source,"/data/homebrew/PPSA99386/assets/niak-profile.dds",dds,4)) {
            mark_profile_asset(user,"dds");
            report("Current user DDS avatar staged",0);
            return;
        }
    }
    report("Current user avatar inaccessible: no image staged",0);
}

/* The user-authorized PLDmgr one-shot stays resident as a narrow, LOCAL-ONLY
 * launch broker. Native titles cannot reliably start other games from their
 * sandbox. No remote bind, no files / commands / arbitrary title IDs accepted.
 * This is not an exploit, ShellUI hook or remote control service.
 */
static int permitted_title(const char *id) {
    static const char *const roots[]={
        "/user/app/","/system_ex/app/","/data/homebrew/",
        "/mnt/ext0/user/app/","/mnt/ext1/user/app/"
    };
    return niak_title_is_launchable(
        id,NIAK_TITLE,roots,sizeof(roots)/sizeof(roots[0]));
}
static uint64_t niak_monotonic_ms(void) {
    struct timespec clock_time;
    if(clock_gettime(CLOCK_MONOTONIC,&clock_time)!=0)return 0;
    return (uint64_t)clock_time.tv_sec*1000u+
           (uint64_t)clock_time.tv_nsec/1000000u;
}
static void serve_launch_requests(void) {
    const int fd=socket(AF_INET,SOCK_STREAM,0);
    if(fd<0){report("Local launch broker socket unavailable",fd);return;}
    niak_socket_guard(fd);
    int yes=1;(void)setsockopt(fd,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));
    struct sockaddr_in addr={0};
    addr.sin_family=AF_INET;
    addr.sin_port=htons(19187);
    addr.sin_addr.s_addr=htonl(0x7f000001u);
    if(bind(fd,(struct sockaddr*)&addr,sizeof(addr))!=0 || listen(fd,3)!=0) {
        report("Local launch broker bind refused",-1);close(fd);return;
    }
    report("Local launch broker ready (127.0.0.1 only)",0);
    NiakRedirectGate gate;
    int gate_ready=0,return_user=-1;
    // The original 21,600 two-second iterations silently stopped the
    // launch service after roughly twelve hours. Keep the opt-in broker
    // alive until the user disables it or the console shuts down.
    for(;;) {
        if(is_regular_file(NIAK_DISABLED))break;
        fd_set pending;FD_ZERO(&pending);FD_SET(fd,&pending);
        struct timeval tv={2,0};
        const int available=select(fd+1,&pending,NULL,NULL,&tv);
        if(available>0 && FD_ISSET(fd,&pending)) {
            int client=accept(fd,NULL,NULL);
            if(client>=0) {
                niak_socket_guard(client);
                struct timeval client_timeout={2,0};
                (void)setsockopt(client,SOL_SOCKET,SO_RCVTIMEO,
                                 &client_timeout,sizeof(client_timeout));
                (void)setsockopt(client,SOL_SOCKET,SO_SNDTIMEO,
                                 &client_timeout,sizeof(client_timeout));
                char request[24]={0};
                size_t count=0;
                while(count<sizeof(request)-1) {
                    ssize_t n=recv(client,request+count,sizeof(request)-1-count,0);
                    if(n<=0)break;
                    count+=(size_t)n;
                    if(memchr(request,'\n',count))break;
                }
                if(count==6 && memcmp(request,"GAMES\n",6)==0) {
                    char titles[8192];
                    const int n=niak_broker_inventory(titles,sizeof(titles),"");
                    if(n<0)(void)niak_socket_send(client,"DENIED\n",7);
                    else {
                        (void)niak_socket_send(client,"GAMES\n",6);
                        size_t pos=0,len=strlen(titles);
                        while(pos<len) {
                            const ssize_t sent=niak_socket_send(client,titles+pos,len-pos);
                            if(sent<=0)break;
                            pos+=(size_t)sent;
                        }
                        if(pos==len)(void)niak_socket_send(client,"END\n",4);
                    }
                    close(client);
                    continue;
                }
                // A read-only PING makes actual PLDmgr residency testable
                // without launching anything or depending on historical logs.
                if(count==5 && memcmp(request,"PING\n",5)==0) {
                    (void)niak_socket_send(client,"PONG\n",5);
                    close(client);
                    continue;
                }
                int result=-3;
                if(count==17 && memcmp(request,"LAUNCH ",7)==0 &&
                   request[16]=='\n') {
                    char title[10]={0};
                    memcpy(title,request+7,9);
                    if(permitted_title(title)) {
                        int user=-1;
                        if(sceUserServiceGetForegroundUser(&user)==0&&user>=0) {
                            const int source_app=sceSystemServiceGetAppIdOfRunningBigApp();
                            result=sceSystemServiceLaunchApp(title,NULL,NULL);
                            report("Local title launch request",result);
                            // The return gate is opt-in, and only the launch
                            // we explicitly requested may arm it. Merely
                            // seeing some other bigapp never arms a redirect.
                            gate_ready=niak_redirect_arm_after_launch(
                                &gate,is_regular_file(NIAK_RESUME),
                                source_app,result);
                            return_user=gate_ready?user:-1;
                        }
                    }
                }
                char response[32];
                int n=snprintf(response,sizeof(response),
                               "RC %08X\n",(unsigned)result);
                if(n>0&&n<(int)sizeof(response))
                    (void)niak_socket_send(client,response,(size_t)n);
                close(client);
            }
        }
        if(!is_regular_file(NIAK_RESUME)) {
            gate_ready=0;
            return_user=-1;
            continue;
        }
        if(!gate_ready)continue;
        const int running=sceSystemServiceGetAppIdOfRunningBigApp();
        if(!niak_redirect_tick(&gate,running,niak_monotonic_ms()))continue;
        int user=-1;
        const int user_rc=sceUserServiceGetForegroundUser(&user);
        if(user_rc==0 && niak_redirect_same_user(return_user,user)) {
            const int rc=sceSystemServiceLaunchApp(NIAK_TITLE,NULL,NULL);
            report("Optional game-exit return",rc);
        } else {
            // A changed or unreadable profile must never receive an
            // unsolicited home switch from the previous user's game.
            report("Optional game-exit return cancelled (user changed)",user_rc);
        }
        gate_ready=0;
        return_user=-1;
    }
    close(fd);
    report("Local launch broker shutdown",0);
}
int main(void) {
    if(is_regular_file(NIAK_DISABLED))return 0;
    report("NiakPS5 optional autostart start",0);
    int profile_checked=0;
    int launcher_started=0;
    for(unsigned i=0;i<12;++i) {
        if(is_regular_file(NIAK_DISABLED))return 0;
        const int running=sceSystemServiceGetAppIdOfRunningBigApp();
        if(running>0) {
            /* Do not interrupt foreground system tasks or games. */
            sceKernelUsleep(3000000);
            continue;
        }
        int user=-1;
        const int user_rc=sceUserServiceGetForegroundUser(&user);
        if(user_rc==0 && user>=0) {
            if(!profile_checked){copy_current_avatar_png(user);profile_checked=1;}
            const int rc=sceSystemServiceLaunchApp(NIAK_TITLE,NULL,NULL);
            report("sceSystemServiceLaunchApp",rc);
            if(rc==0) {
                launcher_started=1;
                break;
            }
        } else {
            report("Foreground user unavailable",user_rc);
        }
        sceKernelUsleep(3000000);
    }
    if(!launcher_started)
        report("Autostart not confirmed; launch broker still available",0);
    // A manually started title can submit an explicit launch request too.
    // Return is armed by that request, not by autostart success at boot.
    serve_launch_requests();
    return 0;
}
