/* SPDX-License-Identifier: GPL-3.0-or-later
 * Read-only fixed-root installed title inventory. No paths or user files
 * pass between the PLDmgr ELF and the sandboxed graphical application.
 */
#ifndef NIAK_BROKER_INVENTORY_H
#define NIAK_BROKER_INVENTORY_H
#include <dirent.h>
#include <stdio.h>
#include <string.h>
#include <stddef.h>
#include <sys/stat.h>
#include "title_category.h"
static inline int niak_broker_id(const char *id) {
 if(!id||strlen(id)!=9)return 0;
 if(strncmp(id,"PPSA",4)&&strncmp(id,"CUSA",4)&&
    strncmp(id,"LAPY",4)&&strncmp(id,"FAKE",4)&&
    strncmp(id,"NPXS",4))return 0;
 for(int i=4;i<9;i++)if(id[i]<'0'||id[i]>'9')return 0;
 return 1;
}
static inline int niak_broker_is_file(const char *p) {
 struct stat st;return lstat(p,&st)==0&&S_ISREG(st.st_mode);
}
/* NPXS includes shell services: expose only explicitly categorized media. */
static inline int niak_broker_media(const char *path,const char *id) {
 FILE *f=fopen(path,"rb");if(!f)return 0;
 char json[32769];const size_t n=fread(json,1,sizeof(json),f);
 const int complete=feof(f);fclose(f);
 if(!complete || n<10 || n>=sizeof(json))return 0;
 json[n]=0;
 return niak_is_installed_media_category_for_title(json,id);
}
static inline int niak_broker_is_dir(const char *p) {
 struct stat st;return lstat(p,&st)==0&&S_ISDIR(st.st_mode);
}
/* Each record is EXACTLY 9 ASCII ID bytes and newline; NUL terminator.
 * Cap the result at 512 IDs. -1 means all fixed roots were inaccessible.
 * Nonempty root is used by host filesystem fixture tests only. */
static inline int niak_broker_inventory(char *out,size_t cap,const char *root) {
 static const char *const roots[]={"/user/app","/system_ex/app",
   "/mnt/ext0/user/app","/mnt/ext1/user/app","/data/homebrew"};
 if(!out||cap<12||!root)return -1;
 size_t used=0;int accessible=0,total=0;out[0]=0;
 for(size_t k=0;k<sizeof(roots)/sizeof(roots[0]);++k) {
  char top[512];
  int n=snprintf(top,sizeof(top),"%s%s",root,roots[k]);
  if(n<0||(size_t)n>=sizeof(top))continue;
  DIR *dir=opendir(top);
  if(!dir)continue;
  accessible=1;struct dirent *entry;
  while((entry=readdir(dir)) && total<512) {
   const char *id=entry->d_name;
   if(!niak_broker_id(id)||strcmp(id,"PPSA99386")==0)continue;
   char base[576],meta[640],eboot[640],pkg[640];
   n=snprintf(base,sizeof(base),"%s/%s",top,id);
   if(n<0||(size_t)n>=sizeof(base)||!niak_broker_is_dir(base))continue;
   snprintf(meta,sizeof(meta),"%s/sce_sys/param.json",base);
   snprintf(eboot,sizeof(eboot),"%s/eboot.bin",base);
   snprintf(pkg,sizeof(pkg),"%s/app.pkg",base);
   if(!niak_broker_is_file(meta)&&!niak_broker_is_file(eboot)&&
      !niak_broker_is_file(pkg))continue;
   if(strncmp(id,"NPXS",4)==0 &&
      (!niak_broker_is_file(meta)||!niak_broker_media(meta,id)))continue;
   int duplicate=0;
   for(size_t pos=0;pos+10<=used;pos+=10)
    if(memcmp(out+pos,id,9)==0){duplicate=1;break;}
   if(duplicate||used+11>cap)continue;
   memcpy(out+used,id,9);out[used+9]='\n';
   used+=10;out[used]=0;total++;
  }
  closedir(dir);
 }
 return accessible?total:-1;
}
/* A second, bounded inventory records only application IDs from the
 * already-validated live GAMES list. Homebrew param.json often uses native
 * game category 0 even for utility launchers. A verified media category or
 * recognized launcher title in its OWN installed manifest makes it an app.
 * Unknown NPXS shell services remain excluded by niak_broker_inventory.
 */
static inline int niak_broker_apps_from_inventory(const char *ids,
                                                  char *apps,size_t cap,
                                                  const char *root) {
 if(!ids||!apps||cap<2||!root)return -1;
 static const char *const roots[]={"/user/app","/system_ex/app",
   "/mnt/ext0/user/app","/mnt/ext1/user/app","/data/homebrew"};
 apps[0]=0;size_t used=0;int count=0;
 const char *cursor=ids;
 while(*cursor) {
  if(strlen(cursor)<10 || cursor[9]!='\n')return -1;
  char id[10];memcpy(id,cursor,9);id[9]=0;cursor+=10;
  if(!niak_broker_id(id))return -1;
  int is_app=0;
  for(size_t k=0;k<sizeof(roots)/sizeof(roots[0]);++k) {
   char file[800];
   const int n=snprintf(file,sizeof(file),
       "%s%s/%s/sce_sys/param.json",root,roots[k],id);
   if(n<=0||(size_t)n>=sizeof(file)||!niak_broker_is_file(file))continue;
   FILE *f=fopen(file,"rb");if(!f)continue;
   char json[32769]={0};
   const size_t size=fread(json,1,sizeof(json)-1,f);
   const int complete=feof(f);
   fclose(f);
   if(!complete||size<12||size>=sizeof(json))continue;
   if(niak_is_installed_media_category_for_title(json,id)) {
       is_app=1;break;
   }
   // Only apply these named launchers to non-NPXS *installed* titles.
   // Strings here classify shelf presentation, not execution rights.
   if(strncmp(id,"NPXS",4)!=0 &&
      (strstr(json,"ShadowMount")||strstr(json,"shadowmount")||
       strstr(json,"Eden Encore")||strstr(json,"Eden-Encore")||
       strstr(json,"Mes vid")||strstr(json,"My Videos"))) {
       is_app=1;break;
   }
  }
  if(is_app) {
   if(used+11>cap)return -1;
   memcpy(apps+used,id,9);apps[used+9]='\n';
   used+=10;apps[used]=0;++count;
  }
 }
 return count;
}
#endif
