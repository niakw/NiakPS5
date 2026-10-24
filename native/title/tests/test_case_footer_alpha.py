#!/usr/bin/env python3
"""Fixed lower-back graphics stay visible but never add an opaque card."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class FooterTests(unittest.TestCase):
    def test_alpha_extraction(self):
        cxx=shutil.which("g++") or shutil.which("clang++")
        if not cxx:self.skipTest("C++ compiler not installed")
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"footer"
            subprocess.run([cxx,"-std=c++20","-Wall","-Wextra","-Werror",
                str(ROOT/"tests/case_footer_alpha_test.cpp"),"-o",str(target)],
                check=True,capture_output=True,text=True)
            subprocess.run([str(target)],check=True,capture_output=True,text=True)
if __name__=="__main__":unittest.main()
