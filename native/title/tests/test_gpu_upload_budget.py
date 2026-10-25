"""Only one queued PS5 image upload is accepted in an idle frame."""
from pathlib import Path
import unittest
SOURCE=(Path(__file__).resolve().parents[1]/"prepare.py").read_text()
class GpuUploadBudgetTests(unittest.TestCase):
    def test_single_gl_upload_budget_is_shared_across_media(self):
        start=SOURCE.index("// Limit successful asynchronous GPU uploads")
        end=SOURCE.index("#else\n        // Host preview remains eager",start)
        native=SOURCE[start:end]
        self.assertIn("bool gpu_budget_used=navigation_idle &&",native)
        self.assertIn("catalog.release_one_retired_case_texture(renderer);",native)
        self.assertIn("catalog.has_pending_covers()",native)
        self.assertIn("gpu_budget_used=true;",native)
        for loader in ("refresh_pending_game_icons","refresh_pending_case_art",
                       "refresh_pending_case_templates",
                       "refresh_pending_case_background"):
            self.assertIn("if(navigation_idle && !gpu_budget_used)\n"
                          "            gpu_budget_used=catalog."+loader+"(renderer);",native)
        self.assertIn("if(navigation_idle && !gpu_budget_used)\n"
                      "            niak_profile_poll_avatar(renderer);",native)
        self.assertIn("cover_stream_.remaining()!=0",SOURCE)
        order=[native.index("stream_next_covers(")]+[
            native.index("gpu_budget_used=catalog."+loader) for loader in
            ("refresh_pending_game_icons","refresh_pending_case_art",
             "refresh_pending_case_templates","refresh_pending_case_background")]
        order.append(native.index("niak_profile_poll_avatar(renderer)"))
        self.assertEqual(order,sorted(order))
    def test_host_preview_keeps_existing_eager_path(self):
        start=SOURCE.index("#else\n        // Host preview remains eager")
        end=SOURCE.index("#endif",start)
        host=SOURCE[start:end]
        self.assertIn("catalog.stream_next_covers(renderer,fonts,1)",host)
        self.assertIn("catalog.refresh_pending_case_art(renderer)",host)
if __name__=="__main__":
    unittest.main()
