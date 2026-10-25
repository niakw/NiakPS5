"""Immediate CPU scan cancellation on a changed Aurora game identity."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
CPP=(ROOT/"case_art.cpp").read_text()
HEADER=(ROOT/"case_art.hpp").read_text()
BUILDER=(ROOT/"prepare.py").read_text()

class PreparedCaseFocusTests(unittest.TestCase):
    def test_focus_change_cancels_queued_completed_and_inflight_work(self):
        start=CPP.index("void niak_select_prepared_case_focus(")
        end=CPP.index("void niak_invalidate_prepared_case_art(",start)
        code=CPP[start:end]
        for expected in ("std::lock_guard<std::mutex> lock(state.mutex)",
                         "if(state.selected_id==next)return;",
                         "state.selected_id=next;",
                         "++state.generation;",
                         "state.queued_sides.clear();",
                         "state.in_flight.clear();",
                         "state.completed=false;",
                         "state.completed_pixels.clear();",
                         "state.wake.notify_one();"):
            self.assertIn(expected,code)
        self.assertNotIn("renderer.",code)
        self.assertNotIn("std::fopen",code)
        self.assertNotIn("niak_prepare_case_pixels(",code)
        self.assertIn("niak_valid_title_id(id)?id:\"\"",code)
        self.assertIn("void niak_select_prepared_case_focus(const char *title_id);",HEADER)

    def test_focus_owner_sync_precedes_remote_cdn_and_is_not_idle_gated(self):
        update=BUILDER[BUILDER.index("const int index=focused_item();"):
                       BUILDER.index("// ---- animation state ----''')")]
        self.assertIn("std::strcmp(last_art_title_,art_id)!=0",update)
        self.assertIn("niak_select_prepared_case_focus(art_id[0]?art_id:nullptr);",update)
        self.assertLess(update.index("niak_select_prepared_case_focus("),
                        update.index("niak_select_case_art("))
        self.assertIn("niak_select_game_background_focus(art_id[0]?art_id:nullptr);",update)
        self.assertLess(update.index("niak_select_game_background_focus("),
                        update.index("niak_select_case_art("))
        self.assertNotIn("navigation_idle",update)
        self.assertIn('#include "niak/case_art.hpp"',BUILDER)

    def test_generation_blocks_finishing_old_decode_after_switch(self):
        worker=CPP[CPP.index("static void prepared_case_worker()"):
                   CPP.index("static void queue_prepared_case_art(")]
        self.assertIn("generation=state.generation;",worker)
        self.assertIn("if(generation!=state.generation || id!=state.selected_id)",worker)
        self.assertIn("state.completed_pixels=std::move(pixels);",worker)

if __name__=="__main__":
    unittest.main()
