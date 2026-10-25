/* SPDX-License-Identifier: GPL-3.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include "catalog.h"
#include "title/localized_name.h"
#include <sqlite3.h>
#include <dirent.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
static void copy_text(char *dst, size_t cap, const char *src) {
  if (!cap) return;
  if (!src) src="";
  snprintf(dst,cap,"%s",src);
}
int niak_valid_title_id(const char *id) {
  if (!id || strlen(id)!=9) return 0;
  if (strncmp(id,"CUSA",4)!=0 && strncmp(id,"PPSA",4)!=0 &&
      strncmp(id,"LAPY",4)!=0 && strncmp(id,"FAKE",4)!=0) return 0;
  /* Disallow arbitrarily long identifiers and path separators. */
  for (int i=4;i<9;i++) if (id[i]<'0' || id[i]>'9') return 0;
  return id[9]=='\0';
}

/* NPXS can refer to Sony built-ins: only explicit media categories qualify. */
static int valid_media_id(const char *id) {
 if(!id||strlen(id)!=9||strncmp(id,"NPXS",4)!=0)return 0;
 for(int i=4;i<9;i++)if(id[i]<'0'||id[i]>'9')return 0;
 return 1;
}
/* Installed title category is a unique TOP-LEVEL manifest field.
 * A substring in a description or nested localizedParameters must never
 * promote a game into an application (or authorize a system NPXS title). */
