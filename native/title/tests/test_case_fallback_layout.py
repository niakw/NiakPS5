#!/usr/bin/env python3
"""Compile fixed PS4/PS5 fallback geometries independently of SDK."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class CaseFallbackTests(unittest.TestCase):
    def test_geometry_and_unstretched_full_bleed(self):
        cc=shutil.which("c++") or shutil.which("clang++")
        if not cc:self.skipTest("No host C++ compiler")
        with tempfile.TemporaryDirectory() as td:
            binary=Path(td)/"fallback"
            subprocess.run([cc,"-std=c++20","-O1","-Wall","-Wextra","-Werror",
                            "-I",str(ROOT),str(ROOT/"tests/case_fallback_layout_test.cpp"),
                            "-o",str(binary)],check=True,capture_output=True,text=True)
            subprocess.run([str(binary)],check=True,capture_output=True,text=True)

    def test_official_faces_override_independently(self):
        source=(ROOT/"case_renderer.cpp").read_text()
        staged=(ROOT/"prepare.py").read_text()
        assert "if(texture) {" in source
        assert "printed(list,texture,paper" in source
        assert "if(!item.case_front) {" in staged
        assert "if(!item.case_back)" in staged
        assert "if(!item.case_spine)" in staged
        assert 'item.case_template_front=niak_load_case_template' in staged
        assert 'item.case_template_back=niak_load_case_template' in staged
        assert "niak_case_cover_crop(" in source
        assert "item.logo_art" in source
        assert "layout.front_header" in source
        assert "layout.back_footer" in source
        assert "item.case_scene_aspect" in source
        assert "item.logo_art_aspect" in source
        assert "if(!back)" in source
        assert "if(item.case_template_back)" in source
        assert "if(item.case_template_front)" in source
        assert "0.18f+v*0.59f" not in source
        assert "block(0,0.90f,1,1" not in source

if __name__=="__main__":
    unittest.main()
