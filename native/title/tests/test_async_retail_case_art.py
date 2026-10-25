"""PS5 LaunchBox retail scans decode off GL, with generation-safe updates."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/"case_art.cpp").read_text()
HEADER=(ROOT/"case_art.hpp").read_text()
STAGE=(ROOT/"prepare.py").read_text()

class AsyncRetailCaseArtTests(unittest.TestCase):
    def test_png_webp_and_scale_are_cpu_only(self):
        prepare=SOURCE[SOURCE.index("static bool niak_prepare_case_pixels("):
                       SOURCE.index("#if defined(__PROSPERO__)\n// Latest-selected-title worker.")]
        self.assertIn("WebPDecodeRGBAInto(png.data(),png.size(),pixels.data()",prepare)
        self.assertIn("lodepng::decode(pixels,w,h,png)",prepare)
        self.assertIn("niak_scale_case_rgba(pixels,w,h,",prepare)
        self.assertIn("valid_download_source(filename)",prepare)
        self.assertIn("/download0/niak-case-%s-%s.webp",prepare)
        self.assertIn("/download0/niak-case-%s-%s.png",prepare)
        self.assertNotIn("renderer.create_texture",prepare)

    def test_ps5_loader_only_enqueues(self):
        loader=SOURCE[SOURCE.index("std::uint32_t niak_load_case_art("):
                      SOURCE.index("// Drop mismatched completions BEFORE")]
        native=loader[loader.index("#if defined(__PROSPERO__)"):
                      loader.index("#else")]
        self.assertIn("queue_prepared_case_art(id,side);",native)
        self.assertNotIn("std::fopen(",native)
        self.assertNotIn("WebPDecode",native)
        self.assertNotIn("lodepng::decode",native)
        self.assertNotIn("renderer.create_texture",native)

    def test_latest_selected_title_and_one_result_backpressure(self):
        worker=SOURCE[SOURCE.index("struct PreparedCaseArt {"):
                      SOURCE.index("void niak_invalidate_prepared_case_art(")]
        self.assertIn("state.wake.wait(lock,[&]",worker)
        self.assertIn("!state.completed && !state.queued_sides.empty()",worker)
        self.assertIn("if(state.in_flight.size()>=8",worker)
        self.assertIn("state.queued_sides.clear();",worker)
        self.assertIn("++state.generation;",worker)
        self.assertIn("if(generation!=state.generation || id!=state.selected_id)",worker)
        self.assertIn("std::thread([] {prepared_case_worker();}).detach();",worker)
        self.assertNotIn("renderer.create_texture",worker)

    def test_renderer_rejects_stale_title_before_gpu_allocation(self):
        poll=SOURCE[SOURCE.index("std::uint32_t niak_take_prepared_case_art("):
                    SOURCE.index("void niak_destroy_case_texture(")]
        self.assertIn("state.completed_id==expected_id",poll)
        self.assertIn("state.selected_id==expected_id",poll)
        self.assertLess(poll.index("if(pixels.empty()"),poll.index("renderer.create_texture("))
        self.assertIn("track_case_texture(handle,w,h);",poll)
        self.assertIn("bool Catalog::refresh_pending_case_art(",STAGE)
        self.assertIn("catalog.refresh_pending_case_art(renderer);",STAGE)
        self.assertIn("niak_destroy_case_texture(renderer,handle);",STAGE)

    def test_new_cdn_completion_invalidates_old_prepared_pixels(self):
        method=SOURCE[SOURCE.index("void niak_invalidate_prepared_case_art("):
                      SOURCE.index("std::uint32_t niak_load_case_art(")]
        self.assertIn("++state.generation;",method)
        self.assertIn("state.queued_sides.clear();",method)
        self.assertIn("state.in_flight.clear();",method)
        self.assertIn("state.completed_pixels.clear();",method)
        self.assertIn("state.completed=false;",method)
        self.assertIn("void niak_invalidate_prepared_case_art(const char *title_id);",HEADER)
        self.assertIn("if(same_focus && completed!=last_case_completed_)",STAGE)
        self.assertIn("niak_invalidate_prepared_case_art(",STAGE)

if __name__=="__main__":
    unittest.main()