static int category_of(const char *text,const char *title_id) {
 return niak_installed_category_for_title(text,title_id);
}
static int category_from_param(const char *root,const char *id) {
 static const char *paths[]={"/user/app/","/system_ex/app/",
      "/data/homebrew/","/mnt/ext0/user/app/","/mnt/ext1/user/app/",
      "/user/appmeta/"};
 char file[768],content[32769];
 for(size_t i=0;i<sizeof(paths)/sizeof(paths[0]);++i) {
  int n= i==5 ?
      snprintf(file,sizeof(file),"%s%s%s/param.json",root,paths[i],id) :
      snprintf(file,sizeof(file),"%s%s%s/sce_sys/param.json",root,paths[i],id);
  if(n<=0||n>=(int)sizeof(file))continue;
  FILE *fp=fopen(file,"rb");if(!fp)continue;
  size_t size=fread(content,1,sizeof(content)-1,fp);
  int eof=feof(fp);fclose(fp);
  if(!eof || size<15)continue;
  content[size]=0;
  int category=category_of(content,id);
  if(category)return category;
 }
 return 0;
}
static void read_json_value(const char *source,const char *key,char *out,size_t cap) {
 if(!source||!key||!cap)return;
 char quoted[90];snprintf(quoted,sizeof(quoted),"\"%s\"",key);
 const char *p=strstr(source,quoted);
 if(!p || !(p=strchr(p+strlen(quoted),':')))return;
 ++p;while(*p==' '||*p=='\t')++p;
 size_t n=0;
 if(*p=='"') {
  ++p;
  while(*p && *p!='"' && n+1<cap) {
   if(*p=='\\')return;
   out[n++]=*p++;
  }
 }else{
  while((*p>='0'&&*p<='9') && n+1<cap)out[n++]=*p++;
 }
 out[n]=0;
}
static int installed(const char *root,const char *id) {
  static const char *prefixes[]={"/user/app/","/system_ex/app/","/mnt/ext0/user/app/","/mnt/ext1/user/app/","/data/homebrew/"};
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
    if((!niak_valid_title_id(id)&&!valid_media_id(id))||
       !installed(root,id)||find_index(games,*count,id)>=0)continue;
    const int columns=sqlite3_column_count(st);
    const char *details=columns>4?(const char*)sqlite3_column_text(st,4):NULL;
    int category=category_from_param(root,id);
    if(!category)category=category_of(details,id);
    if(valid_media_id(id) && category!=2)continue;
    NiakGame *game=&games[(*count)++];
    memset(game,0,sizeof(*game));
    copy_text(game->id,sizeof(game->id),id);
    copy_text(game->title,sizeof(game->title),(name&&name[0])?name:id);
    game->application_category=(unsigned char)category;
    if(columns>3) {
      copy_text(game->last_access,sizeof(game->last_access),
                (const char*)sqlite3_column_text(st,2));
      copy_text(game->installed_at,sizeof(game->installed_at),
                (const char*)sqlite3_column_text(st,3));
    }
    read_json_value(details,"#_last_access_time",
                    game->last_access,sizeof(game->last_access));
    read_json_value(details,"#_install_time",
                    game->installed_at,sizeof(game->installed_at));
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
    "SELECT titleId,titleName,lastAccessTime,installTime,AppInfoJson FROM tbl_contentinfo "
    "WHERE titleId LIKE 'CUSA%' OR titleId LIKE 'PPSA%' OR titleId LIKE 'NPXS%' "
    "ORDER BY lastAccessTime DESC,installTime DESC",
    "SELECT titleId,titleName FROM tbl_appbrowse WHERE titleId LIKE 'CUSA%' OR titleId LIKE 'PPSA%' OR titleId LIKE 'NPXS%' ORDER BY titleName COLLATE NOCASE",
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

/* Independently discover installed-looking homebrew title folders on /data.
 * Metadata-only: no package executes, no sqlite writes, no firmware changes.
 * Presence does NOT establish ShadowMount registration or launch permission.
 */
static int is_plain_file(const char *path) {
  struct stat st;
  return lstat(path,&st)==0 && S_ISREG(st.st_mode);
}
static int is_plain_dir(const char *path) {
  struct stat st;
  return lstat(path,&st)==0 && S_ISDIR(st.st_mode);
}
static int compare_games(const void *left,const void *right) {
  const NiakGame *a=(const NiakGame*)left;
  const NiakGame *b=(const NiakGame*)right;
  return strcmp(a->id,b->id);
}
int niak_scan_homebrews(const char *filesystem_root,NiakGame *games,size_t capacity) {
  if(!filesystem_root||!games||!capacity)return -1;
  char base[768];
  int n=snprintf(base,sizeof(base),"%s/data/homebrew",filesystem_root);
  if(n<=0||n>=(int)sizeof(base)||!is_plain_dir(base))return -1;
  DIR *dir=opendir(base);
  if(!dir)return -1;
  size_t count=0;
  const struct dirent *entry;
  while((entry=readdir(dir))!=NULL && count<capacity) {
    const char *id=entry->d_name;
    if(!niak_valid_title_id(id))continue;
    char folder[832],eboot[896],param[896],icon[896];
    n=snprintf(folder,sizeof(folder),"%s/%s",base,id);
    if(n<=0||n>=(int)sizeof(folder)||!is_plain_dir(folder))continue;
    n=snprintf(eboot,sizeof(eboot),"%s/eboot.bin",folder);
    if(n<=0||n>=(int)sizeof(eboot)||!is_plain_file(eboot))continue;
    n=snprintf(param,sizeof(param),"%s/sce_sys/param.json",folder);
    if(n<=0||n>=(int)sizeof(param)||!is_plain_file(param))continue;
    NiakGame *game=&games[count++];
    memset(game,0,sizeof(*game));
    copy_text(game->id,sizeof(game->id),id);
    // Installed manifest names are facts, not evidence of registration.
    copy_text(game->title,sizeof(game->title),id);
    FILE *name_file=fopen(param,"rb");
    if(name_file) {
      char json[32769]={0};
      const size_t size=fread(json,1,sizeof(json)-1,name_file);
      const int complete=feof(name_file);fclose(name_file);
      if(complete && size>10 && size<sizeof(json)) {
        const char *native_name=niak_json_direct(json,"titleName");
        (void)niak_json_title_value(native_name,game->title,sizeof(game->title));
        (void)niak_manifest_localized_title(json,game->title,sizeof(game->title));
      }
    }
    game->discovered_from_homebrew=1;
    game->is_homebrew=1;
    game->application_category=(unsigned char)category_from_param(filesystem_root,id);
    n=snprintf(icon,sizeof(icon),"%s/sce_sys/icon0.png",folder);
    if(n>0&&n<(int)sizeof(icon)&&is_plain_file(icon))
      copy_text(game->icon,sizeof(game->icon),icon);
  }
  closedir(dir);
  qsort(games,count,sizeof(*games),compare_games);
  return (int)count;
}


/* Read-only fallback for user-installed native games AND multimedia apps.
 * Never promote built-in shell NPXS services without an explicit media type.
 */
int niak_scan_installed_folders(const char *root,NiakGame *games,size_t capacity) {
 if(!root||!games||capacity==0)return -1;
 const char *dirs[]={"/user/app","/system_ex/app",
                      "/mnt/ext0/user/app","/mnt/ext1/user/app"};
 size_t count=0;int visible=0;
 for(size_t r=0;r<sizeof(dirs)/sizeof(dirs[0]);++r) {
  char base[640];int n=snprintf(base,sizeof(base),"%s%s",root,dirs[r]);
  if(n<=0||n>=(int)sizeof(base))continue;
  DIR *dir=opendir(base);if(!dir)continue;
  visible=1;
  struct dirent *entry;
  while((entry=readdir(dir))!=NULL && count<capacity) {
   const char *id=entry->d_name;
   if((!niak_valid_title_id(id) && !valid_media_id(id)) ||
       find_index(games,count,id)>=0)continue;
   char folder[768],manifest[850],pkg[850],eboot[850];
   n=snprintf(folder,sizeof(folder),"%s/%s",base,id);
   if(n<=0||n>=(int)sizeof(folder)||!is_plain_dir(folder))continue;
   snprintf(manifest,sizeof(manifest),"%s/sce_sys/param.json",folder);
   snprintf(pkg,sizeof(pkg),"%s/app.pkg",folder);
   snprintf(eboot,sizeof(eboot),"%s/eboot.bin",folder);
   if(!is_plain_file(manifest) && !is_plain_file(pkg) &&
      !is_plain_file(eboot))continue;
   const int category=category_from_param(root,id);
   if(valid_media_id(id) && category!=2)continue;
   NiakGame *game=&games[count++];
   memset(game,0,sizeof(*game));
   copy_text(game->id,sizeof(game->id),id);
   copy_text(game->title,sizeof(game->title),id);
   game->application_category=(unsigned char)category;
   struct stat st;
   if(stat(folder,&st)==0) {
    struct tm *local=localtime(&st.st_mtime);
    if(local)strftime(game->installed_at,sizeof(game->installed_at),
                      "%Y-%m-%dT%H:%M:%S",local);
   }
   FILE *f=fopen(manifest,"rb");
   if(f) {
    char content[32769]={0};
    size_t len=fread(content,1,sizeof(content)-1,f);
    fclose(f);
    if(len>10 && len<sizeof(content)-1) {
      const char *native_name=niak_json_direct(content,"titleName");
      (void)niak_json_title_value(native_name,game->title,sizeof(game->title));
      (void)niak_manifest_localized_title(content,game->title,sizeof(game->title));
    }
   }
   artwork(root,id,"icon0.png",game->icon,sizeof(game->icon));
   artwork(root,id,"pic1.png",game->background,sizeof(game->background));
  }
  closedir(dir);
 }
 qsort(games,count,sizeof(*games),compare_games);
 return visible?(int)count:-1;
}
