/* SPDX-License-Identifier: GPL-3.0-or-later
 * NiakPS5 optional autostart payload for the already-jailbroken console.
 * NOT a ShellUI replacement, memory patch, hbldr, SceSysCore hook, or GUI.
 * Opt-in only. The homebrew title remains a normal app with a normal exit.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/stat.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <sys/time.h>
#include "redirect_gate.h"

#define NIAK_TITLE "PPSA99386"
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
            snprintf(temp,sizeof(temp),"%s.tmp",dest);
            const int fd=open(temp,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
            if(fd>=0) {
                const ssize_t n=write(fd,data,size);
                ok=n==(ssize_t)size && fchmod(fd,0644)==0 && fsync(fd)==0 && rename(temp,dest)==0;
                close(fd);
                if(!ok)unlink(temp);
            }else ok=0;
        }else ok=0;
    }
    free(data);return ok;
}
static void copy_current_avatar_png(int user) {
    if(user<0)return;
    char profile[256],source[320];
    snprintf(profile,sizeof(profile),
             "/system_data/priv/cache/profile/0x%08X",(unsigned)user);
    static const unsigned char png[8]={137,80,78,71,13,10,26,10};
    static const unsigned char dds[4]={'D','D','S',' '};
    snprintf(source,sizeof(source),"%s/avatar.png",profile);
    if(copy_profile_image(source,"/data/homebrew/PPSA99386/assets/niak-profile.png",png,8)) {
        report("Current user PNG avatar staged",0);
        return;
    }
    for(int i=0;i<3;++i) {
        const char *name=i==0?"avatar128.dds":i==1?"avatar260.dds":"avatar64.dds";
        snprintf(source,sizeof(source),"%s/%s",profile,name);
        if(copy_profile_image(source,"/data/homebrew/PPSA99386/assets/niak-profile.dds",dds,4)) {
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
    if(!id||strlen(id)!=9||
       (strncmp(id,"PPSA",4)!=0 && strncmp(id,"CUSA",4)!=0 &&
        strncmp(id,"LAPY",4)!=0 && strncmp(id,"FAKE",4)!=0 &&
        strncmp(id,"NPXS",4)!=0)||
       strcmp(id,NIAK_TITLE)==0)return 0;
    for(int i=4;i<9;++i)if(id[i]<'0'||id[i]>'9')return 0;
    const char *roots[]={"/user/app/","/system_ex/app/","/data/homebrew/",
                         "/mnt/ext0/user/app/","/mnt/ext1/user/app/"};
    char path[192];struct stat st;
    for(size_t i=0;i<sizeof(roots)/sizeof(roots[0]);++i) {
        int n=snprintf(path,sizeof(path),"%s%s",roots[i],id);
        if(n>0&&n<(int)sizeof(path) && stat(path,&st)==0 && S_ISDIR(st.st_mode)) {
            if(strncmp(id,"NPXS",4)!=0)return 1;
            char meta_path[256];
            int k=snprintf(meta_path,sizeof(meta_path),"%s/sce_sys/param.json",path);
            if(k<=0||k>=(int)sizeof(meta_path))continue;
            FILE *meta=fopen(meta_path,"rb");if(!meta)continue;
            char data[32769]={0};
            size_t size=fread(data,1,sizeof(data)-1,meta);
            fclose(meta);
            if(size<30)continue;
            // Only media apps. Internal system/services use different values.
            const char *v=strstr(data,"applicationCategoryType");
            if(!v || !(v=strchr(v,':')))continue;
            const long category=strtol(v+1,NULL,10);
            if(category==65536||category==65792||category==66048)
                return 1;
        }
    }
    return 0;
}
static void serve_launch_requests(void) {
    const int fd=socket(AF_INET,SOCK_STREAM,0);
    if(fd<0){report("Local launch broker socket unavailable",fd);return;}
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
    int current_niak=-1, gate_ready=0;
    for(int ticks=0;ticks<21600;++ticks) {
        if(is_regular_file(NIAK_DISABLED)||!is_regular_file(NIAK_ENABLED))break;
        fd_set pending;FD_ZERO(&pending);FD_SET(fd,&pending);
        struct timeval tv={2,0};
        const int available=select(fd+1,&pending,NULL,NULL,&tv);
        if(available>0 && FD_ISSET(fd,&pending)) {
            int client=accept(fd,NULL,NULL);
            if(client>=0) {
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
                // A read-only PING makes actual PLDmgr residency testable
                // without launching anything or depending on historical logs.
                if(count==5 && memcmp(request,"PING\n",5)==0) {
                    (void)send(client,"PONG\n",5,0);
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
                            result=sceSystemServiceLaunchApp(title,NULL,NULL);
                            report("Local title launch request",result);
                        }
                    }
                }
                char response[32];
                int n=snprintf(response,sizeof(response),
                               "RC %08X\n",(unsigned)result);
                if(n>0&&n<(int)sizeof(response))
                    (void)send(client,response,(size_t)n,0);
                close(client);
            }
        }
        if(!is_regular_file(NIAK_RESUME))continue;
        const int running=sceSystemServiceGetAppIdOfRunningBigApp();
        if(!gate_ready) {
            if(running>0) {
                current_niak=running;
                niak_redirect_init(&gate,current_niak);
                gate_ready=1;
            }
            continue;
        }
        if(!niak_redirect_tick(&gate,running))continue;
        int user=-1;
        if(sceUserServiceGetForegroundUser(&user)==0 && user>=0) {
            const int rc=sceSystemServiceLaunchApp(NIAK_TITLE,NULL,NULL);
            report("Optional game-exit return",rc);
            gate_ready=0;current_niak=-1;
        }
    }
    close(fd);
    report("Local launch broker shutdown",0);
}
int main(void) {
    if(!is_regular_file(NIAK_ENABLED)||is_regular_file(NIAK_DISABLED))return 0;
    report("NiakPS5 optional autostart start",0);
    int profile_checked=0;
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
                serve_launch_requests();
                return 0;
            }
        } else {
            report("Foreground user unavailable",user_rc);
        }
        sceKernelUsleep(3000000);
    }
    report("Autostart gave up: no system partition or title modified",0);
    return 1;
}
