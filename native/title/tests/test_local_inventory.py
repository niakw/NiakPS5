#!/usr/bin/env python3
"""Cached FTP title manifest parser; no Sony DB access or writes."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=r"""
#include "niak/local_inventory.h"
#include <assert.h>
#include <string.h>
int main(int argc,char **argv) {
    assert(argc==2);
    NiakGame games[8]={0};
    assert(niak_scan_local_inventory(argv[1],games,8)==3);
    assert(strcmp(games[0].id,"PPSA12345")==0);
    assert(strcmp(games[0].title,"Mon Jeu")==0);
    assert(games[0].application_category==1);
    assert(games[0].discovered_from_homebrew==3);
    assert(strcmp(games[1].id,"CUSA99999")==0);
    assert(strcmp(games[2].id,"NPXS12345")==0);
    assert(games[2].application_category==2);
    assert(niak_scan_local_inventory("/not-found/manifest.tsv",games,8)==-1);
    return 0;
}
"""

class LocalInventoryTests(unittest.TestCase):
    def test_rejects_invalid_and_builtin_titles(self):
        compiler=shutil.which("cc")
        if not compiler:
            self.skipTest("host C compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"niak").mkdir()
            shutil.copyfile(ROOT/"local_inventory.h",root/"niak/local_inventory.h")
            shutil.copyfile(ROOT.parent/"catalog.h",root/"niak/catalog.h")
            (root/"main.c").write_text(SOURCE)
            inventory=root/"titles.tsv"
            inventory.write_text(
                "PPSA12345\\tMon Jeu\\tJeu\\t\\t\\n"
                "CUSA99999\\tJeu PS4\\tJeu\\t\\t\\n"
                "NPXS98765\\tService système\\tJeu\\t\\t\\n"
                "NPXS12345\\tApplication média\\tApplication\\t\\t\\n"
                "PPSA99386\\tNiakPS5\\tApplication\\t\\t\\n"
                "PPSA12345\\tDoublon\\tJeu\\t\\t\\n"
                "BADID\\tInvalide\\tJeu\\t\\t\\n",
                encoding="utf-8")
            binary=root/"test"
            subprocess.run([compiler,"-std=c11","-Wall","-Wextra","-Werror",
                            "-I",str(root),str(root/"main.c"),"-o",str(binary)],
                           check=True,capture_output=True,text=True,timeout=20)
            subprocess.run([str(binary),str(inventory)],
                           check=True,capture_output=True,text=True,timeout=10)

if __name__=="__main__":
    unittest.main()
