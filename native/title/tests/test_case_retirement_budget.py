"""Bounded GPU case retirement keeps transitions responsive."""
from pathlib import Path
import unittest
SOURCE=(Path(__file__).resolve().parents[1]/"prepare.py").read_text()
class CaseRetirementTests(unittest.TestCase):
    def test_detached_case_does_not_reference_retired_texture(self):
        code=SOURCE[SOURCE.index("const int retire=retained_case_focus_;"):
                    SOURCE.index("retained_case_focus_=last_case_focus_;")]
        self.assertIn("retiring_case_textures_.push_back(*texture);",code)
        self.assertIn("*texture=0;",code)
        self.assertLess(code.index("retiring_case_textures_.push_back(*texture);"),code.index("*texture=0;"))
        self.assertNotIn("niak_destroy_case_texture(renderer,*texture)",code)
        self.assertIn("old.case_reload_mask=0;",code)
    def test_queue_bound_and_single_idle_gpu_retire(self):
        self.assertIn("while(retiring_case_textures_.size()>27u)",SOURCE)
        begin=SOURCE.index("bool Catalog::release_one_retired_case_texture(")
        end=SOURCE.index("bool Catalog::refresh_pending_case_background(",begin)
        method=SOURCE[begin:end]
        self.assertIn("retiring_case_textures_.pop_front();",method)
        self.assertIn("niak_destroy_case_texture(renderer,texture);",method)
        native=SOURCE[SOURCE.index("// One retired case texture consumes the idle frame's GPU budget."):
                      SOURCE.index("#else\n        // Host preview remains eager")]
        self.assertIn("catalog.release_one_retired_case_texture(renderer);",native)
        self.assertIn("if(navigation_idle && !gpu_budget_used",native)
    def test_rebuild_drains_all_detached_gpu_handles(self):
        begin=SOURCE.index("// A catalogue rebuild flushes detached handles")
        end=SOURCE.index("for (Item &item : items_)",begin)
        method=SOURCE[begin:end]
        self.assertIn("while(!retiring_case_textures_.empty())",method)
        self.assertLess(method.index("retiring_case_textures_.pop_front();"),
                        method.index("niak_release_case_templates(renderer);"))
        self.assertIn("niak_destroy_case_texture(renderer,texture);",method)
if __name__=="__main__":
    unittest.main()
