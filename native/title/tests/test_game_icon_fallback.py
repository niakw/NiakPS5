"""Regression contracts for bounded PS5 background decoding and fallback."""
from pathlib import Path
import unittest

SOURCE=(Path(__file__).resolve().parents[1]/"game_icons.cpp").read_text()

class InstalledBackgroundFallbackTests(unittest.TestCase):
    def test_scene_geometry_guard_precedes_decompression(self):
        self.assertIn("bool valid_scene_dimensions(unsigned width,unsigned height)",SOURCE)
        self.assertIn("if(landscape_scene && !valid_scene_dimensions(w,h))return false;",SOURCE)
        self.assertIn("if(landscape_scene && !valid_scene_dimensions(iw,ih))return false;",SOURCE)
        self.assertIn("if(!decode_installed_art(png,rgba,w,h,true))continue;",SOURCE)

    def test_failed_texture_upload_attempts_next_local_source(self):
        self.assertIn("if(!texture)continue;",SOURCE)
        self.assertIn("niak_track_case_texture(texture,target_w,target_h);",SOURCE)
        self.assertLess(SOURCE.index("if(!texture)continue;"),
                        SOURCE.index("niak_track_case_texture(texture,target_w,target_h);"))

if __name__=="__main__":
    unittest.main()
