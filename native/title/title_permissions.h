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
#include <fcntl.h>
#include <unistd.h>
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
        /* Resolve each trusted component relative to an already-opened
         * directory. A symlink swap cannot replace the checked inode.
         */
        const int title_fd=open(path,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
        if(title_fd<0)continue;
        struct stat installed;
        if(fstat(title_fd,&installed)!=0 || !S_ISDIR(installed.st_mode)){
            close(title_fd);continue;
        }
        if(strncmp(id,"NPXS",4)!=0){close(title_fd);return 1;}
        const int sys_fd=openat(title_fd,"sce_sys",
                                O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
        close(title_fd);
        if(sys_fd<0)continue;
        const int param_fd=openat(sys_fd,"param.json",
                                  O_RDONLY|O_NONBLOCK|O_NOFOLLOW);
        close(sys_fd);
        if(param_fd<0)continue;
        struct stat meta_stat;
        if(fstat(param_fd,&meta_stat)!=0 ||
           !S_ISREG(meta_stat.st_mode) ||
           meta_stat.st_size<30 || meta_stat.st_size>65536){
            close(param_fd);continue;
        }
        FILE *meta=fdopen(param_fd,"rb");
        if(!meta){close(param_fd);continue;}
        char data[65537]={0};
        const size_t size=fread(data,1,sizeof(data)-1,meta);
        const int bad=ferror(meta) || size!=(size_t)meta_stat.st_size;
        fclose(meta);
        if(!bad && niak_is_installed_media_category_for_title(data,id))return 1;
    }
    return 0;
}
#endif
