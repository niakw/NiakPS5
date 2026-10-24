#!/usr/bin/env python3
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class BackMediaTests(unittest.TestCase):
 def test_unique_selection_host_cpp(self):
  compiler=shutil.which("c++") or shutil.which("clang++")
  if not compiler:self.skipTest("C++ compiler unavailable")
  with tempfile.TemporaryDirectory() as root:
   exe=Path(root)/"backmedia"
   subprocess.run([compiler,"-std=c++20","-Wall","-Wextra","-Werror",
                   str(ROOT/"tests/case_back_media_test.cpp"),"-o",str(exe)],
                   check=True,capture_output=True,text=True)
   subprocess.run([str(exe)],check=True)
 def test_never_repeat_hero_or_expose_plastic(self):
  s=(ROOT/"case_renderer.cpp").read_text()
  self.assertIn("niak_select_back_media({",s)
  self.assertIn("if(chosen.second.texture)",s)
  self.assertIn("Color::rgb(ps4?0x161a19:0xffffff)",s)
  self.assertNotIn("item.cover?item.cover:source",s)
  idx=(ROOT/"launchbox_index.py").read_text()
  self.assertIn("Screenshot - Gameplay",idx)
  self.assertIn("Fanart - Background",idx)
  prepare=(ROOT/"prepare.py").read_text()
  self.assertIn("case_hero",prepare)
  self.assertIn("case_shot1",prepare)
  self.assertIn("case_shot2",prepare)
  self.assertIn("case_back_media.hpp",prepare)
if __name__=="__main__":
 unittest.main()
