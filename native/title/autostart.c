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
                ok=n==(ssize_t)size && fsync(fd)==0 && rename(temp,dest)==0;
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

/* A voluntary, low-frequency monitor for the transition game -> Sony Home.
 * We never read PS-button state and never forcibly focus over a running game.
 */
static void monitor_return_after_game(void) {
    if (!is_regular_file(NIAK_RESUME)) return;
    int home_app=-1;
    for (int i=0;i<10;++i) {
        if (is_regular_file(NIAK_DISABLED)) return;
        sceKernelUsleep(2000000);
        const int running=sceSystemServiceGetAppIdOfRunningBigApp();
        if (running>0) {home_app=running;break;}
    }
    if (home_app<=0) {
        report("Cannot identify NiakPS5 big-app id; return monitoring disabled",home_app);
        return;
    }
    report("Opt-in return monitor armed, NiakPS5 app id",home_app);
    NiakRedirectGate gate;
    niak_redirect_init(&gate,home_app);
    for(int ticks=0;ticks<21600;++ticks) {
        if(is_regular_file(NIAK_DISABLED)||!is_regular_file(NIAK_RESUME))break;
        sceKernelUsleep(2000000);
        const int running=sceSystemServiceGetAppIdOfRunningBigApp();
        if(!niak_redirect_tick(&gate,running))continue;
        // A running game (including one behind the PS Control Center) cannot
        // produce this event.  Exactly one attempt, no relaunch loop.
        int user=-1;
        if(sceUserServiceGetForegroundUser(&user)==0 && user>=0) {
            const int rc=sceSystemServiceLaunchApp(NIAK_TITLE,NULL,NULL);
            report("NiakTV-style game-exit redirect (one attempt)",rc);
            if(rc==0) {
                home_app=-1;
                for(int i=0;i<8;++i) {
                    sceKernelUsleep(1500000);
                    const int app=sceSystemServiceGetAppIdOfRunningBigApp();
                    if(app>0){home_app=app;break;}
                }
                if(home_app>0) {
                    niak_redirect_init(&gate,home_app);
                    continue;
                }
            }
        }
        // No retries if the user intentionally remains in Sony settings,
        // or if the launch failed: always leave an escape hatch.
        break;
    }
    report("Return monitor exit",0);
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
                monitor_return_after_game();
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
