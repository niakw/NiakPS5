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
#include <sys/syscall.h>
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
#include "loopback_connect.h"
#include "launch_policy.h"
#include "broker_inventory.h"
#include "broker_snapshot.h"

#define NIAK_TITLE "PPSA99386"
/* Legacy marker is tolerated but no longer required: PLDmgr's explicit
 * autoload.txt entry is itself the opt-in. A freshly dropped payload must
 * not silently exit merely because ftp_install.py was never executed. */
#define NIAK_ENABLED "/data/niakps5-autostart.enabled"
#define NIAK_DISABLED "/data/niakps5-autostart.disable"
#define NIAK_LOG "/data/niakps5-autostart.log"

extern int sceKernelUsleep(unsigned int microseconds);
extern int sceUserServiceGetForegroundUser(int *user_id);
extern int sceUserServiceInitialize(void *params);
extern int sceSystemServiceLaunchApp(const char *title_id,
                                     const char **arguments,
                                     NiakLaunchContext *params);
extern int sceLncUtilInitialize(void);
extern int sceLncUtilLaunchApp(const char *title_id,
                              const char **arguments,
                              NiakLaunchContext *params);
extern int sceSystemServiceGetAppIdOfRunningBigApp(void);
extern int sceKernelLoadStartModule(const char *path,size_t argc,
                                   const void *args,uint32_t flags,
                                   uint32_t options,int *result);
extern int sceKernelDlsym(int handle,const char *name,void **target);

typedef struct {
    uint32_t size;
    uint32_t user;
} NiakShellSettingsArgs;
/* Fixed, owner-initiated settings request via the ALREADY resident broker.
 * The sandbox cannot load this private ShellUIUtil module. No custom URI,
 * arbitrary path or general command execution is accepted over loopback.
 */
static int niak_open_settings_from_broker(void) {
    int result=0;
    const int module=sceKernelLoadStartModule(
        "/system_ex/common_ex/lib/libSceShellUIUtil.sprx",
        0,NULL,0,0,&result);
    if(module<0)return module;
    void *initialize=NULL,*launch=NULL;
    if(sceKernelDlsym(module,"sceShellUIUtilInitialize",&initialize)<0 ||
       !initialize)return -10;
    if(sceKernelDlsym(module,"sceShellUIUtilLaunchByUri",&launch)<0 ||
       !launch)return -11;
    int user=-1;
    const int got=sceUserServiceGetForegroundUser(&user);
    if(got<0||user<0)return got<0?got:-12;
    const int started=((int(*)(void))initialize)();
    if(started<0)return started;
    NiakShellSettingsArgs args={sizeof(args),(uint32_t)user};
    return ((int(*)(const char*,NiakShellSettingsArgs*))launch)(
        "pssettings:play?mode=settings",&args);
}

/* One checked entry point for both autostart and the local Jouer action.
 * Logs the raw status of both APIs; a positive LncUtil app id is accepted
 * by the local protocol as success, never sent as a launch error.
 */
static void report(const char *msg,int result);
static int launch_title_as_user(const char *title,int user) {
    NiakLaunchResult launch=niak_launch_with_fallback(
        title,user,sceSystemServiceLaunchApp,sceLncUtilLaunchApp);
    report("sceSystemServiceLaunchApp",launch.system_rc);
    if(launch.method==2)
        report("sceLncUtilLaunchApp accepted app id",launch.lnc_rc);
    else if(launch.lnc_rc==0)
        report("sceLncUtilLaunchApp returned invalid app id",0);
    else if(launch.lnc_rc!=NIAK_LAUNCH_NOT_TRIED)
        report("sceLncUtilLaunchApp refused",launch.lnc_rc);
    return launch.result;
}
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
#define NIAK_RESUME_DISABLED "/data/niakps5-return-after-game.disable"

/* Import only the foreground user's existing PNG, if one exists.
 * Never collect accounts, credentials, PSN tokens or any other user's media.
 * Source is the local PS5 profile cache; destination is one private app asset.
 */
/* Match the graphical avatar decoder's DDS/BC3 contract BEFORE writing
 * /data/homebrew. DDS magic alone is not enough: an incompatible 440 image
 * could otherwise suppress the smaller usable 128/64 fallback. */
