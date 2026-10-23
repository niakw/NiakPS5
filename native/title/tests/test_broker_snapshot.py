#!/usr/bin/env python3
"""Host contract: PLDmgr snapshot works without TCP, rejects stale/symlinks."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=r'''
#define _POSIX_C_SOURCE 200809L
#include "niak/broker_snapshot.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
int main(int argc,char **argv) {
  assert(argc==2);
  const char *path=argv[1];
  NiakGame games[4]; memset(games,0,sizeof(games));
  const long long now=(long long)time(NULL);
  assert(niak_snapshot_write(path,"PPSA12345\nCUSA54321\n",2,now)==0);
  assert(niak_snapshot_read(path,games,4)==2);
  assert(strcmp(games[0].id,"PPSA12345")==0);
  assert(strcmp(games[1].id,"CUSA54321")==0);
  assert(niak_snapshot_read(path,games,1)==1);
  /* A crashed older writer may have left its PID-named temp behind. */
  char old_temp[512];
  snprintf(old_temp,sizeof(old_temp),"%s.tmp.%ld",path,(long)getpid());
  FILE *orphan=fopen(old_temp,"wb");assert(orphan);
  fputs("stale",orphan);fclose(orphan);
  assert(niak_snapshot_write(path,"PPSA12345\n",1,now)==0);
  assert(niak_snapshot_read(path,games,1)==1);
  unlink(old_temp);
  /* Even a cap=1 reader must reject duplicates elsewhere in the file. */
  FILE *duplicate=fopen(path,"wb");assert(duplicate);
  fprintf(duplicate,"NIAKPS5-GAMES-1 %lld 2\nPPSA12345\nPPSA12345\nEND\n",now);
  fclose(duplicate);
  assert(niak_snapshot_read(path,games,1)==-1);
  FILE *suffix=fopen(path,"wb");assert(suffix);
  fprintf(suffix,"NIAKPS5-GAMES-1 %lld 1 EXTRA\nPPSA12345\nEND\n",now);
  fclose(suffix);
  assert(niak_snapshot_read(path,games,1)==-1);
  assert(niak_snapshot_write(path,"PPSA12345\n",1,now-2000)==0);
  assert(niak_snapshot_read(path,games,4)==-1);
  assert(niak_snapshot_write(path,"PPSA12345\n",1,now+2000)==0);
  assert(niak_snapshot_read(path,games,4)==-1);
  assert(niak_snapshot_write(path,"../../etc/passwd\n",1,now)==-1);
  assert(niak_snapshot_write(path,"PPSA12345\n",1,now)==0);
  FILE *out=fopen(path,"wb");assert(out);
  fputs("NIAKPS5-GAMES-1 12345 1\nINVALID999\nEND\n",out);fclose(out);
  assert(niak_snapshot_read(path,games,4)==-1);
  unlink(path);
  assert(symlink("/dev/null",path)==0);
  assert(niak_snapshot_read(path,games,4)==-1);
  return 0;
}
'''
class SnapshotTests(unittest.TestCase):
    def test_fresh_sandbox_file_catalogue_and_security(self):
        cc=shutil.which("cc")
        if not cc:self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"niak").mkdir()
            for p in ("broker_snapshot.h",):
                shutil.copyfile(ROOT/p,root/"niak"/p)
            shutil.copyfile(ROOT.parent/"catalog.h",root/"niak"/"catalog.h")
            (root/"test.c").write_text(SOURCE,encoding="utf-8")
            binary=root/"test"
            compiled=subprocess.run([cc,"-std=c11","-Wall","-Wextra","-Werror",
                                     "-I",str(root),str(root/"test.c"),
                                     "-o",str(binary)],capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            subprocess.run([str(binary),str(root/"snapshot.txt")],
                           check=True,capture_output=True,text=True)
if __name__=="__main__":
    unittest.main()
