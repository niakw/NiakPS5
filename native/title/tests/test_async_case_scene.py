"""PS5 case backgrounds decode without filesystem or WebP work on GL thread."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/"game_icons.cpp").read_text()
PATCH=(ROOT/"prepare.py").read_text()
HEADER=(ROOT/"game_icons.hpp").read_text()

class AsyncCaseSceneTests(unittest.TestCase):
    def test_only_one_bounded_case_scene_worker(self):
        block=SOURCE[SOURCE.index("struct AsyncCaseBackground {"):
                     SOURCE.index("std::uint32_t niak_load_game_icon(")]
        self.assertIn("state.wake.wait(",block)
        self.assertIn("!state.completed && !state.queue.empty()",block)
        self.assertIn("state.queued.size()>=256",block)
        self.assertIn("std::thread([] {case_background_worker();}).detach();",block)
        self.assertIn("decode_installed_art(image,rgba,width,height,true)",block)
        self.assertIn("state.completed_pixels=std::move(pixels);",block)
        self.assertNotIn("renderer.",block)

    def test_ps5_scene_request_does_not_block_rendering(self):
        body=SOURCE[SOURCE.index("std::uint32_t niak_load_game_background("):
                    SOURCE.index("std::uint32_t niak_take_downloaded_game_background(")]
        ps5=body[body.index("#if defined(__PROSPERO__)"):body.index("#else")]
        self.assertIn("enqueue_missing_scene(id);",ps5)
        self.assertNotIn("read_local_png",ps5)
        self.assertNotIn("decode_installed_art",ps5)
        self.assertIn("return 0;",ps5)

    def test_gpu_texture_remains_on_renderer_thread(self):
        poll=SOURCE[SOURCE.index("std::uint32_t niak_take_downloaded_game_background("):
                    SOURCE.index("std::uint32_t niak_load_profile_cache_png(")]
        self.assertIn("renderer.create_texture(int(width),int(height),pixels.data())",poll)
        self.assertIn("niak_track_case_texture(texture,width,height)",poll)
        self.assertIn("state.queued.erase(id);",poll)
        self.assertIn("niak_take_downloaded_game_background",HEADER)
        self.assertIn("bool Catalog::refresh_pending_case_background(",PATCH)
        self.assertIn("catalog.refresh_pending_case_background(renderer);",PATCH)
        self.assertIn("niak_destroy_case_texture(renderer,texture);",PATCH)
        self.assertIn("item.case_scene_aspect=aspect;",PATCH)
        # Host preview must retain its fallback to the next valid local file.
        self.assertIn("if(!texture)continue;",SOURCE)

if __name__=="__main__":
    unittest.main()
