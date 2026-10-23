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
static inline int niak_broker_id(const char *id) {
 if(!id||strlen(id)!=9)return 0;
 if(strncmp(id,"PPSA",4)&&strncmp(id,"CUSA",4)&&
    strncmp(id,"LAPY",4)&&strncmp(id,"FAKE",4))return 0;
 for(int i=4;i<9;i++)if(id[i]<'0'||id[i]>'9')return 0;
 return 1;
}
static inline int niak_broker_is_file(const char *p) {
 struct stat st;return lstat(p,&st)==0&&S_ISREG(st.st_mode);
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
#endif
