"""Prevent eager decoding and GPU allocation of fourteen WebP wallpapers."""
from pathlib import Path
import unittest

SOURCE=(Path(__file__).resolve().parents[1]/"daily_backdrop.cpp").read_text()

class WallpaperBudgetTests(unittest.TestCase):
    def test_at_most_one_packaged_gpu_texture(self):
        self.assertNotIn("std::array<std::uint32_t,14> images",SOURCE)
        self.assertIn("std::uint32_t packaged_texture=0;",SOURCE)
        self.assertIn("if(previous)runtime.renderer->destroy_texture(previous);",SOURCE)
        self.assertIn("packaged_failed.fill(false);",SOURCE)
        self.assertIn("packaged_paths.fill({});",SOURCE)

    def test_no_eager_decode_in_catalogue(self):
        catalog=SOURCE[SOURCE.index("void niak_load_daily_backdrops("):
                       SOURCE.index("std::uint32_t niak_daily_backdrop()")]
        self.assertIn("packaged_header_ok(path)",catalog)
        self.assertNotIn("load_packaged(path,pixels)",catalog)
        self.assertNotIn("renderer.create_texture(1280,720,pixels.data())",catalog)
        self.assertIn("return count?packaged_backdrop(",SOURCE)

    def test_live_wallpapers_expire_on_day_change(self):
        self.assertIn("if(s.texture && s.live_day!=day && s.renderer)",SOURCE)
        self.assertIn("s.renderer->destroy_texture(s.texture);",SOURCE)

if __name__=="__main__":
    unittest.main()
