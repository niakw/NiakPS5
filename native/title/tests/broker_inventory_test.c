#define _POSIX_C_SOURCE 200809L
#include "../broker_inventory.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(void) {
 char root[]="/tmp/niak-inventory-XXXXXX";
 assert(mkdtemp(root)!=NULL);
 char command[1000];
 snprintf(command,sizeof(command),
    "mkdir -p '%s/user/app/PPSA12345/sce_sys' '%s/data/homebrew/LAPY12345' '%s/user/app/NPXS99999' '%s/user/app/NPXS54321/sce_sys'",
    root,root,root,root);
 assert(system(command)==0);
 char path[680];
 snprintf(path,sizeof(path),"%s/user/app/PPSA12345/sce_sys/param.json",root);
 FILE *p=fopen(path,"wb");assert(p);fputs("{}",p);fclose(p);
 snprintf(path,sizeof(path),"%s/data/homebrew/LAPY12345/eboot.bin",root);
 p=fopen(path,"wb");assert(p);fputs("elf",p);fclose(p);
 snprintf(path,sizeof(path),"%s/user/app/NPXS54321/sce_sys/param.json",root);
 p=fopen(path,"wb");assert(p);
 fputs("{\"titleId\":\"NPXS54321\",\"applicationCategoryType\":65536}",p);
 fclose(p);
 char buffer[8192];
 assert(niak_broker_inventory(buffer,sizeof(buffer),root)==3);
 assert(strstr(buffer,"PPSA12345\n")!=NULL);
 assert(strstr(buffer,"LAPY12345\n")!=NULL);
 assert(strstr(buffer,"NPXS54321\n")!=NULL);
 assert(strstr(buffer,"NPXS99999")==NULL);
 char small[12];
 assert(niak_broker_inventory(small,sizeof(small),root)==1);
 snprintf(command,sizeof(command),"rm -rf -- '%s'",root);
 assert(system(command)==0);
 return 0;
}
