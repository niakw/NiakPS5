"""Shared PS4/PS5 template decoding runs on worker; GPU upload stays on GL."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/"case_art.cpp").read_text()
HEADER=(ROOT/"case_art.hpp").read_text()
PATCH=(ROOT/"prepare.py").read_text()

class TemplateWorkerTests(unittest.TestCase):
    def test_one_cpu_pipeline_preserves_six_assets_and_alpha(self):
        cpu=SOURCE[SOURCE.index("bool prepare_case_template_pixels("):
                   SOURCE.index("#if defined(__PROSPERO__)\nstruct PreparedTemplates")]
        self.assertIn('"/data/homebrew/PPSA99386/assets/niak-templates/%s-%s.png"',cpu)
        self.assertIn('"/app0/assets/niak-templates/%s-%s.webp"',cpu)
        self.assertIn("niak_footer_paper_to_alpha(pixels,w,h,generation==0)",cpu)
        self.assertIn("niak_scale_case_rgba(pixels,w,h,side==2?96u:1024u,",cpu)
        self.assertIn('NIAK_CASE_TEMPLATE_ASSETS',cpu)
        self.assertNotIn("renderer.create_texture",cpu)

    def test_worker_never_calls_gl_or_rebuilds_stale_epoch(self):
        worker=SOURCE[SOURCE.index("struct PreparedTemplates {"):
                      SOURCE.index("#endif\nint case_template_index(")]
        self.assertIn("!state.completed && !state.queue.empty()",worker)
        self.assertIn("prepare_case_template_pixels(",worker)
        self.assertIn("if(epoch!=state.generation || !okay)continue;",worker)
        self.assertIn("state.queue.size()>=6",worker)
        self.assertIn("std::thread([] {template_reader_worker();}).detach();",worker)
        self.assertNotIn("renderer.",worker)

    def test_loader_enqueues_and_render_thread_uploads(self):
        loader=SOURCE[SOURCE.index("std::uint32_t niak_load_case_template("):]
        native=loader[loader.index("#if defined(__PROSPERO__)"):loader.index("#else")]
        self.assertIn("queue_case_template(index);",native)
        self.assertNotIn("std::fopen",native)
        self.assertNotIn("lodepng::decode",native)
        uploader=SOURCE[SOURCE.index("bool niak_upload_one_prepared_case_template("):
                        SOURCE.index("std::uint32_t niak_load_case_template(")]
        self.assertIn("template_textures[index]=renderer.create_texture(",uploader)
        self.assertIn("track_case_texture(template_textures[index],w,h);",uploader)
        self.assertIn("niak_upload_one_prepared_case_template",HEADER)

    def test_renderer_rebuild_invalidates_queue_before_destroy(self):
        release=SOURCE[SOURCE.index("void niak_release_case_templates("):
                       SOURCE.index("std::uint32_t niak_get_ready_case_template(")]
        self.assertLess(release.index("++state.generation;"),
                        release.index("niak_destroy_case_texture(renderer,template_textures[i]);"))
        self.assertIn("state.queue.clear();",release)
        self.assertIn("state.completed_pixels.clear();",release)

    def test_current_game_hydrates_only_missing_fixed_faces(self):
        self.assertIn("bool Catalog::refresh_pending_case_templates(",PATCH)
        self.assertIn("catalog.refresh_pending_case_templates(renderer);",PATCH)
        self.assertIn("attach(item.case_template_front,item.case_front,",PATCH)
        self.assertIn("attach(item.case_template_back,item.case_back,",PATCH)
        self.assertIn("attach(item.case_template_spine,item.case_spine,",PATCH)
        self.assertIn("niak_get_ready_case_template",HEADER)
if __name__=="__main__":
    unittest.main()
