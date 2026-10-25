"""Reject stale and redundant asynchronous media before GPU upload."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
CPP=(ROOT/"game_icons.cpp").read_text()
STAGE=(ROOT/"prepare.py").read_text()
HEADER=(ROOT/"game_icons.hpp").read_text()
class MediaAdmissionTests(unittest.TestCase):
    def test_icon_validated_before_gpu_allocation(self):
        section=CPP[CPP.index("std::uint32_t niak_take_downloaded_game_icon("):
                    CPP.index("std::uint32_t niak_load_game_background(")]
        self.assertLess(section.index("if(accept && !accept(title_id,opaque))return 0;"),
                        section.index("renderer.create_texture("))
        self.assertLess(section.index("state.seen.erase(id);"),
                        section.index("if(accept && !accept(title_id,opaque))return 0;"))
        self.assertIn("catalog.items_.begin()",STAGE)
        self.assertIn("!match->cover_is_image",STAGE)
        self.assertIn("renderer,id,accept,this",STAGE)
        self.assertIn("bool (*accept)(const char *,void *)=nullptr",HEADER)
    def test_scene_validated_before_gpu_allocation(self):
        section=CPP[CPP.index("std::uint32_t niak_take_downloaded_game_background("):
                    CPP.index("std::uint32_t niak_load_profile_cache_png(")]
        self.assertLess(section.index("if(!expected_id || id!=expected_id)return 0;"),
                        section.index("renderer.create_texture("))
        self.assertLess(section.index("state.queued.erase(id);"),
                        section.index("if(!expected_id || id!=expected_id)return 0;"))
        self.assertIn("!selected->case_front && !selected->case_scene",STAGE)
        self.assertIn("renderer,title_id,&aspect,expected",STAGE)
        self.assertIn("const char *expected_id=nullptr",HEADER)
if __name__=="__main__":
    unittest.main()
