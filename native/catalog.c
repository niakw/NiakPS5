/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "catalog.h"
#include <sqlite3.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
static void copy_text(char *dst, size_t cap, const char *src) {
  if (!cap) return;
  if (!src) src="";
  snprintf(dst,cap,"%s",src);
}
int niak_valid_title_id(const char *id) {
  if (!id) return 0;
  if (strncmp(id,"CUSA",4)!=0 && strncmp(id,"PPSA",4)!=0) return 0;
  /* Disallow arbitrarily long identifiers and path separators. */
  for (int i=4;i<9;i++) if (id[i]<'0' || id[i]>'9') return 0;
  return id[9]=='\0';
}
static int installed(const char *root,const char *id) {
  static const char *prefixes[]={"/user/app/","/system_ex/app/","/mnt/ext0/user/app/","/mnt/ext1/user/app/"};
  char path[768];
  struct stat st;
  for(size_t i=0;i<sizeof(prefixes)/sizeof(prefixes[0]);i++){
    int n=snprintf(path,sizeof(path),"%s%s%s",root,prefixes[i],id);
    if(n>0 && n<(int)sizeof(path) && stat(path,&st)==0 && S_ISDIR(st.st_mode))return 1;
  }
  return 0;
}
static void artwork(const char *root, const char *id, const char *name, char *dst, size_t size){
  char path[768];
  struct stat st;
  int n=snprintf(path,sizeof(path),"%s/user/appmeta/%s/%s",root,id,name);
  if(n>0 && n<(int)sizeof(path) && stat(path,&st)==0 && S_ISREG(st.st_mode))copy_text(dst,size,path);
}
static int find_index(NiakGame *games,size_t count,const char *id) {
  for(size_t i=0;i<count;i++)if(strcmp(games[i].id,id)==0)return (int)i;
  return -1;
}
static int gather(sqlite3 *db,const char *sql,const char *root,NiakGame *games,size_t *count,size_t capacity){
  sqlite3_stmt *st=NULL;
  if(sqlite3_prepare_v2(db,sql,-1,&st,NULL)!=SQLITE_OK) return -1;
  while(sqlite3_step(st)==SQLITE_ROW && *count<capacity){
    const char *id=(const char*)sqlite3_column_text(st,0);
    const char *name=(const char*)sqlite3_column_text(st,1);
    if(!niak_valid_title_id(id)||!installed(root,id)||find_index(games,*count,id)>=0)continue;
    NiakGame *game=&games[(*count)++];
    memset(game,0,sizeof(*game));
    copy_text(game->id,sizeof(game->id),id);
    copy_text(game->title,sizeof(game->title),(name&&name[0])?name:id);
    artwork(root,id,"icon0.png",game->icon,sizeof(game->icon));
    artwork(root,id,"pic1.png",game->background,sizeof(game->background));
    if(!game->background[0])artwork(root,id,"pic0.png",game->background,sizeof(game->background));
  }
  sqlite3_finalize(st);
  return 0;
}
int niak_scan_games(const char *database_path,const char *filesystem_root,NiakGame *games,size_t capacity) {
  if(!database_path||!filesystem_root||!games||!capacity)return -1;
  sqlite3 *db=NULL;
  if(sqlite3_open_v2(database_path,&db,SQLITE_OPEN_READONLY|SQLITE_OPEN_NOMUTEX,NULL)!=SQLITE_OK){
    if(db)sqlite3_close(db);
    return -1;
  }
  sqlite3_busy_timeout(db,150);
  size_t count=0;
  /* PS5 databases vary between firmware revisions. These are best-effort queries. */
  const char *queries[]={
    "SELECT titleId,titleName FROM tbl_appbrowse WHERE titleId LIKE 'CUSA%' OR titleId LIKE 'PPSA%' ORDER BY titleName COLLATE NOCASE",
    "SELECT titleId, MAX(CASE WHEN key='TITLE_01' THEN val END) FROM tbl_appinfo WHERE titleId LIKE 'CUSA%' OR titleId LIKE 'PPSA%' GROUP BY titleId",
    "SELECT titleId, titleId FROM tbl_contentinfo WHERE titleId LIKE 'CUSA%' OR titleId LIKE 'PPSA%'"
  };
  int any_success=0;
  for(size_t i=0;i<sizeof(queries)/sizeof(queries[0]);i++){
    int rc=gather(db,queries[i],filesystem_root,games,&count,capacity);
    if(rc==0)any_success=1;
    if(count==capacity)break;
  }
  sqlite3_close(db);
  return any_success ? (int)count : -1;
}
