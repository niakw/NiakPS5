"""Guard the native Aurora hero against duplicate 3D case renders."""
from pathlib import Path
import unittest

SOURCE=(Path(__file__).resolve().parents[1]/"polish.py").read_text()

class HeroCaseScopeTests(unittest.TestCase):
    def test_only_the_focused_game_receives_the_3d_mesh(self):
        self.assertIn("it.application || !it.title_id[0] || index != focused_item()", SOURCE)
        self.assertIn("niak_draw_rotating_case(list,it,art,", SOURCE)
        self.assertIn("it.cover_is_image ? gfx::kFullUv : gfx::kCanvasUv", SOURCE)
        self.assertIn("list.rounded_rect(art, 36, it.dark)", SOURCE)

    def test_removes_unconditional_mesh_substitution(self):
        self.assertNotIn("""'niak_draw_rotating_case(list,it,art,'
                 'context_.settings.reduced_motion""", SOURCE)

if __name__=="__main__":
    unittest.main()
