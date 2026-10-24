"""Production case hydration never loads a whole sleeve on one frame."""
from pathlib import Path
import unittest

SOURCE=(Path(__file__).resolve().parents[1]/"prepare.py").read_text()

class HydrationBudgetTest(unittest.TestCase):
    def test_ps5_icon_stream_does_not_eagerly_decode_case(self):
        host_scope=SOURCE[SOURCE.index("#if !defined(__PROSPERO__)\\n            if(index==niak::case_media_stats.preferred_index)"):]
        self.assertLess(host_scope.index("if(index==niak::case_media_stats.preferred_index)"),
                        host_scope.index("item.case_front = niak_load_case_art("))
        self.assertLess(host_scope.index("item.case_front = niak_load_case_art("),
                        host_scope.index("} // Host preview uses complete fixtures; PS5 hydrates while idle.\\n#endif"))
        self.assertNotIn("if(index==niak::case_media_stats.preferred_index) {\\n#endif",SOURCE)
        self.assertIn("case_hydration_step_=0;",SOURCE)

    def test_one_media_source_per_idle_tick(self):
        start=SOURCE.index("switch(case_hydration_step_++)")
        end=SOURCE.index("default: break;",start)
        sequence=SOURCE[start:end]
        for n in range(11):
            self.assertIn("case "+str(n)+":",sequence)
        self.assertIn("case_hydration_step_>=11u",SOURCE)
        self.assertIn('missing(selected.case_front,"front")',sequence)
        self.assertIn('missing(selected.case_back,"back")',sequence)
        self.assertIn('missing(selected.case_spine,"spine")',sequence)
        self.assertIn("case_status.sides_completed[side]!=last_case_sides_[side]",SOURCE)
        self.assertIn("niak_destroy_case_texture(renderer,*updated_side.second)",SOURCE)

if __name__=="__main__":
    unittest.main()