static unsigned niak_avatar_dds_u32(const unsigned char *p) {
    return (unsigned)p[0]|((unsigned)p[1]<<8)|
           ((unsigned)p[2]<<16)|((unsigned)p[3]<<24);
}
static int niak_avatar_dds_supported(const unsigned char *data,size_t size) {
    if(!data || size<144 || memcmp(data,"DDS ",4)!=0 ||
       niak_avatar_dds_u32(data+4)!=124u ||
       niak_avatar_dds_u32(data+76)!=32u ||
       memcmp(data+84,"DXT5",4)!=0)return 0;
    const unsigned width=niak_avatar_dds_u32(data+16);
    const unsigned height=niak_avatar_dds_u32(data+12);
    if(width<16u || height<16u || width>512u || height>512u)return 0;
    const size_t blocks=((size_t)width+3u)/4u*
                        (((size_t)height+3u)/4u);
    return blocks<=(size-128u)/16u;
}
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
    if(ok && signature_size==4 && memcmp(magic,"DDS ",4)==0)
        ok=niak_avatar_dds_supported(data,size);
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
static int mark_profile_asset(int user,const char *format) {
    if(user<0 || !format)return 0;
    const char *dst="/data/homebrew/PPSA99386/assets/niak-profile-source.txt";
    char temp[]="/data/homebrew/PPSA99386/assets/.niak-profile-source-XXXXXX";
    int fd=mkstemp(temp);
    if(fd<0)return 0;
    char identity[32];
    const int n=snprintf(identity,sizeof(identity),"0x%08X %s\n",
                         (unsigned)user,format);
    int ok=n>0 && n<(int)sizeof(identity) &&
           write(fd,identity,(size_t)n)==n &&
           fchmod(fd,0644)==0 && fsync(fd)==0;
    if(close(fd)!=0)ok=0;
    if(ok)ok=rename(temp,dst)==0;
    if(!ok)unlink(temp);
    return ok;
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
static int copy_current_avatar_png(int user) {
    if(user<0)return 0;
    if(!invalidate_profile_asset()) {
        report("Avatar owner invalidation denied", -1);
        return 0;
    }
    char profile[256],source[320];
    snprintf(profile,sizeof(profile),
             "/system_data/priv/cache/profile/0x%08X",(unsigned)user);
    static const unsigned char png[8]={137,80,78,71,13,10,26,10};
    static const unsigned char dds[4]={'D','D','S',' '};
    snprintf(source,sizeof(source),"%s/avatar.png",profile);
    if(copy_profile_image(source,"/data/homebrew/PPSA99386/assets/niak-profile.png",png,8)) {
        if(mark_profile_asset(user,"png")) {
            report("Current user PNG avatar staged",0);
            return 1;
        }
        report("Avatar PNG owner marker refused",-1);
        return 0;
    }
    // Native PS5 profile caches can have avatar440.dds even when the PNG
    // or smaller DDS derivatives are missing. Prefer the sharpest permitted
    // BC3 image, while keeping the same strict foreground-user directory.
    static const char *const avatar_files[]={
        "avatar440.dds","avatar260.dds","avatar128.dds","avatar64.dds"};
    for(size_t i=0;i<sizeof(avatar_files)/sizeof(avatar_files[0]);++i) {
        const char *name=avatar_files[i];
        snprintf(source,sizeof(source),"%s/%s",profile,name);
        if(copy_profile_image(source,"/data/homebrew/PPSA99386/assets/niak-profile.dds",dds,4)) {
            if(mark_profile_asset(user,"dds")) {
                report("Current user DDS avatar staged",0);
                return 1;
            }
            report("Avatar DDS owner marker refused",-1);
            return 0;
        }
    }
    report("Current user avatar inaccessible: no image staged",0);
    return 0;
}

/* FTP replacement of the native title may remove an avatar or its owner
 * marker even while the already-running broker remembers an earlier success.
 * Check only the foreground user's exact private marker and the corresponding
 * fixed app asset. No other profile is enumerated or read.
 */
static int current_avatar_asset_staged(int user) {
    if(user<0)return 0;
    const char *marker_path=
        "/data/homebrew/PPSA99386/assets/niak-profile-source.txt";
    const int fd=open(marker_path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
    if(fd<0)return 0;
    struct stat marker_info;
    if(fstat(fd,&marker_info)!=0 || !S_ISREG(marker_info.st_mode) ||
       marker_info.st_size<14 || marker_info.st_size>31) {
        close(fd);return 0;
    }
    char marker[32]={0};
    const ssize_t size=read(fd,marker,sizeof(marker)-1);
    close(fd);
    if(size!=marker_info.st_size)return 0;
    char expected[32];
    const int n=snprintf(expected,sizeof(expected),"0x%08X ",
                         (unsigned)user);
    if(n!=11 || strncmp(marker,expected,(size_t)n)!=0)return 0;
    const char *image=NULL;
    if(strcmp(marker+n,"png\n")==0)
        image="/data/homebrew/PPSA99386/assets/niak-profile.png";
    else if(strcmp(marker+n,"dds\n")==0)
        image="/data/homebrew/PPSA99386/assets/niak-profile.dds";
    else return 0;
    // A file of plausible length is not necessarily a decodable avatar.
    // Older builds could stage an unsupported avatar440.dds and mark it
    // valid forever. Recheck only this foreground owner's private asset
    // on the existing bounded heartbeat, then retry the original profile
    // cache selection if its stored format is incompatible.
    const int avatar_fd=open(image,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
    if(avatar_fd<0)return 0;
    struct stat st;
    int valid=fstat(avatar_fd,&st)==0 && S_ISREG(st.st_mode) &&
              st.st_size>=144 && st.st_size<=2*1024*1024;
    unsigned char header[128];
    if(valid) {
        size_t loaded=0;
        while(loaded<sizeof(header)) {
            const ssize_t n=read(avatar_fd,header+loaded,sizeof(header)-loaded);
            if(n<0 && errno==EINTR)continue;
            if(n<=0)break;
            loaded+=(size_t)n;
        }
        valid=loaded==sizeof(header);
    }
    if(close(avatar_fd)!=0)valid=0;
    if(!valid)return 0;
    if(strcmp(marker+n,"dds\\n")==0)
        return niak_avatar_dds_supported(header,(size_t)st.st_size);
    static const unsigned char png[8]={137,80,78,71,13,10,26,10};
    return memcmp(header,png,sizeof(png))==0 &&
           memcmp(header+12,"IHDR",4)==0;
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
/* PLDmgr may execute the same ELF twice. Check whether OUR local protocol
 * already owns the port instead of reporting a second broker as a failure. */
static int broker_already_ready(void) {
    const int probe=socket(AF_INET,SOCK_STREAM,0);
    if(probe<0)return 0;
    niak_socket_guard(probe);
    struct timeval timeout={0,200000};
    (void)setsockopt(probe,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
    (void)setsockopt(probe,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
    struct sockaddr_in peer={0};
    peer.sin_family=AF_INET;
    peer.sin_port=htons(19187);
    peer.sin_addr.s_addr=htonl(0x7f000001u);
    int ok=niak_connect_bounded(probe,(struct sockaddr*)&peer,sizeof(peer),100)==0;
    if(ok)ok=niak_socket_send(probe,"PING\n",5)==5;
    char reply[5]={0};size_t got=0;
    while(ok && got<sizeof(reply)) {
        const ssize_t n=recv(probe,reply+got,sizeof(reply)-got,0);
        if(n<=0){ok=0;break;}
        got+=(size_t)n;
    }
    close(probe);
    return ok && got==5 && memcmp(reply,"PONG\n",5)==0;
}
static void serve_launch_requests(void) {
    if(broker_already_ready()) {
        report("Local broker already running",0);
        return;
    }
    const int fd=socket(AF_INET,SOCK_STREAM,0);
    if(fd<0){report("Local launch broker socket unavailable",fd);return;}
    niak_socket_guard(fd);
    int yes=1;(void)setsockopt(fd,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));
    struct sockaddr_in addr={0};
    addr.sin_family=AF_INET;
    addr.sin_port=htons(19187);
    addr.sin_addr.s_addr=htonl(0x7f000001u);
    if(bind(fd,(struct sockaddr*)&addr,sizeof(addr))!=0) {
        const int problem=errno;
        if(problem==EADDRINUSE && broker_already_ready())
            report("Local broker already running",0);
        else report("Local launch broker bind refused",problem);
        close(fd);return;
    }
    if(listen(fd,3)!=0) {
        report("Local launch broker listen refused",errno);close(fd);return;
    }
    report("Local launch broker ready (127.0.0.1 only)",0);
    /* The ELF loader may host the payload in a differently named process.
     * Record actual PID and one low-frequency heartbeat instead of assuming
     * it appears under niakps5.elf in a process scanner.
     */
    report("NiakPS5 broker process PID",(int)getpid());
    NiakRedirectGate gate;
    int gate_ready=0,return_user=-1;
    // Listen for launcher PING/GAMES immediately. Previously a 12x3-second
    // autostart polling loop delayed the launch broker by up to 36 seconds.
    unsigned startup_attempts=0;
    int startup_done=0,profile_checked=0,staged_profile_user=-1;
    uint64_t next_start_ms=0, next_heartbeat_ms=0, next_avatar_ms=0;
    uint64_t started_at_ms=0;
    // The original 21,600 two-second iterations silently stopped the
    // launch service after roughly twelve hours. Keep the opt-in broker
    // alive until the user disables it or the console shuts down.
    for(;;) {
        if(is_regular_file(NIAK_DISABLED))break;
        const uint64_t now=niak_monotonic_ms();
        if(now>=next_heartbeat_ms) {
            // PING may be blocked by the sandbox, while the UI can read our
            // existing /data log. Publish a read-only game ID snapshot
            // separately so no TCP or root privilege is required in the UI.
            char inventory[8192]={0};
            const int count=niak_broker_inventory(inventory,sizeof(inventory),"");
            if(count>=0) {
                const long long stamp=(long long)time(NULL);
                /* Stage to the mounted title's assets so /app0 can read it
                 * without depending on sandbox access to the /data root. */
                if(niak_snapshot_write(NIAK_SNAPSHOT_APP_SOURCE,inventory,
                                       count,stamp)==0)
                    report("NiakPS5 app snapshot installed titles",count);
                else report("NiakPS5 app snapshot write refused",errno);
                if(niak_snapshot_write(NIAK_SNAPSHOT_FILE,inventory,
                                       count,stamp)==0)
                    report("NiakPS5 legacy snapshot installed titles",count);
                else report("NiakPS5 legacy snapshot write refused",errno);
                // Preserve media/app category from the privileged, live
                // installed manifests. The old GAMES socket only sends IDs.
                char app_ids[8192]={0};
                const int apps=niak_broker_apps_from_inventory(
                    inventory,app_ids,sizeof(app_ids),"");
                if(apps>=0) {
                    (void)niak_snapshot_write(NIAK_APPS_SNAPSHOT_APP_SOURCE,
                                              app_ids,apps,stamp);
                    (void)niak_snapshot_write(NIAK_APPS_SNAPSHOT_FILE,
                                              app_ids,apps,stamp);
                    report("NiakPS5 verified installed applications",apps);
                }
            } else report("NiakPS5 broker inventory roots inaccessible",count);
            // The active profile cache may become readable AFTER the GUI
            // starts or after a profile switch. Retry on the already bounded
            // heartbeat without touching an unrelated account's image.
            int avatar_user=-1;
            if(sceUserServiceGetForegroundUser(&avatar_user)==0 &&
               avatar_user>=0 &&
               now>=next_avatar_ms) {
                // A success is not permanent: FTP updates can remove the
                // staged file or the binding to this foreground account.
                const int still_staged=profile_checked &&
                    avatar_user==staged_profile_user &&
                    current_avatar_asset_staged(avatar_user);
                if(!still_staged)
                    profile_checked=copy_current_avatar_png(avatar_user);
                staged_profile_user=avatar_user;
                // Missing assets retry soon; verified assets only receive
                // one inexpensive stat/marker check every two minutes.
                next_avatar_ms=now+(profile_checked?120000u:30000u);
            }
            report("NiakPS5 broker heartbeat PID",(int)getpid());
            // Timestamp each heartbeat so offline FTP diagnostics can tell
            // an old journal from evidence of recent service activity.
            FILE *heartbeat=fopen(NIAK_LOG,"a");
            if(heartbeat) {
                fprintf(heartbeat,"NiakPS5 broker heartbeat epoch=%lld pid=%u\n",
                        (long long)time(NULL),(unsigned)getpid());
                fclose(heartbeat);
            }
            next_heartbeat_ms=now+120000u;
        }
        // The title may be registered by ShadowMountPlus AFTER the 36-second
        // PLDmgr startup window. Retain a bounded ten-minute readiness window,
        // with slow follow-up attempts and no interruption of another big app.
        // After the window the broker stays resident for PING/GAMES/LAUNCH.
        if(!started_at_ms)started_at_ms=now?now:1;
        const uint64_t elapsed_ms=now>=started_at_ms?now-started_at_ms:0;
        if(!startup_done && elapsed_ms<600000u && now>=next_start_ms) {
            ++startup_attempts;
            next_start_ms=now+(startup_attempts<=12?3000u:30000u);
            const int running=sceSystemServiceGetAppIdOfRunningBigApp();
            if(running<=0) {
                int user=-1;
                const int user_rc=sceUserServiceGetForegroundUser(&user);
                if(user_rc==0 && user>=0) {
                    if((!profile_checked || user!=staged_profile_user) &&
                       now>=next_avatar_ms) {
                        profile_checked=copy_current_avatar_png(user);
                        staged_profile_user=user;
                        next_avatar_ms=now+30000u;
                    }
                    const int rc=launch_title_as_user(NIAK_TITLE,user);
                    if(rc==0)startup_done=1;
                } else report("Foreground user unavailable",user_rc);
            }
        }
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
                    report("Local installed title inventory",n);
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
                // Fixed settings deep link from the already privileged
                // broker; no arbitrary URI or client-controlled parameters.
                if(count==9 && memcmp(request,"SETTINGS\n",9)==0) {
                    const int settings_rc=niak_open_settings_from_broker();
                    report("NiakPS5 broker system settings",settings_rc);
                    char response[24];
                    const int length=snprintf(response,sizeof(response),
                        "RC %08X\n",(unsigned)settings_rc);
                    if(length==12)
                        (void)niak_socket_send(client,response,12);
                    close(client);continue;
                }
                // Exact local status: broker PID, not arbitrary process enumeration.
                if(count==7 && memcmp(request,"STATUS\n",7)==0) {
                    char status[20];
                    const int n=snprintf(status,sizeof(status),"PID %08X\n",
                                         (unsigned)getpid());
                    if(n>0 && n<(int)sizeof(status))
                        (void)niak_socket_send(client,status,(size_t)n);
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
                            result=launch_title_as_user(title,user);
                            report("Local title launch request",result);
                            // The return gate is opt-in, and only the launch
                            // we explicitly requested may arm it. Merely
                            // seeing some other bigapp never arms a redirect.
                            /* Only an explicit Niak launch can arm this one-shot
                             * redirect. An opt-out marker disables it. */
                            gate_ready=niak_redirect_arm_after_launch(
                                &gate,!is_regular_file(NIAK_RESUME_DISABLED),
                                source_app,result);
                            return_user=gate_ready?user:-1;
                            report("Return gate source app",source_app);
                            report("Return gate armed",gate_ready);
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
        if(is_regular_file(NIAK_RESUME_DISABLED)) {
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
            const int rc=launch_title_as_user(NIAK_TITLE,user);
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
    /* On PS5 this FreeBSD syscall names the executing payload thread, which
     * is visible in common process/thread scanners instead of payload.elf.
     * The external ELF loader may still control the executable filename. */
#ifdef SYS_thr_set_name
    (void)syscall(SYS_thr_set_name,-1,"NiakPS5");
#endif
    if(is_regular_file(NIAK_DISABLED))return 0;
    report("NiakPS5 optional autostart start",0);
    /* Raw PLDmgr ELFs do not inherit a UI title's UserService init.
     * Without this, GetForegroundUser fails with 0x80960002. */
    const int user_service_rc=sceUserServiceInitialize(NULL);
    report("UserService initialize",user_service_rc);
    /* LncUtil has a separate initializer on firmware 13.60. The fallback
     * cannot be assumed usable merely because UserService is initialized. */
    const int lnc_init_rc=sceLncUtilInitialize();
    report("LncUtil initialize",lnc_init_rc);
    // The local broker becomes available before console autostart attempts.
    // A manually launched UI can contact it even while the payload is still
    // waiting for the current foreground user or a free big-app slot.
    serve_launch_requests();
    return 0;
}
