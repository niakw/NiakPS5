"""Secondary scanned faces must be eligible before touching GPU memory."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
CATALOG=(ROOT/"prepare.py").read_text()
WORKER=(ROOT/"case_art.cpp").read_text()

class CaseFacePreflightTests(unittest.TestCase):
    def test_decoded_completion_is_drained_before_preflight(self):
        poll=WORKER[WORKER.index("std::uint32_t niak_take_prepared_case_art("):
                    WORKER.index("void niak_destroy_case_texture(")]
        self.assertLess(poll.index("state.completed=false;"),
                        poll.index("if(accept && !accept("))
        self.assertLess(poll.index("state.in_flight.erase(selected_side);"),
                        poll.index("if(accept && !accept("))
        self.assertLess(poll.index("if(accept && !accept("),
                        poll.index("renderer.create_texture("))
        self.assertIn("state.wake.notify_one();",poll)

    def test_catalogue_drops_unneeded_secondary_art_before_vram(self):
        start=CATALOG.index("bool Catalog::refresh_pending_case_art(")
        end=CATALOG.index("bool Catalog::refresh_selected_case_art(",start)
        catalog=CATALOG[start:end]
        admission=catalog[catalog.index("const auto accept="):
                          catalog.index("char side[16]{};")]
        self.assertIn('std::strcmp(side,"front")==0',admission)
        self.assertIn('std::strcmp(side,"back")==0',admission)
        self.assertIn('std::strcmp(side,"spine")==0',admission)
        self.assertIn("!item.case_front && !item.case_poster",admission)
        self.assertIn("!item.case_front && !item.logo_art",admission)
        self.assertIn("(!item.case_front || !item.case_back)",admission)
        self.assertIn("!item.case_back &&",admission)
        self.assertIn("item.case_reload_mask & (1u<<",admission)
        self.assertIn("return false;",admission)
        self.assertIn("renderer,selected.title_id,side,&aspect,accept,&selected",catalog)
        self.assertIn("if(!destination || redundant || (*destination && !refreshing))",catalog)

if __name__=="__main__":
    unittest.main()
