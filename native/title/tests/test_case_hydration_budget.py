"""Production case hydration never loads a whole sleeve on one frame."""
from pathlib import Path
import unittest

SOURCE=(Path(__file__).resolve().parents[1]/"prepare.py").read_text()

class HydrationBudgetTest(unittest.TestCase):
    def test_ps5_icon_stream_does_not_eagerly_decode_case(self):
        host_start=SOURCE.index("#if !defined(__PROSPERO__)\n            // On the host")
        host_end=SOURCE.index("#endif // Host fixtures are eager;",host_start)
        host_scope=SOURCE[host_start:host_end]
        for side in ("front","back","spine"):
            self.assertIn('item.case_'+side+' = niak_load_case_art(',host_scope)
        self.assertNotIn("if(index==niak::case_media_stats.preferred_index)",host_scope)
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
        self.assertIn("selected.case_reload_mask|=(1u<<side);",SOURCE)
        self.assertIn("if(texture && !(selected.case_reload_mask & bit))return;",SOURCE)
        self.assertIn("if(*destination)niak_destroy_case_texture(renderer,*destination);",SOURCE)

if __name__=="__main__":
    unittest.main()
