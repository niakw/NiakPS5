#!/usr/bin/env python3
"""Simple source contract tests for the pinned GPU-native title staging scripts."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]

class NativeTitleTests(unittest.TestCase):
    def test_autostart_is_explicit_and_reversible(self):
        source = (ROOT / "title" / "autostart.c").read_text()
        self.assertIn("niakps5-autostart.enabled", source)
        self.assertIn("niakps5-autostart.disable", source)
        self.assertIn("sceSystemServiceLaunchApp", source)
        self.assertIn("GetAppIdOfRunningBigApp", source)
        self.assertIn("niak_redirect_arm_after_launch(",source)
        self.assertIn('niak_socket_guard(client)',source)
        self.assertIn('niak_socket_send(client,"PONG\\n",5)',source)
        self.assertIn('niak_socket_send(fd,"PING\\n",5)',(ROOT/"title"/"launch_bridge.cpp").read_text())
        self.assertNotIn("current_niak=running",source)
        self.assertNotIn("ptrace(", source)
        self.assertNotIn("mount(", source)

    def test_exact_ftp_package(self):
        import tempfile
        import json
        import sys
        import zipfile
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "PPSA99386"
            for path in ("eboot.bin", "sce_module/libc.prx", "sce_sys/param.json"):
                target=base / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({"titleId":"PPSA99386"}) if
                                  path.endswith("param.json") else "nonempty")
            (base / "assets").mkdir()
            (base / "tools").mkdir()
            (base / "tools/niakps5.elf").write_bytes(b"\\x7fELF" if False else bytes([127,69,76,70]))
            package=Path(temp) / "PPSA99386.zip"
            subprocess.run([sys.executable, str(ROOT / "title" / "pack_ftp.py"),
                            "--folder", str(base), "--output", str(package)], check=True)
            with zipfile.ZipFile(package) as z:
                self.assertIsNone(z.testzip())
                self.assertEqual([n.split("/")[0] for n in z.namelist()],
                                 ["PPSA99386"] * len(z.namelist()))
                self.assertFalse(any(n.endswith(".zip") for n in z.namelist()))
                self.assertIn("PPSA99386/tools/niakps5.elf", z.namelist())
                self.assertEqual((z.getinfo("PPSA99386/tools/niakps5.elf").external_attr >> 16) & 0o777, 0o755)
                self.assertEqual((z.getinfo("PPSA99386/eboot.bin").external_attr >> 16) & 0o777, 0o755)
                self.assertEqual((z.getinfo("PPSA99386/sce_module/libc.prx").external_attr >> 16) & 0o777, 0o644)
            (base / "assets/inner.zip").write_text("forbidden")
            with self.assertRaises(subprocess.CalledProcessError):
                subprocess.run([sys.executable, str(ROOT / "title" / "pack_ftp.py"),
                                "--folder", str(base), "--output", str(package)],
                               check=True, capture_output=True)

    def test_standalone_native_title(self):
        source = (ROOT / "title" / "build.sh").read_text()
        self.assertIn("PPSA99386", source)
        self.assertIn("2188642afbcc8d84d36149124f3d9e39dc1b1a05", source)
        self.assertIn("dist/$title/eboot.bin", source)
        self.assertIn("sce_module/libc.prx", source)
        self.assertNotIn("niakps5_bootstrap.elf", source)

    def test_daily_wallpaper_pipeline(self):
        source = (ROOT / "title" / "fetch_daily_games.py").read_text()
        native = (ROOT / "title" / "daily_backdrop.cpp").read_text()
        compile(source, "fetch_daily_games.py", "exec")
        self.assertIn("sharpemu/sharpemu-site", source)
        self.assertIn("image.api.playstation.com", source)
        self.assertIn("niak_daily_backdrop", native)
        self.assertIn("std::localtime", native)

    def test_wallpaper_readability_contract(self):
        source=(ROOT / "title" / "patch_home.py").read_text()
        preview=(ROOT / "title" / "validate_preview.py").read_text()
        self.assertIn("Color::rgb(0x081014, 0.52f)", source)
        self.assertIn("Color::rgb(0x051015, 0.65f)", source)
        self.assertIn("Wallpaper washes out NiakPS5", preview)
        self.assertIn("outer_face", (ROOT / "title" / "case_renderer.cpp").read_text())

    def test_final_rendering_contracts(self):
        source=(ROOT / "title" / "polish.py").read_text()
        compile(source,"polish.py","exec")
        for expected in ("cover_is_image ? gfx::kFullUv : gfx::kCanvasUv",
                         "row_ == 0", "NiakPS5", "play.x + 132"):
            self.assertIn(expected,source)

    def test_focus_case_replaces_selected_tile_and_not_a_loader(self):
        source=(ROOT/"title"/"polish.py").read_text()
        case=(ROOT/"title"/"case_renderer.cpp").read_text()
        self.assertIn("niak_draw_rotating_case(list,it,art,",source)
        self.assertNotIn("niak_draw_rotating_case(list, it, ring",source)
        self.assertNotIn("niak_draw_rotating_case(list, it, art",source)
        self.assertIn("case_selected_at_",source)
        self.assertIn("clock_ - case_selected_at_",source)
        self.assertIn("shelf.column = next;",source)
        self.assertIn("row_ = next;",source)
        self.assertIn("if(!item.title_id[0])",case)
        self.assertNotIn("loading_percent",case)
        self.assertNotIn("progress_percent",case)

    def test_retail_case_runtime(self):
        source=(ROOT/"title"/"case_renderer.cpp").read_text()
        for name in ("case_front","case_back","case_spine","PS4","PS5","yaw_at",
                     "list.image","item.blurb","!item.title_id[0]"):
            self.assertIn(name,source)
        stage=(ROOT/"title"/"prepare.py").read_text()
        self.assertIn("niak_load_case_art",stage)
        self.assertIn("niak_load_game_background",stage)
        self.assertIn("case_scene",source)
        self.assertIn("sce_sys/pic1.png",(ROOT/"title"/"game_icons.cpp").read_text())
        self.assertIn("niak_socket_guard(sock)",(ROOT/"title"/"game_icons.cpp").read_text())
        self.assertIn("niak_socket_send(sock,", (ROOT/"title"/"game_icons.cpp").read_text())
        self.assertIn("niak_http_icon_body(response,false", (ROOT/"title"/"game_icons.cpp").read_text())
        self.assertIn('"http_icon_response.hpp"',(ROOT/"title"/"prepare.py").read_text())
        icons=(ROOT/"title"/"game_icons.cpp").read_text()
        self.assertIn("/mnt/ext0/user/app/%s/sce_sys/icon0.png",icons)
        self.assertIn("/mnt/ext1/user/appmeta/%s/icon0.png",icons)
        self.assertIn("niak_load_profile_cache_png",(ROOT/"title"/"profile.cpp").read_text())
        self.assertIn("niak-profile-source.txt",(ROOT/"title"/"profile.cpp").read_text())
        profile=(ROOT/"title"/"profile.cpp").read_text()
        self.assertIn("checked_at=now",profile)
        self.assertIn("current!=niak_avatar_owner",profile)
        self.assertNotIn("static bool initialized=false",profile)
        self.assertIn('mark_profile_asset(user,"dds")',(ROOT/"title"/"autostart.c").read_text())
        self.assertIn("invalidate_profile_asset()", (ROOT/"title"/"autostart.c").read_text())
        self.assertIn("mkstemp(temp)",(ROOT/"title"/"autostart.c").read_text())
        self.assertNotIn('snprintf(temp,sizeof(temp),"%s.tmp",dest)',(ROOT/"title"/"autostart.c").read_text())
        self.assertIn("niak_next_daily_backdrop",(ROOT/"title"/"daily_backdrop.cpp").read_text())
        self.assertIn("/data/homebrew/%s/sce_sys/icon0.png",(ROOT/"title"/"game_icons.cpp").read_text())
        self.assertIn("case_renderer.cpp",stage)
        self.assertIn('item.case_spine = niak_load_case_art(renderer,item.title_id,"spine")',stage)
        self.assertIn("printed(",source)
        self.assertIn("left_spine(",source)
        self.assertIn("if(item.case_spine)",source)
        self.assertIn("printed(list,image,fill",source)
        self.assertIn("printed(list,image,art",source)
        # Fallback design is runtime geometry; no generated image or new
        # commercial artwork is embedded in the application package.
        self.assertIn("APERÇU RECONSTITUÉ — NON OFFICIEL",source)
        self.assertIn("const bool ps4=item.title_id[0]=='C'",source)
        self.assertIn("0.885f*v",source)
        self.assertIn("footer_start=ps4?0.57f:0.69f",source)
        self.assertIn("description_top=ps4?0.482f:0.505f",source)
        self.assertIn("area.second,ps4?12.f:15.f",source)
        self.assertIn("fonts.regular,description",source)
        self.assertIn("if(std::fabs(camera.cs)>0.90f)",source)
        self.assertNotIn("case_wrap",source)

        self.assertIn("item.cover_is_image",source)
        self.assertIn("box-front.png",(ROOT/"title"/"case_art.cpp").read_text())
        self.assertIn("PS4\":\"PS5",source)
        self.assertIn("outer_face(",source)
        self.assertIn("right_seal(",source)
        self.assertIn("Positive sin means",source)
        for forbidden in ("disk_tray(", "inside_door(", "front_door(",
                          "Surface flap(", "Motion {", "motion.opening"):
            self.assertNotIn(forbidden,source)
        preview=(ROOT/"title"/"host_preview.py").read_text()
        for obsolete in ("case-02-open", "case-01-unlatch",
                         "case-03-close", "case-04-turn"):
            self.assertNotIn(obsolete,preview)
        for angle in ("case-00-front","case-01-spine",
                      "case-02-back","case-03-return"):
            self.assertIn(angle,preview)
        self.assertIn("const Camera camera{",source)
        self.assertNotIn("case_wrap",source)
        self.assertIn("if(back&&show_face)",source)
        # Near-front/back holds use fewer quads; full perspective returns
        # during rotation to preserve the 3D box proportions and corners.
        self.assertIn("const bool near_frontal=std::fabs(camera.cs)>0.985f",source)
        self.assertIn("near_frontal?12:32",source)
        self.assertIn("near_frontal?12:24",source)
        self.assertIn("near_frontal?12:28",source)
        self.assertIn("if(!back&&show_face)",source)
        self.assertIn("if(show_spine)",source)
        self.assertIn("if(show_seal)",source)
        host=(ROOT/"title"/"host_preview.py").read_text()
        self.assertIn("make_case_art_fixtures",host)
        self.assertIn("case-04-homebrew-fallback",host)
        self.assertIn("case-05-wallpaper-r1",host)
        self.assertIn("case-06-touchpad-details",host)
        self.assertIn("case-07-ps4-template-front",host)
        self.assertIn('ids[n][0]==\'C\'?"PS4":"PS5"',host)
        self.assertIn("case-08-ps4-template-back",host)
        self.assertIn("PS4 front and back overlays rendered identically",
                      (ROOT/"title"/"validate_preview.py").read_text())
        self.assertIn("Touchpad click did not open",(ROOT/"title"/"validate_preview.py").read_text())
        self.assertIn("R1 did not visibly switch",(ROOT/"title"/"validate_preview.py").read_text())
        self.assertIn("item.application=n==4",host)
        self.assertIn("case-04-homebrew-fallback",
                      (ROOT/"title"/"validate_preview.py").read_text())
        self.assertIn("NIAK_CASE_PREVIEW_ASSETS",(ROOT/"title"/"case_art.cpp").read_text())
        self.assertIn("NIAK_CASE_TEMPLATE_ASSETS",(ROOT/"title"/"case_art.cpp").read_text())
        self.assertIn("niak_load_case_template",(ROOT/"title"/"case_art.hpp").read_text())
        self.assertIn("stats.fronts+=item.case_front!=0",stage)
        self.assertIn("stats.templates+=item.case_template_front!=0",stage)
        self.assertIn("Médias lus par NiakPS5",
                      (ROOT/"title"/"patch_home.py").read_text())
        settings_ui=(ROOT/"title"/"patch_home.py").read_text()
        self.assertIn("now-last_check>=15",settings_ui)
        self.assertIn("journal_status,sizeof(journal_status)",settings_ui)
        self.assertNotIn("static const char *journal_status",settings_ui)
        self.assertIn("now<last_check",settings_ui)
        self.assertNotIn("static const bool live_broker",settings_ui)
        self.assertIn("niak_release_case_templates",(ROOT/"title"/"case_art.cpp").read_text())
        self.assertIn("niak_release_case_templates(renderer)",stage)
        self.assertIn("renderer.destroy_texture(*texture)",stage)
        self.assertIn("case_template_back",source)
        self.assertIn("case_template_front",source)
        self.assertIn("case_template_spine",source)
        self.assertIn("niak-preview-templates",host)
        self.assertIn("NIAK_CASE_TEMPLATE_ASSETS",
                      (ROOT.parent/".github/workflows/native-title.yml").read_text())
        self.assertNotIn("face_w=bounds.w",source)

    def test_real_top_navigation(self):
        from pathlib import Path
        code = (ROOT / "title" / "patch_home.py").read_text()
        compile(code, "patch_home.py", "exec")
        for token in ("update_tabs", "update_page", "draw_aux_page",
                      "context_.settings_changed = true", "Profil non lie"):
            self.assertIn(token, code)

    def test_real_catalog_only(self):
        source = (ROOT / "title" / "prepare.py").read_text()
        self.assertIn('niak_scan_games("/system_data/priv/mms/app.db"', source)
        self.assertIn("Bibliothèque indisponible", source)
        self.assertIn("shelves_.resize(2)", source)
        self.assertIn("niak_launch_registered_title", source)
        self.assertIn("niak-manrope.huifont", source)
        self.assertIn("niak-instrument-serif.huifont", source)
        self.assertIn("IDENTIFIANT DU TITRE", source)
        self.assertIn("item.application",source)
        self.assertIn('item.studio=item.application ? "Application installée"',source)
        self.assertNotIn('game.is_homebrew ? "Application" : "Jeu installé"',source)
        # Regression: the fallback homebrew flag must NOT overwrite an
        # explicit PS5 media/game applicationCategoryType decision.
        start=source.index("if(std::strcmp(game.id,\"PPSA99386\")==0)")
        end=source.index("item.blurb = owned_blurbs_",start)
        classification=source[start:end]
        self.assertLess(classification.index('std::strcmp(game.title,"Mes vidéos")==0'),
                        classification.index("game.application_category==1"))
        self.assertLess(classification.index("game.application_category==2"),
                        classification.index("game.application_category==1"))
        self.assertLess(classification.index('meta.category=="Application"'),
                        classification.index("item.application=game.is_homebrew!=0"))
        self.assertEqual(classification.count("item.application=game.is_homebrew!=0"),1)
        self.assertNotIn('else item.application=game.is_homebrew!=0;',classification)
        self.assertIn("niak_launch_registered_title",source)
        self.assertIn("serve_launch_requests",(ROOT/"title"/"autostart.c").read_text())
        broker=(ROOT/"title"/"autostart.c").read_text()
        self.assertNotIn("ticks<21600",broker)
        self.assertIn("is_regular_file(NIAK_DISABLED)",broker)
        self.assertIn("PING\\n",(ROOT/"title"/"autostart.c").read_text())
        self.assertIn("niak_launch_broker_ready",(ROOT/"title"/"patch_home.py").read_text())
        self.assertIn('std::strcmp(game.title,"Mes vidéos")==0',source)
        self.assertIn('if (input.is_pressed(Action::page_next))',
                      (ROOT/"title"/"patch_home.py").read_text())
        # Wallpapers should not be almost invisible under stacked overlays.
        wallpaper_ui=(ROOT/"title"/"patch_home.py").read_text()
        self.assertIn("kWhite.with_alpha(0.85f)",wallpaper_ui)
        self.assertIn("Color::rgb(0x081014, 0.52f)",wallpaper_ui)
        self.assertIn("Color::rgb(0x051015, 0.65f)",wallpaper_ui)
        self.assertIn('ui::Button::cross, "Choisir"',
                      (ROOT/"title"/"polish.py").read_text())
        self.assertIn("Stratégie au tour par tour",
                      (ROOT/"title"/"title_meta.cpp").read_text())
        self.assertIn("Action::touch",source)
        self.assertIn("concepts_.size()>1 && input.is_pressed(Action::touch)",source)
        self.assertIn('for action in ("pressed","released","held"):',source)
        self.assertIn("if (concepts_.size()>1) forwarded.{action} &= ~kShellActions;",source)
        self.assertIn('meta.category=="Application"',source)
        self.assertIn("data.genre.clear()",
                      (ROOT/"title"/"title_meta.cpp").read_text())
        self.assertIn('shelves_[0].items=shelves_[1].items',source)
        self.assertNotIn('shelves_[0].items.push_back(shelves_[1].items.front())',source)
        self.assertIn("/data/homebrew/PPSA99386/assets/niak-local-titles.tsv",
                      (ROOT/"title"/"title_meta.cpp").read_text())
        self.assertIn("applicationCategoryType",(ROOT/"title"/"ftp_install.py").read_text())
        self.assertIn("/download0/niak-favorites.tsv",source)
        self.assertIn("std::stable_partition",source)
        self.assertIn("Bibliothèque PS5",source)
        self.assertIn("1720, true",source)
        self.assertNotIn("Jeu ou application installé sur cette console.",source)
        self.assertIn("CATALOGUE INACCESSIBLE", source)
        self.assertIn("Fake clock or rating remains", source)
        self.assertIn("concepts::make_aurora", source)
        self.assertNotIn("Lumen Drift", source)
        compile(source, "prepare.py", "exec")

if __name__ == "__main__":
    unittest.main()
