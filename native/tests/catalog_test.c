/* SPDX-License-Identifier: GPL-3.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include "../catalog.h"
#include <sqlite3.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
static void make_dir(const char *path){if(mkdir(path,0700))perror(path);}
int main(void){
  assert(niak_valid_title_id("PPSA12345"));
  assert(niak_valid_title_id("CUSA98765"));
  assert(!niak_valid_title_id("NPXS40000"));
  assert(!niak_valid_title_id("PPSA12345/../"));
  assert(!niak_valid_title_id("PPSA1234"));
  char root[]="/tmp/niakps5-test-XXXXXX";
  assert(mkdtemp(root)!=NULL);
  char path[512];
  snprintf(path,sizeof(path),"%s/user",root);make_dir(path);
  snprintf(path,sizeof(path),"%s/user/app",root);make_dir(path);
  snprintf(path,sizeof(path),"%s/user/app/PPSA12345",root);make_dir(path);
  snprintf(path,sizeof(path),"%s/user/appmeta",root);make_dir(path);
  snprintf(path,sizeof(path),"%s/user/appmeta/PPSA12345",root);make_dir(path);
  snprintf(path,sizeof(path),"%s/user/appmeta/PPSA12345/icon0.png",root);
  FILE *icon=fopen(path,"wb");assert(icon);fputs("fixture",icon);fclose(icon);
  char database[512];snprintf(database,sizeof(database),"%s/app.db",root);
  sqlite3 *db=NULL;assert(sqlite3_open(database,&db)==SQLITE_OK);
  assert(sqlite3_exec(db,"CREATE TABLE tbl_appbrowse(titleId TEXT,titleName TEXT);"
      "INSERT INTO tbl_appbrowse VALUES('PPSA12345','Titre installé');"
      "INSERT INTO tbl_appbrowse VALUES('CUSA54321','Titre désinstallé');"
      "INSERT INTO tbl_appbrowse VALUES('NPXS40000','Shell système');"
      "INSERT INTO tbl_appbrowse VALUES('PPSA99999/../','Chemin malicieux');",
      NULL,NULL,NULL)==SQLITE_OK);
  sqlite3_close(db);
  NiakGame games[5]={0};
  int count=niak_scan_games(database,root,games,5);
  assert(count==1);
  assert(strcmp(games[0].id,"PPSA12345")==0);
  assert(strcmp(games[0].title,"Titre installé")==0);
  assert(strstr(games[0].icon,"icon0.png")!=NULL);
  assert(niak_scan_games("/file/that/does/not/exist",root,games,5)==-1);
  /* Verify that the read-only scanner did not modify the record. */
  assert(sqlite3_open_v2(database,&db,SQLITE_OPEN_READONLY,NULL)==SQLITE_OK);
  sqlite3_stmt *st=NULL;
  assert(sqlite3_prepare_v2(db,"SELECT count(*) FROM tbl_appbrowse",-1,&st,NULL)==SQLITE_OK);
  assert(sqlite3_step(st)==SQLITE_ROW&&sqlite3_column_int(st,0)==4);
  sqlite3_finalize(st);sqlite3_close(db);
  snprintf(path,sizeof(path),"%s/user/appmeta/PPSA12345/icon0.png",root);unlink(path);
  snprintf(path,sizeof(path),"%s/user/appmeta/PPSA12345",root);rmdir(path);
  snprintf(path,sizeof(path),"%s/user/appmeta",root);rmdir(path);
  snprintf(path,sizeof(path),"%s/user/app/PPSA12345",root);rmdir(path);
  snprintf(path,sizeof(path),"%s/user/app",root);rmdir(path);
  snprintf(path,sizeof(path),"%s/user",root);rmdir(path);
  unlink(database);rmdir(root);
  puts("NiakPS5 native catalog: OK");
  return 0;
}
