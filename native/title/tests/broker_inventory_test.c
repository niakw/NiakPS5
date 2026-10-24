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
 char app_ids[8192];
 assert(niak_broker_apps_from_inventory(buffer,app_ids,sizeof(app_ids),root)==1);
 assert(strcmp(app_ids,"NPXS54321\n")==0);
 // A native-game-category homebrew with a known application identity is
 // still an application, independent of PPSA/CUSA and install origin.
 snprintf(command,sizeof(command),
    "mkdir -p '%s/data/homebrew/PPSA12346/sce_sys'",root);
 assert(system(command)==0);
 snprintf(path,sizeof(path),"%s/data/homebrew/PPSA12346/sce_sys/param.json",root);
 p=fopen(path,"wb");assert(p);
 fputs("{\"titleId\":\"PPSA12346\",\"applicationCategoryType\":0,"
       "\"localizedParameters\":{\"en-US\":{\"titleName\":\"Eden Encore\"}}}",p);
 fclose(p);
 // A media app can have its verified param in appmeta, but it must still
 // have an actual installation in /user/app.
 snprintf(command,sizeof(command),
    "mkdir -p '%s/user/app/NPXS11111' '%s/user/appmeta/NPXS11111'",root,root);
 assert(system(command)==0);
 snprintf(path,sizeof(path),"%s/user/app/NPXS11111/eboot.bin",root);
 p=fopen(path,"wb");assert(p);fputs("elf",p);fclose(p);
 snprintf(path,sizeof(path),"%s/user/appmeta/NPXS11111/param.json",root);
 p=fopen(path,"wb");assert(p);
 fputs("{\"titleId\":\"NPXS11111\",\"applicationCategoryType\":65792}",p);
 fclose(p);
 assert(niak_broker_inventory(buffer,sizeof(buffer),root)==5);
 assert(niak_broker_apps_from_inventory(buffer,app_ids,sizeof(app_ids),root)==2);
 assert(strstr(app_ids,"PPSA12346\n")!=NULL);
 char small[12];
 assert(niak_broker_inventory(small,sizeof(small),root)==1);
 snprintf(command,sizeof(command),"rm -rf -- '%s'",root);
 assert(system(command)==0);
 return 0;
}
