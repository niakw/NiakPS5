#define _POSIX_C_SOURCE 200809L
#include "../title_permissions.h"
#include <assert.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <sys/stat.h>
static void file_at(const char *path,const char *body) {
    FILE *fp=fopen(path,"wb");
    assert(fp);
    assert(fwrite(body,1,strlen(body),fp)==strlen(body));
    assert(fclose(fp)==0);
}
int main(void) {
    char root[]="/tmp/niak-launch-perms-XXXXXX";
    assert(mkdtemp(root));
    char base[256],param[512],meta_dir[300];
    const char *roots[]={root};
    snprintf(base,sizeof(base),"%s/PPSA12345",root);
    assert(mkdir(base,0700)==0);
    assert(niak_title_is_launchable("PPSA12345","PPSA99386",roots,1));
    assert(!niak_title_is_launchable("PPSA99386","PPSA99386",roots,1));
    assert(!niak_title_is_launchable("NPXS00001","PPSA99386",roots,1));
    assert(!niak_title_is_launchable("PPSA1234/","PPSA99386",roots,1));
    assert(!niak_title_is_launchable("XXXX12345","PPSA99386",roots,1));
    assert(!niak_title_is_launchable(NULL,"PPSA99386",roots,1));
    assert(!niak_title_is_launchable("PPSA12345","PPSA99386",NULL,1));
    // Symlink to a real installed title must not be treated as an install.
    char shortcut[256];
    snprintf(shortcut,sizeof(shortcut),"%s/CUSA11111",root);
    assert(symlink(base,shortcut)==0);
    assert(!niak_title_is_launchable("CUSA11111","PPSA99386",roots,1));
    assert(unlink(shortcut)==0);
    // NPXS system services cannot launch unless verified by their OWN param.
    snprintf(base,sizeof(base),"%s/NPXS00001",root);
    assert(mkdir(base,0700)==0);
    snprintf(meta_dir,sizeof(meta_dir),"%s/sce_sys",base);
    assert(mkdir(meta_dir,0700)==0);
    snprintf(param,sizeof(param),"%s/param.json",meta_dir);
    file_at(param,"{\"applicationCategoryType\":0,\"titleName\":\"System\"}");
    assert(!niak_title_is_launchable("NPXS00001","PPSA99386",roots,1));
    file_at(param,"{\"other\":{\"applicationCategoryType\":65536},"
                  "\"applicationCategoryType\":0}");
    assert(!niak_title_is_launchable("NPXS00001","PPSA99386",roots,1));
    file_at(param,"{\"applicationCategoryType\":65536,\"titleName\":\"Media\"}");
    assert(niak_title_is_launchable("NPXS00001","PPSA99386",roots,1));
    file_at(param,"{\"titleId\":\"NPXS00002\",\"applicationCategoryType\":65536}");
    assert(!niak_title_is_launchable("NPXS00001","PPSA99386",roots,1));
    file_at(param,"{\"titleId\":\"NPXS00001\",\"applicationCategoryType\":65536}");
    assert(niak_title_is_launchable("NPXS00001","PPSA99386",roots,1));
    file_at(param,"{\"applicationCategoryType\":\"65792\","
                  "\"localizedParameters\":{\"en-US\":{\"titleName\":\"Video\"}}}");
    assert(niak_title_is_launchable("NPXS00001","PPSA99386",roots,1));
    // 64 KiB remains a hard input bound even if valid metadata is at the start.
    char huge[65600];
    memset(huge,' ',sizeof(huge));
    huge[0]='{';huge[1]='"';huge[2]='a';huge[sizeof(huge)-1]='}';
    FILE *fp=fopen(param,"wb");assert(fp);
    assert(fwrite(huge,1,sizeof(huge),fp)==sizeof(huge));
    assert(fclose(fp)==0);
    assert(!niak_title_is_launchable("NPXS00001","PPSA99386",roots,1));
    assert(unlink(param)==0);
    assert(rmdir(meta_dir)==0);
    assert(rmdir(base)==0);
    snprintf(base,sizeof(base),"%s/PPSA12345",root);
    assert(rmdir(base)==0);
    assert(rmdir(root)==0);
    return 0;
}
