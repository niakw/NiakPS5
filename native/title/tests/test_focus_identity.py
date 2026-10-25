"""LaunchBox selection follows stable game identity, not shelf position."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
BUILDER=(ROOT/"prepare.py").read_text()
WORKER=(ROOT/"case_auto_art.cpp").read_text()

class FocusIdentityTests(unittest.TestCase):
    def test_same_slot_with_new_game_must_switch_download_owner(self):
        block=BUILDER[BUILDER.index("// Only the focused GAME triggers remote LaunchBox artwork."):
                      BUILDER.index("// ---- animation state ----''')")]
        self.assertIn("const demo::Item &selected=item(index);",block)
        self.assertIn("selected.application || !selected.title_id[0]",block)
        self.assertIn("std::strcmp(last_art_title_,art_id)!=0",block)
        self.assertIn("std::snprintf(last_art_title_,sizeof(last_art_title_),",block)
        self.assertIn("niak_select_case_art(art_id[0]?art_id:nullptr);",block)
        self.assertNotIn("index!=last_art_selection_",block)
        self.assertIn("char last_art_title_[16] = {};",BUILDER)

    def test_same_game_at_another_index_does_not_restart_cdn(self):
        block=BUILDER[BUILDER.index("const demo::Item &selected=item(index);"):
                      BUILDER.index("// ---- animation state ----''')")]
        if_block=block[block.index("if(std::strcmp(last_art_title_,art_id)!=0)"):]
        self.assertIn("niak_select_case_art(",if_block)
        self.assertNotIn("last_art_selection_",BUILDER)
        self.assertIn("if(s.selected==(valid?std::string(title_id):std::string{}))return;",WORKER)

    def test_apps_and_empty_titles_clear_remote_selection(self):
        self.assertIn('"" : selected.title_id;',BUILDER)
        self.assertIn("niak_select_case_art(art_id[0]?art_id:nullptr);",BUILDER)
        self.assertIn('s.selected=valid?title_id:"";',WORKER)

if __name__=="__main__":
    unittest.main()
