"""Ensure late inventory updates restore navigation by title ID, never stale indices."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "patch_home.py").read_text()


class NavigationRestorePolicy(unittest.TestCase):
    def test_snapshot_captures_stable_title_before_catalogue_rebuild(self):
        self.assertIn("struct NiakNavigationSnapshot", SOURCE)
        self.assertIn("char last_selected_title_[16]{};", SOURCE)
        self.assertIn('"%s",item(focused_item()).title_id', SOURCE)
        self.assertIn('"%s",last_selected_title_', SOURCE)
        self.assertIn("~Aurora() override", SOURCE)

    def test_new_shelf_is_located_by_id_and_not_old_index(self):
        self.assertIn("for(std::size_t r=0;r<shelves_.size() && !found;++r)", SOURCE)
        self.assertIn("items[static_cast<std::size_t>(item_index)].title_id", SOURCE)
        self.assertIn("shelf.column=static_cast<int>(column);", SOURCE)
        self.assertIn("if(active_tab_!=3 && found)", SOURCE)
        self.assertIn("if(row_==1)active_tab_=2;", SOURCE)
        self.assertIn("row_position_.snap(float(row_));", SOURCE)
        self.assertIn("if(active_tab_==2 && !has_app_shelf())active_tab_=0;", SOURCE)
        self.assertIn('std::strcmp(shelves_[0].title,"Applications")==0', SOURCE)
        self.assertIn("Aucune application détectée", SOURCE)
        self.assertNotIn("Galerie de captures", SOURCE)

    def test_settings_retained_and_stale_catalogue_never_read_from_destructor(self):
        self.assertIn("nav.settings_cursor=settings_cursor_;", SOURCE)
        self.assertIn("settings_cursor_=std::clamp(nav.settings_cursor,0,9);", SOURCE)
        destructor = SOURCE.split('~Aurora() override {', 1)[1].split(
            "const app::ConceptInfo &info()", 1
        )[0]
        executable="\\n".join(line for line in destructor.splitlines()
                            if not line.lstrip().startswith("//"))
        self.assertNotIn("context_.catalog", executable)
        self.assertNotIn("focused_item()", executable)


if __name__ == "__main__":
    unittest.main()
