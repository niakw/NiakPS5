/* SPDX-License-Identifier: GPL-3.0-or-later
 * Read-only copy of a previous owner's FTP-installed title inventory.
 * Used ONLY when live catalogue sources all fail. No assertion that these
 * titles are currently installed/launchable; never executes or opens titles.
 */
#ifndef NIAK_LOCAL_INVENTORY_H
#define NIAK_LOCAL_INVENTORY_H
#include "catalog.h"
#include <stdio.h>
#include <string.h>
static inline int niak_scan_local_inventory(const char *path,
                                            NiakGame *games,size_t capacity) {
    if(!path||!games||!capacity)return -1;
    FILE *input=fopen(path,"rb");
    if(!input)return -1;
    if(fseek(input,0,SEEK_END)!=0){fclose(input);return -1;}
    const long length=ftell(input);
    if(length<0||length>512*1024L||fseek(input,0,SEEK_SET)!=0){
        fclose(input);return -1;
    }
    char line[512];
    size_t count=0;
    while(count<capacity && fgets(line,sizeof(line),input)) {
        const char *first=strchr(line,'\t');
        if(!first || (size_t)(first-line)!=9)continue;
        char id[10]={0};
        memcpy(id,line,9);
        const int media=strncmp(id,"NPXS",4)==0;
        if(!media && strncmp(id,"PPSA",4)!=0 &&
           strncmp(id,"CUSA",4)!=0 && strncmp(id,"LAPY",4)!=0 &&
           strncmp(id,"FAKE",4)!=0)continue;
        int valid=1;
        for(int i=4;i<9;++i)if(id[i]<'0'||id[i]>'9')valid=0;
        if(!valid||strcmp(id,"PPSA99386")==0)continue;
        const char *name=first+1;
        const char *second=strchr(name,'\t');
        if(!second||second-name<1||second-name>=192)continue;
        for(const char *p=name;p<second;++p)
            if((unsigned char)*p<32 || (unsigned char)*p==127)valid=0;
        if(!valid)continue;
        const char *category=second+1;
        const char *end=strchr(category,'\t');
        if(!end)continue;
        const size_t type_len=(size_t)(end-category);
        int type=0;
        if(type_len==3 && memcmp(category,"Jeu",3)==0)type=1;
        else if(type_len==11 && memcmp(category,"Application",11)==0)type=2;
        else if(type_len!=0)continue;
        /* NPXS system services cannot be shown without verified app type. */
        if(media&&type!=2)continue;
        int duplicate=0;
        for(size_t n=0;n<count;++n)
            if(strcmp(games[n].id,id)==0){duplicate=1;break;}
        if(duplicate)continue;
        NiakGame *out=&games[count++];
        memset(out,0,sizeof(*out));
        memcpy(out->id,id,10);
        memcpy(out->title,name,(size_t)(second-name));
        out->application_category=(unsigned char)type;
        out->discovered_from_homebrew=3; /* last-known FTP snapshot */
    }
    const int failed=ferror(input);
    fclose(input);
    return failed?-1:(int)count;
}
#endif
