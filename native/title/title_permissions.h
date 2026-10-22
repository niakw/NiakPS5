/* SPDX-License-Identifier: GPL-3.0-or-later
 * Only locally installed game directories and explicitly classified
 * NPXS media applications can be launched by the loopback broker.
 * Injectable trusted roots allow full filesystem permission tests on host.
 */
#ifndef NIAK_TITLE_PERMISSIONS_H
#define NIAK_TITLE_PERMISSIONS_H
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include "title_category.h"

static inline int niak_title_is_launchable(
    const char *id,const char *own_title,
    const char *const *roots,size_t root_count) {
    if(!id || !own_title || !roots || strlen(id)!=9 ||
       strcmp(id,own_title)==0 ||
       (strncmp(id,"PPSA",4)!=0 && strncmp(id,"CUSA",4)!=0 &&
        strncmp(id,"LAPY",4)!=0 && strncmp(id,"FAKE",4)!=0 &&
        strncmp(id,"NPXS",4)!=0))return 0;
    for(int i=4;i<9;++i)
        if(id[i]<'0'||id[i]>'9')return 0;
    for(size_t i=0;i<root_count;++i) {
        char path[192];
        if(!roots[i])continue;
        const size_t root_len=strlen(roots[i]);
        if(root_len==0)continue;
        const int len=snprintf(path,sizeof(path),"%s%s%s",roots[i],
                               roots[i][root_len-1]=='/'?"":"/",id);
        if(len<=0 || (size_t)len>=sizeof(path))continue;
        struct stat installed;
        // Refuse symlink names masquerading as installed titles. Do not
        // follow arbitrary directories into the system filesystem.
        if(lstat(path,&installed)!=0 || !S_ISDIR(installed.st_mode))continue;
        if(strncmp(id,"NPXS",4)!=0)return 1;
        char meta_dir[240],meta_path[256];
        const int dir_len=snprintf(meta_dir,sizeof(meta_dir),
                                   "%s/sce_sys",path);
        if(dir_len<=0 || (size_t)dir_len>=sizeof(meta_dir))continue;
        struct stat meta_folder;
        // Prevent a symlinked metadata folder from authorizing a protected
        // NPXS service using a JSON file from another installation.
        if(lstat(meta_dir,&meta_folder)!=0 ||
           !S_ISDIR(meta_folder.st_mode))continue;
        const int n=snprintf(meta_path,sizeof(meta_path),
                             "%s/param.json",meta_dir);
        if(n<=0 || (size_t)n>=sizeof(meta_path))continue;
        struct stat meta_stat;
        if(lstat(meta_path,&meta_stat)!=0 ||
           !S_ISREG(meta_stat.st_mode) ||
           meta_stat.st_size<30 || meta_stat.st_size>65536)continue;
        FILE *meta=fopen(meta_path,"rb");
        if(!meta)continue;
        char data[65537]={0};
        const size_t size=fread(data,1,sizeof(data)-1,meta);
        const int bad=ferror(meta) || size!=(size_t)meta_stat.st_size;
        fclose(meta);
        if(!bad && niak_is_installed_media_category_for_title(data,id))return 1;
    }
    return 0;
}
#endif
