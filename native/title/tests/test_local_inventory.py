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
                "PPSA12345\tMon Jeu\tJeu\t\t\n"
                "CUSA99999\tJeu PS4\tJeu\t\t\n"
                "NPXS98765\tService système\tJeu\t\t\n"
                "NPXS12345\tApplication média\tApplication\t\t\n"
                "PPSA99386\tNiakPS5\tApplication\t\t\n"
                "PPSA12345\tDoublon\tJeu\t\t\n"
                "BADID\tInvalide\tJeu\t\t\n",
                encoding="utf-8")
            binary=root/"test"
            subprocess.run([compiler,"-std=c11","-Wall","-Wextra","-Werror",
                            "-I",str(root),str(root/"main.c"),"-o",str(binary)],
                           check=True,capture_output=True,text=True,timeout=20)
            subprocess.run([str(binary),str(inventory)],
                           check=True,capture_output=True,text=True,timeout=10)


    def test_merge_private_overlay_over_packaged_by_exact_title_id(self):
        compiler=shutil.which("c++")
        if not compiler:
            self.skipTest("host C++ compiler unavailable")
        source=r"""
#include "niak/local_inventory_merge.hpp"
#include <cassert>
#include <cstring>
int main(int argc,char **argv) {
    assert(argc==4);
    NiakGame games[8]={};
    int packaged=-9,local=-9;
    int count=niak_merge_local_inventories(
        argv[1],argv[2],games,8,&packaged,&local);
    assert(packaged==2 && local==2 && count==3);
    assert(std::strcmp(games[0].id,"PPSA12345")==0);
    assert(std::strcmp(games[0].title,"Nom français")==0);
    assert(games[0].application_category==2);
    assert(std::strcmp(games[1].title,"Packaged Game")==0);
    assert(std::strcmp(games[2].id,"PPSA33333")==0);
    assert(games[2].application_category==2);
    // A missing immutable /app0 source must NOT hide the private overlay.
    count=niak_merge_local_inventories(
        argv[3],argv[2],games,8,&packaged,&local);
    assert(packaged==-1 && local==2 && count==2);
    assert(std::strcmp(games[0].title,"Nom français")==0);
    assert(std::strcmp(games[1].title,"Application ajoutée")==0);
    // An empty /app0 file must likewise keep the private titles visible.
    count=niak_merge_local_inventories(
        argv[3],argv[3],games,8,&packaged,&local);
    assert(packaged==-1 && local==-1 && count==0);
    assert(niak_merge_local_inventories(
        argv[1],argv[2],games,0)==-1);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"niak").mkdir()
            for filename in ("local_inventory.h","local_inventory_merge.hpp"):
                shutil.copyfile(ROOT/filename,root/"niak"/filename)
            shutil.copyfile(ROOT.parent/"catalog.h",root/"niak/catalog.h")
            (root/"main.cpp").write_text(source)
            packaged=root/"packaged.tsv"
            packaged.write_text(
                "PPSA12345\tEnglish Title\tJeu\t\t\n"
                "PPSA22222\tPackaged Game\tJeu\t\t\n",
                encoding="utf8")
            local=root/"private.tsv"
            local.write_text(
                "PPSA12345\tNom français\tApplication\t\t\n"
                "PPSA33333\tApplication ajoutée\tApplication\t\t\n",
                encoding="utf8")
            executable=root/"merge-test"
            subprocess.run([compiler,"-std=c++20","-Wall","-Wextra","-Werror",
                            "-I",str(root),str(root/"main.cpp"),"-o",str(executable)],
                           check=True,capture_output=True,text=True,timeout=20)
            subprocess.run([str(executable),str(packaged),str(local),str(root/"missing.tsv")],
                           check=True,capture_output=True,text=True,timeout=10)

if __name__=="__main__":
    unittest.main()
