/* SPDX-License-Identifier: GPL-3.0-or-later */
/* NiakPS5 read-only preflight payload. No kernel privileges, ptrace, mounts or app launches. */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <limits.h>

#define DIAG_LOG "/data/niakps5-diagnostic.log"
#define UI_PATH "/data/niakps5/niakps5_ui.elf"
#define FONT_MANROPE "/data/niakps5/assets/manrope.ttf"
#define FONT_SERIF "/data/niakps5/assets/instrument-serif.ttf"
#define LEGACY_BASE "/system_ex/app/NPXS40106/eboot.bin"
#define FAKE_EBOOT "/system_ex/app/FAKE00000/eboot.bin"
#define FAKE_META "/system_ex/app/FAKE00000/sce_sys/param.json"

#ifdef __PS5__
typedef struct {char reserved[45];char message[3075];} NiakNotice;
extern int sceKernelSendNotificationRequest(int,void *,size_t,int);
static void show_notice(const char *message) {
 NiakNotice notice={0};
 snprintf(notice.message,sizeof(notice.message),"%s",message);
 sceKernelSendNotificationRequest(0,&notice,sizeof(notice),0);
}
#else
static void show_notice(const char *message) {fprintf(stdout,"NOTICE: %s\n",message);}
#endif

static int path_from_root(char *out,size_t cap,const char *absolute){
 const char *root="";
#ifndef __PS5__
 const char *test=getenv("NIAK_DIAG_ROOT");
 if(test && *test)root=test;
#endif
 int n=snprintf(out,cap,"%s%s",root,absolute);
 return n>0 && (size_t)n<cap;
}
static int regular_file(const char *path,long *size){
 char full[1024];struct stat st;
 if(!path_from_root(full,sizeof full,path) || stat(full,&st)!=0 || !S_ISREG(st.st_mode))return 0;
 if(size)*size=(long)st.st_size;
 return 1;
}
static int valid_elf(const char *path){
 char full[1024];unsigned char magic[4];FILE *f;
 if(!path_from_root(full,sizeof full,path))return 0;
 f=fopen(full,"rb");
 if(!f)return 0;
 size_t n=fread(magic,1,sizeof magic,f);
 fclose(f);
 return n==4 && magic[0]==0x7f && magic[1]=='E' && magic[2]=='L' && magic[3]=='F';
}
static void report(FILE *log,const char *name,const char *path,int available){
 char row[1152];
 snprintf(row,sizeof row,"%s %s: %s",available?"OK":"ABSENT",name,path);
 puts(row);
 if(log){fprintf(log,"%s\n",row);fflush(log);}
}
int main(void){
 char log_path[1024];
 FILE *log=NULL;
 if(path_from_root(log_path,sizeof log_path,DIAG_LOG)){
  /* Diagnostic only: the sole intended write is /data/niakps5-diagnostic.log */
  log=fopen(log_path,"w");
 }
 if(log)fprintf(log,"NiakPS5 diagnostic v1 (read-only checks, no launches)\n");
 int ui=valid_elf(UI_PATH);
 int manrope=regular_file(FONT_MANROPE,NULL);
 int serif=regular_file(FONT_SERIF,NULL);
 int base=regular_file(LEGACY_BASE,NULL);
 int fake_exe=regular_file(FAKE_EBOOT,NULL);
 int fake_meta=regular_file(FAKE_META,NULL);
 report(log,"interface ELF",UI_PATH,ui);
 report(log,"font Manrope",FONT_MANROPE,manrope);
 report(log,"font Instrument Serif",FONT_SERIF,serif);
 report(log,"legacy PS Now eboot",LEGACY_BASE,base);
 report(log,"legacy fakeapp eboot",FAKE_EBOOT,fake_exe);
 report(log,"legacy fakeapp metadata",FAKE_META,fake_meta);
 char status[280];
 if(!ui) snprintf(status,sizeof status,"NiakPS5: UI absente ou ELF invalide. Voir /data/niakps5-diagnostic.log");
 else if(!manrope || !serif)snprintf(status,sizeof status,"NiakPS5: polices absentes. Voir /data/niakps5-diagnostic.log");
 else if(!base && !(fake_exe&&fake_meta))snprintf(status,sizeof status,"NiakPS5: PS Now/fakeapp absents; ancien chargeur incompatible.");
 else snprintf(status,sizeof status,"NiakPS5: fichiers detectes. Bigapp non teste sur ce firmware.");
 if(log){
  fprintf(log,"RESULTAT: %s\n",status);
  fprintf(log,"Cette verification ne prouve pas la compatibilite du lanceur PS5.\n");
  fprintf(log,"Aucun montage systeme, lancement ou elevation de privileges n'a ete effectue.\n");
  fclose(log);
 }
 show_notice(status);
 return ui&&manrope&&serif?0:2;
}
