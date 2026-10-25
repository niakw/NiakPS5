"""The visible retail sleeve remains stable while CDN artwork refreshes."""
from pathlib import Path
import unittest

SOURCE=(Path(__file__).resolve().parents[1]/"prepare.py").read_text()

class CaseTextureLifecycleTests(unittest.TestCase):
    def test_cdn_does_not_free_visible_face_before_decode_completes(self):
        method=SOURCE[SOURCE.index("bool Catalog::refresh_selected_case_art("):
                      SOURCE.index("} // namespace hui::demo",SOURCE.index("bool Catalog::refresh_selected_case_art("))]
        self.assertIn("if(updated[side] && side!=3u)",method)
        self.assertIn("selected.case_reload_mask|=(1u<<side);",method)
        update=method[method.index("for(unsigned side=0;side<updated.size();++side)"):
                      method.index("const auto missing=")]
        self.assertNotIn("niak_destroy_case_texture(",update)
        missing=method[method.index("const auto missing="):
                       method.index("const char *platform=")]
        self.assertIn("if(texture && !(selected.case_reload_mask & bit))return;",missing)
        self.assertLess(missing.index("if(refreshed) {"),
                        missing.index("niak_destroy_case_texture(renderer,texture);"))
        self.assertIn("selected.case_reload_mask&=~bit;",missing)

    def test_swap_of_official_face_occurs_after_new_gpu_upload(self):
        accept=SOURCE[SOURCE.index("bool Catalog::refresh_pending_case_art("):
                      SOURCE.index("bool Catalog::refresh_selected_case_art(")]
        self.assertLess(accept.index("niak_take_prepared_case_art("),
                        accept.index("if(*destination)niak_destroy_case_texture(renderer,*destination);"))
        self.assertLess(accept.index("if(*destination)niak_destroy_case_texture(renderer,*destination);"),
                        accept.index("*destination=handle;"))
        self.assertIn("const bool refreshing=bit && (selected.case_reload_mask & bit);",accept)
        self.assertIn("(*destination && !refreshing)",accept)
        self.assertIn("selected.case_reload_mask&=~bit;",accept)

    def test_rebuild_resets_pending_swap_and_does_not_own_shared_templates(self):
        self.assertIn("unsigned case_reload_mask = 0;",SOURCE)
        self.assertIn("item.case_reload_mask=0;",SOURCE)
        self.assertIn("niak_release_case_templates(renderer);",SOURCE)
        self.assertIn("selected.case_template_front=0;",SOURCE)
        self.assertIn("std::deque<std::uint32_t> retiring_case_textures_;",SOURCE)
        self.assertIn("release_one_retired_case_texture",SOURCE)

if __name__=="__main__":
    unittest.main()
