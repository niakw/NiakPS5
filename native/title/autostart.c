/* SPDX-License-Identifier: GPL-3.0-or-later
 * NiakPS5 optional autostart payload for the already-jailbroken console.
 * NOT a ShellUI replacement, memory patch, hbldr, SceSysCore hook, or GUI.
 * Opt-in only. The homebrew title remains a normal app with a normal exit.
 */
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/stat.h>
#include <unistd.h>

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
    int game_running=0;
    int idle_ticks=0;
    for (int ticks=0;ticks<21600;++ticks) { /* at most 12 hours */
        if (is_regular_file(NIAK_DISABLED)||!is_regular_file(NIAK_RESUME))break;
        sceKernelUsleep(2000000);
        const int running=sceSystemServiceGetAppIdOfRunningBigApp();
        if (running>0 && running!=home_app) {
            /* The PS button may open Sony controls while this game stays running.
             * Never start NiakPS5 over a live title. */
            game_running=1;
            idle_ticks=0;
        } else if (running==home_app) {
            game_running=0;
            idle_ticks=0;
        } else if (running==0 && game_running) {
            if (++idle_ticks>=5) {
                int user=-1;
                if (sceUserServiceGetForegroundUser(&user)==0 && user>=0) {
                    const int rc=sceSystemServiceLaunchApp(NIAK_TITLE,NULL,NULL);
                    report("Return after game exit (best effort)",rc);
                    if (rc==0) {
                        game_running=0;
                        idle_ticks=0;
                        home_app=-1;
                        for(int i=0;i<8;++i) {
                            sceKernelUsleep(1500000);
                            const int app=sceSystemServiceGetAppIdOfRunningBigApp();
                            if(app>0){home_app=app;break;}
                        }
                        if(home_app<=0)break;
                    } else {
                        /* Do not retry relentlessly while Sony is handling settings. */
                        break;
                    }
                } else break;
            }
        }
    }
    report("Return monitor exit",0);
}
int main(void) {
    if(!is_regular_file(NIAK_ENABLED)||is_regular_file(NIAK_DISABLED))return 0;
    report("NiakPS5 optional autostart start",0);
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
