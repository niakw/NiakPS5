/* SPDX-License-Identifier: GPL-3.0-or-later
 * One-way, read-only installed-ID inventory from opt-in PLDmgr broker.
 * PS5 titles may be forbidden to use fcntl or TCP by their sandbox.
 * No user-provided paths or commands, no privilege transfer.
 */
#ifndef NIAK_BROKER_SNAPSHOT_H
#define NIAK_BROKER_SNAPSHOT_H
#include "catalog.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

/* The payload can update the native title's own existing assets folder.
 * The sandboxed UI reads the same bytes via its mounted /app0 path.
 * Keep /data as a backward-compatible fallback on older installations.
 */
#define NIAK_SNAPSHOT_FILE "/data/niakps5-games.snapshot"
#define NIAK_SNAPSHOT_APP_SOURCE "/data/homebrew/PPSA99386/assets/niakps5-games.snapshot"
#define NIAK_SNAPSHOT_APP_FILE "/app0/assets/niakps5-games.snapshot"
#define NIAK_SNAPSHOT_MAX_AGE 600LL
#define NIAK_SNAPSHOT_MAX_GAMES 512
#define NIAK_SNAPSHOT_VERSION "NIAKPS5-GAMES-1"

static inline int niak_snapshot_valid_id(const char *id) {
    if(!id || strlen(id)!=9 ||
       (strncmp(id,"PPSA",4)&&strncmp(id,"CUSA",4)&&
        strncmp(id,"LAPY",4)&&strncmp(id,"FAKE",4)&&
        strncmp(id,"NPXS",4)))return 0;
    for(int i=4;i<9;i++)if(id[i]<'0'||id[i]>'9')return 0;
    return strcmp(id,"PPSA99386")!=0;
}

/* Only the PLDmgr payload calls this on its FIXED private snapshot file.
 * Caller provides the read-only fixed-root inventory, not a client request.
 * Atomic replace prevents the title seeing a half-written inventory.
 */
static inline int niak_snapshot_write(const char *path,const char *ids,
                                      int count,long long epoch) {
    if(!path || !ids || count<0 || count>NIAK_SNAPSHOT_MAX_GAMES ||
       epoch<=0 || strlen(ids)>8192)return -1;
    char temp[256];
    const int name_len=snprintf(temp,sizeof(temp),"%s.XXXXXX",path);
    if(name_len<=0 || name_len>=(int)sizeof(temp))return -1;
    /* A crashed broker must never leave a predictable PID-named temp that
     * prevents all subsequent refreshes. mkstemp creates a unique O_EXCL file.
     */
    int fd=mkstemp(temp);
    if(fd<0)return -1;
    int ok=fchmod(fd,0644)==0;
    FILE *out=fdopen(fd,"wb");
    if(!out){close(fd);unlink(temp);return -1;}
    if(fprintf(out,NIAK_SNAPSHOT_VERSION " %lld %d\n",epoch,count)<0)ok=0;
    const char *p=ids;
    for(int i=0;ok && i<count;++i) {
        if(strlen(p)<10 || p[9]!='\n') {ok=0;break;}
        char name[10];memcpy(name,p,9);name[9]=0;
        if(!niak_snapshot_valid_id(name)) {ok=0;break;}
        if(fwrite(p,1,10,out)!=10)ok=0;
        p+=10;
    }
    if(ok && *p!=0)ok=0;
    if(ok && fputs("END\n",out)<0)ok=0;
    if(ok && fflush(out)!=0)ok=0;
    if(ok && fsync(fd)!=0)ok=0;
    if(fclose(out)!=0)ok=0;
    if(ok && rename(temp,path)==0)return 0;
    unlink(temp);
    return -1;
}

/* Read-only, strictly bounded. A copied old snapshot cannot masquerade as
 * a live broker; bad paths, duplicates, symlinks and stale data fail closed.
 * At most cap game IDs are returned; count may exceed cap.
 */
static inline int niak_snapshot_read(const char *path,NiakGame *games,
                                     size_t cap) {
    if(!path || !games || !cap || cap>NIAK_SNAPSHOT_MAX_GAMES)return -1;
    struct stat before;
    if(lstat(path,&before)!=0 || !S_ISREG(before.st_mode) ||
       before.st_size<20 || before.st_size>8192)return -1;
    /* O_NOFOLLOW also protects the open itself if a concurrent actor
     * replaces the file after lstat. Compare the resulting inode below.
     */
    const int fd=open(path,O_RDONLY|O_NOFOLLOW);
    if(fd<0)return -1;
    FILE *in=fdopen(fd,"rb");
    if(!in){close(fd);return -1;}
    struct stat after;
    if(fd<0 || fstat(fd,&after)!=0 || before.st_ino!=after.st_ino ||
       before.st_dev!=after.st_dev || !S_ISREG(after.st_mode)) {
        fclose(in);return -1;
    }
    char line[96];long long stamp=0;int count=-1;int result=-1;
    int header_bytes=0;
    if(!fgets(line,sizeof(line),in) ||
       sscanf(line,NIAK_SNAPSHOT_VERSION " %lld %d",&stamp,&count)!=2 ||
       count<0 || count>NIAK_SNAPSHOT_MAX_GAMES || stamp<=0)goto done;
    /* sscanf alone accepts extra trailing data. Require the writer's
     * exact canonical single-line header, including the final newline.
     */
    char expected_header[96];
    header_bytes=snprintf(expected_header,sizeof(expected_header),
        NIAK_SNAPSHOT_VERSION " %lld %d\n",stamp,count);
    if(header_bytes<=0 || header_bytes>=(int)sizeof(expected_header) ||
       strcmp(line,expected_header)!=0)goto done;
    {
        const time_t now=time(NULL);
        if(now<=0 || stamp>(long long)now+60 ||
           (long long)now-stamp>NIAK_SNAPSHOT_MAX_AGE)goto done;
    }
    /* Validate ALL IDs, not only the caller's cap: a small catalogue probe
     * must not accidentally accept duplicates beyond its output buffer.
     */
    char seen[NIAK_SNAPSHOT_MAX_GAMES][10];
    for(int i=0;i<count;++i) {
        if(!fgets(line,sizeof(line),in)||strlen(line)!=10 ||
           line[9]!='\n')goto done;
        line[9]=0;
        if(!niak_snapshot_valid_id(line))goto done;
        for(int k=0;k<i;++k)
            if(strcmp(seen[k],line)==0)goto done;
        memcpy(seen[i],line,10);
        if((size_t)i<cap) {
            memset(&games[i],0,sizeof(games[i]));
            memcpy(games[i].id,line,9);
            memcpy(games[i].title,line,9);
        }
    }
    if(!fgets(line,sizeof(line),in) || strcmp(line,"END\n")!=0 ||
       fgetc(in)!=EOF)goto done;
    result=count<(int)cap?count:(int)cap;
done:
    fclose(in);
    return result;
}
#endif
