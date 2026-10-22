#!/usr/bin/env python3
"""Prepare a dedicated NiakPS5 GPU-native title from pinned PS5_VKHomebrewUI.
Run ONLY on a fresh staging checkout; does not change system or console files.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import re

TITLE_ID = "PPSA99386"

def replace_once(path, old, new):
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one anchor in {path}: {old[:60]!r}; found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

def prepare(kit: Path, project: Path, revision: str):
    registry = kit / "src/concepts/registry.cpp"
    reg = registry.read_text()
    begin = reg.index("    static constexpr ConceptFactory kFactories[] = {")
    end = reg.index("    };", begin) + len("    };")
    reg = reg[:begin] + "    static constexpr ConceptFactory kFactories[] = {concepts::make_aurora};" + reg[end:]
    registry.write_text(reg)

    aurora = kit / "src/concepts/aurora.cpp"
    replace_once(aurora, '#include "ui/motion.hpp"', '#include "ui/motion.hpp"\n#include "platform/ps5/system.hpp"\n#include "niak/version.hpp"\n#include "niak/launch_bridge.hpp"')
    replace_once(aurora, 'namespace hui::concepts\n{', 'namespace hui::concepts\n{')
    old = '''        shelves_.resize(3);
        shelves_[0].title = "Continue playing";
        shelves_[1].title = "Your library";
        shelves_[2].title = "New this year";
        for (int i = 0; i < static_cast<int>(items.size()); ++i)
        {
            const demo::Item &item = items[static_cast<std::size_t>(i)];
            if (item.progress > 0.0f && item.progress < 1.0f && shelves_[0].items.size() < 9)
                shelves_[0].items.push_back(i);
            shelves_[1].items.push_back(i);
            if (item.year == 2026)
                shelves_[2].items.push_back(i);
        }'''
    new = '''        // Library and verified homebrew apps, without imaginary application cards.
        shelves_.resize(2);
        shelves_[0].title = "Bibliothèque PS5";
        shelves_[1].title = "Applications";
        for (int i = 0; i < static_cast<int>(items.size()); ++i)
        {
            // Use a category property rather than relying on PPSA/CUSA prefixes.
            const demo::Item &entry=items[static_cast<std::size_t>(i)];
            (entry.application ? shelves_[1] : shelves_[0]).items.push_back(i);
        }
        // Recent launch/play/install first; unknown dates sort alphabetically.
        for(Shelf &shelf:shelves_) {
            std::stable_sort(shelf.items.begin(),shelf.items.end(),
                [&items](int left,int right) {
                    const demo::Item &a=items[static_cast<std::size_t>(left)];
                    const demo::Item &b=items[static_cast<std::size_t>(right)];
                    const int date=std::strcmp(a.recently_used,b.recently_used);
                    if(date!=0)return date>0;
                    return std::strcmp(a.title,b.title)<0;
                });
        }
        // Empty rows crash the upstream focus/card code. When there are
        // only applications, show one Applications row rather than putting
        // an application into the Games row or duplicating its tile.
        if (shelves_[0].items.empty() && !shelves_[1].items.empty()) {
            shelves_[0].title=shelves_[1].title;
            shelves_[0].items=shelves_[1].items;
            shelves_.resize(1);
        } else if (shelves_[1].items.empty()) {
            shelves_.resize(1);
        }'''
    replace_once(aurora, old, new)
    replace_once(aurora, '"Aurora Shelf",', '"NiakPS5",')
    replace_once(aurora, '"A console home screen: hero panel, cover shelves, frosted details",',
                 '"Votre console. Votre espace. Accueil natif NiakTV.",')
    replace_once(aurora, '''        const char *tabs[] = {"Home", "Library", "Store", "Captures"};''',
                 '''        const char *tabs[] = {"NIAK", "Jeux", "Multimedia", "Reglages"};''')
    replace_once(aurora, 'Color::rgb(0x7ff0d8),', 'Color::rgb(0x91f5df),')
    old_launch = '''            if (action_ == 0)
            {
                feedback.play(audio::Cue::launch);
                feedback.rumble(0.7f, 0.18f);
                sheet_open_ = false;
            }'''
    new_launch = '''            if (action_ == 0)
            {
                const demo::Item &selected = item(focused_item());
                if (selected.title_id[0] == '\\0')
                {
                    sys::log("[NiakPS5] No launchable title: catalog unavailable");
                    std::snprintf(launch_error_,sizeof(launch_error_),
                        "Titre indisponible : identifiant de lancement manquant");
                    feedback.play(audio::Cue::error);
                }
                else
                {
                    const int rc = niak_launch_registered_title(selected.title_id);
                    sys::log("[NiakPS5] launch %.9s => 0x%08x", selected.title_id,
                             static_cast<unsigned>(rc));
                    if(rc == 0) {
                        launch_error_[0] = '\\0';
                        feedback.play(audio::Cue::launch);
                        sheet_open_ = false;
                    } else {
                        std::snprintf(launch_error_,sizeof(launch_error_),
                            rc==-2 ? "Service de lancement PLDmgr indisponible (0x%08X)" :
                            rc==-3 ? "Titre non autorisé ou non installé (0x%08X)" :
                                     "Lancement refusé (code 0x%08X)",
                            static_cast<unsigned>(rc));
                        feedback.play(audio::Cue::error);
                    }
                }
            }'''
    replace_once(aurora, old_launch, new_launch)
    replace_once(aurora, '            sheet_open_ = true;',
                 '            launch_error_[0] = 0;\n            sheet_open_ = true;')
    # The DualSense touchpad click is an explicit details shortcut, while
    # Cross keeps the normal confirm action. The same sheet opens either way.
    replace_once(aurora,
        '        if (input.is_pressed(Action::confirm))\n'
        '        {\n'
        '            launch_error_[0] = 0;',
        '        if (input.is_pressed(Action::confirm) || '
        'input.is_pressed(Action::touch))\n'
        '        {\n'
        '            launch_error_[0] = 0;')
    # Private favorites are reloaded and sorted before the first screen draw.
    replace_once(aurora, '        favorite_.assign(items.size(), false);',
    """        favorite_.assign(items.size(), false);
        if (std::FILE *saved=std::fopen("/download0/niak-favorites.tsv","rb"))
        {
            char line[24]{};
            while (std::fgets(line,sizeof(line),saved))
            {
                line[std::strcspn(line,"\\r\\n")]=0;
                for (std::size_t k=0;k<items.size();++k)
                    if (std::strcmp(items[k].title_id,line)==0)
                        favorite_[k]=true;
            }
            std::fclose(saved);
            for (Shelf &shelf:shelves_)
                std::stable_partition(shelf.items.begin(),shelf.items.end(),
                    [this](int i){return favorite_[static_cast<std::size_t>(i)];});
        }""")
    # Failed launch must remain visible in the detail panel rather than
    # closing as if it had succeeded; the PS5 return code is diagnostic.
    replace_once(aurora, '    int action_ = 0;', 
                 "    char launch_error_[96] = {};\n    int action_ = 0;")
    # Favorites affect actual positions, not merely the star decoration.
    replace_once(aurora, '        favorite_[index] = !favorite_[index];',
                 """        favorite_[index] = !favorite_[index];
        for (Shelf &shelf : shelves_)
        {
            if (shelf.items.empty()) continue;
            const int selected=shelf.items[static_cast<std::size_t>(
                std::clamp(shelf.column,0,int(shelf.items.size())-1))];
            std::stable_partition(shelf.items.begin(),shelf.items.end(),
                [this](int id) {return favorite_[static_cast<std::size_t>(id)];});
            for (std::size_t pos=0;pos<shelf.items.size();++pos)
                if (shelf.items[pos]==selected) {
                    shelf.column=static_cast<int>(pos);
                    break;
                }
        }""")
    replace_once(aurora,
        '        if (favorite_[index])\n            star_.trigger();',
        """        if (favorite_[index])
            star_.trigger();
        // Atomic private storage. No writes to Sony's system databases.
        if(std::FILE *out=std::fopen("/download0/niak-favorites.tsv.tmp","wb"))
        {
            bool success=true;
            for(std::size_t i=0;i<favorite_.size();++i)
                if(favorite_[i] && item(static_cast<int>(i)).title_id[0])
                    if(std::fprintf(out,"%s\\n",item(static_cast<int>(i)).title_id)<0)
                        success=false;
            if(std::fflush(out)!=0)success=false;
            if(std::fclose(out)!=0)success=false;
            if(success)
                std::rename("/download0/niak-favorites.tsv.tmp",
                            "/download0/niak-favorites.tsv");
            else
                std::remove("/download0/niak-favorites.tsv.tmp");
        }""")
    # The single-design title does not display the UI Lab tour banner.
    shell = kit / "src/app/shell.cpp"
    replace_once(shell, '    banner_ = kBannerSeconds;\n}\n', '    banner_ = 0.0f;\n}\n')
    # Single-concept NiakPS5 owns R1 and touchpad. The pinned upstream Shell
    # captures these actions for its multi-concept switcher, removes them from
    # the forwarded InputFrame, and opens an English developer info panel.
    # That interception made both features unreachable despite compiling.
    replace_once(shell,
        '    if (input.is_pressed(Action::page_next) || input.is_pressed(Action::page_prev))',
        '    if (concepts_.size()>1 && (input.is_pressed(Action::page_next) || input.is_pressed(Action::page_prev)))')
    replace_once(shell,
        '    if (input.is_pressed(Action::touch))',
        '    if (concepts_.size()>1 && input.is_pressed(Action::touch))')
    for action in ("pressed","released","held"):
        replace_once(shell,
            f'    forwarded.{action} &= ~kShellActions;',
            f'    if (concepts_.size()>1) forwarded.{action} &= ~kShellActions;')

    catalog_h = kit / "src/demo/catalog.hpp"
    replace_once(catalog_h, '#include <cstdint>', '#include <cstdint>\n#include <deque>\n#include <string>')
    replace_once(catalog_h, '    std::uint32_t cover = 0;',
                 '    char title_id[16] = {};\n    bool homebrew = false;\n    bool application = false;\n    char recently_used[48] = {};\n    bool cover_is_image = false;\n    std::uint32_t case_front = 0;\n    std::uint32_t case_back = 0;\n    std::uint32_t case_spine = 0;\n    std::uint32_t logo_art = 0;\n    std::uint32_t cover = 0;')
    replace_once(catalog_h, '    std::vector<Item> items_;',
                 '    std::deque<std::string> owned_titles_;\n    std::deque<std::string> owned_blurbs_;\n    std::vector<Item> items_;')

    src_niak = kit / "src/niak"
    src_niak.mkdir(parents=True, exist_ok=True)
    if not re.fullmatch(r"[0-9a-f]{7,12}",revision):
        raise ValueError("Invalid Git revision")
    (src_niak/"version.hpp").write_text(
        '#pragma once\nnamespace niak {inline constexpr const char *revision = "'
        + revision + '";}\n',encoding="utf8")
    for filename in ("catalog.c", "catalog.h", "shadowmount_api.c", "shadowmount_api.h"):
        shutil.copy2(project / "native" / filename, src_niak / filename)
    for filename in ("title_meta.cpp", "title_meta.hpp"):
        shutil.copy2(project / "native" / "title" / filename, src_niak / filename)
    shutil.copy2(project / "native" / "title" / "ps_titles.tsv",
                 kit / "assets" / "niak-ps-titles.tsv")
    for filename in ("daily_backdrop.cpp", "daily_backdrop.hpp", "daily_runtime.cpp", "daily_runtime.hpp"):
        shutil.copy2(project / "native" / "title" / filename, src_niak / filename)
    shutil.copy2(project / "native" / "title" / "vendor" / "picojson.h", src_niak / "picojson.h")
    for filename in ("game_icons.cpp", "game_icons.hpp"):
        shutil.copy2(project / "native" / "title" / filename, src_niak / filename)
    for filename in ("case_renderer.cpp","case_renderer.hpp","case_art.cpp","case_art.hpp",
                     "launch_bridge.cpp","launch_bridge.hpp"):
        shutil.copy2(project / "native" / "title" / filename, src_niak / filename)
    for filename in ("profile.cpp", "profile.hpp", "avatar_dds.cpp", "avatar_dds.hpp"):
        shutil.copy2(project / "native" / "title" / filename, src_niak / filename)
    for filename in ("lodepng.cpp", "lodepng.h"):
        shutil.copy2(project / "native" / "title" / "vendor" / filename, src_niak / filename)
    art_file = kit / "src/demo/catalog_art.cpp"
    replace_once(art_file, '#include "gfx/renderer.hpp"',
                 '#include "gfx/renderer.hpp"\n#include "niak/game_icons.hpp"\n#include "niak/case_art.hpp"')
    replace_once(art_file, '    for (Item &item : items_)\n    {\n        gfx::BackdropSpec spec;',
                 """    for (Item &item : items_)
    {
        // Prefer the true installed app icon from the local system catalogue.
        // If absent/forbidden/corrupt, generate the existing neutral placeholder.
        if (item.title_id[0]) {
            item.case_front = niak_load_case_art(renderer,item.title_id,"front");
            item.case_back = niak_load_case_art(renderer,item.title_id,"back");
            item.case_spine = niak_load_case_art(renderer,item.title_id,"spine");
            item.logo_art = niak_load_case_art(renderer,item.title_id,"logo");
            item.cover = niak_load_game_icon(renderer, item.title_id);
        }
        if (item.cover)
        {
            item.cover_is_image = true;
            ++index;
            continue;
        }
        gfx::BackdropSpec spec;""")
    replace_once(kit / "src/main.cpp", '#include "demo/catalog.hpp"',
                 '#include "demo/catalog.hpp"\n#include "niak/daily_backdrop.hpp"\n#include "niak/profile.hpp"')
    replace_once(kit / "src/main.cpp", '    demo::Catalog catalog;',
                 '    niak_load_daily_backdrops(renderer);\n    niak_profile_load_avatar(renderer);\n    demo::Catalog catalog;')
    replace_once(aurora, '#include "ui/glyphs.hpp"',
                 '#include "ui/glyphs.hpp"\n#include "niak/daily_backdrop.hpp"')
    # The PacBrew SQLite build references localtime_r, not exported by the
    # title's clean-room runtime. Provide the POSIX API locally; SQLite date
    # parsing is not used by our read-only catalogue queries.
    (src_niak / "localtime_compat.c").write_text(
        """/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <time.h>
#include <pthread.h>
static pthread_mutex_t niak_time_lock = PTHREAD_MUTEX_INITIALIZER;
struct tm *localtime_r(const time_t *stamp, struct tm *dest) {
    if (!stamp || !dest) return NULL;
    if (pthread_mutex_lock(&niak_time_lock) != 0) return NULL;
    struct tm *shared = localtime(stamp);
    if (shared) *dest = *shared;
    (void)pthread_mutex_unlock(&niak_time_lock);
    return shared ? dest : NULL;
}
""", encoding="utf-8")
    # PacBrew sqlite static archive + header are selected at build time.
    (kit / "src/demo/catalog.cpp").write_text(CATALOG_CPP, encoding="utf-8")

    # NiakTV typography: bake the original OFL Manrope and Instrument Serif
    # into SDF GPU atlases. Font conversion happens at build time on the host.
    # A PS5 title reads these through /app0/assets, not external /data assets.
    baker = kit / "build/host/niak_font_baker"
    baker.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["clang++", "-std=c++20", "-O2", "-w",
                    str(kit / "tools/font-baker/bake_font.cpp"), "-o", str(baker)],
                   check=True)
    font_dest = kit / "assets/fonts"
    for filename, out, pixels in (
            ("manrope.ttf", "niak-manrope.huifont", "56"),
            ("instrument-serif.ttf", "niak-instrument-serif.huifont", "56")):
        source = project / "native/assets" / filename
        if not source.is_file():
            raise SystemExit(f"Missing required NiakTV font {source}")
        subprocess.run([str(baker), str(source), str(font_dest / out),
                        pixels, "8", "2048", "european"], check=True)
    for filename in ("OFL-Manrope.txt", "OFL-InstrumentSerif.txt"):
        shutil.copy2(project / "fonts" / filename, font_dest / filename)

    # The production title is a NiakPS5 home app, not the original UI Lab demo.
    app_main = kit / "src/main.cpp"
    replace_once(app_main, '"inter-regular.huifont"', '"niak-manrope.huifont"')
    replace_once(app_main, '"inter-semibold.huifont"', '"niak-manrope.huifont"')
    replace_once(app_main, '"montserrat-medium.huifont"', '"niak-instrument-serif.huifont"')

    # Never report invented ratings, playtime, progress, or a fixed clock.
    replace_once(aurora, '#include <cstdio>', '#include <cstdio>\n#include <ctime>\n#include <cstring>')
    visual = aurora.read_text(encoding="utf-8")
    start = visual.find('        std::snprintf(text, sizeof(text), "%s  ')
    end = visual.find('        const Rect play{x, 540, 220, 64};', start)
    if start < 0 or end < 0:
        raise SystemExit("Upstream hero metadata changed; review necessary")
    visual = visual[:start] + """        // Only display information actually available from the installed-title scan.
        const char *id = it.title_id[0] ? it.title_id : "INDISPONIBLE";
        std::snprintf(text, sizeof(text), "%s  /  %s", it.genre, id);
        ui::text(list, fonts.regular, text, x, 366, 25, kWhite.with_alpha(0.8f));
        if (it.blurb && it.blurb[0])
            ui::paragraph(list, fonts.regular, it.blurb, x, 426, 25, 1020, 36,
                          kWhite.with_alpha(0.85f), 2);
        // An installed title needs no redundant detection banner.

""" + visual[end:]
    # The sheet stays open with a diagnostic instead of silently doing nothing.
    visual = visual.replace(
        '        // Actions: one highlight that springs between the rows.',
        '''        if (launch_error_[0])
            ui::text(list, fonts.semibold, launch_error_, sheet.x + 60,
                     sheet.y + sheet.h - 31, 20, Color::rgb(0xffb8a8));
        // Actions: one highlight that springs between the rows.''')
    # Two clearly labelled rows; never let an accented label pass through
    # the upstream ASCII-only upper() conversion.
    visual = visual.replace(
        '''            ui::text(list, fonts.semibold, shelf.title, kMargin, y - 62, 24,
                     kWhite.with_alpha(r == row_ ? 0.95f : 0.6f));''',
        '''            ui::text(list, fonts.semibold, shelf.title, kMargin, y - 62, 24,
                     kWhite.with_alpha(r == row_ ? 0.95f : 0.6f));
            ui::text(list, fonts.regular, r==0 ? "Jeux PS5 · Jeux homebrew" :
                "Applications PS5 · Applications homebrew", 450, y - 62, 18,
                kWhite.with_alpha(0.54f));''')
    # Detail-panel controller legends must stay WITHIN the frosted panel,
    # not spill past its right or bottom edge.
    visual = visual.replace(
        'ui::draw_hints(list, fonts, style, hints, 2, 1824, true);',
        'ui::draw_hints(list, fonts, style, hints, 2, 1720, true, '
        'ui::HintLayout{31.0f, 20.0f, 983.0f, 22.0f});',1)
    # The upstream detail sheet has three invented rating/playtime/player tiles.
    # NiakPS5 has none of these facts; show a verified title ID instead.
    sheet_start = visual.find('        // Three stat tiles; the first is a gauge drawn with arcs.')
    sheet_end = visual.find('        // Actions: one highlight that springs between the rows.', sheet_start)
    if sheet_start < 0 or sheet_end < 0:
        raise SystemExit("Upstream demo detail tiles changed; review required")
    facts = """        // Verified PS5 identifier only; no fictional scores or hours played.
        const Rect fact{x, sheet.y + 298, 700, 124};
        list.rounded_rect(fact, 24, kWhite.with_alpha(0.08f));
        ui::text(list, fonts.semibold, "IDENTIFIANT DU TITRE", fact.x + 24, fact.y + 38,
                 17, kWhite.with_alpha(0.55f));
        std::snprintf(text, sizeof(text), "%s",
                      it.title_id[0] ? it.title_id : "CATALOGUE INACCESSIBLE");
        ui::text(list, fonts.semibold, text, fact.x + 24, fact.y + 92, 34, kWhite);

"""
    visual = visual[:sheet_start] + facts + visual[sheet_end:]
    visual = visual.replace('const char *actions[kActions] = {it.progress > 0.0f ? "Resume" : "Play",',
                            'const char *actions[kActions] = {it.title_id[0] ? "Jouer" : "Indisponible",')
    visual = visual.replace('"Remove from favorites" : "Add to favorites"', 
                            '"Retirer des favoris" : "Ajouter aux favoris"')
    visual = visual.replace('                                         "Close"};', '                                         "Fermer"};')
    visual = visual.replace('"Choose"}, {ui::Button::circle, "Back"', 
                            '"Choisir"}, {ui::Button::circle, "Retour"')
    visual = visual.replace('"Details"},\n                                      {ui::Button::triangle, "Favorite"', 
                            '"Details"},\n                                      {ui::Button::triangle, "Favori"')
    visual = visual.replace('ui::text(list, fonts.semibold, "B", 1800, 91, 22,',
                            'ui::text(list, fonts.semibold, "N", 1800, 91, 22,')
    # Draw long titles inside the LEFT text column, never over the right-hand jacket.
    visual = visual.replace(
        'ui::text(list, fonts.display, it.title, x - 2, sheet.y + 156, 60, kWhite);',
        'ui::paragraph(list, fonts.semibold, it.title, x - 2, sheet.y + 130, '
        '43, 690, 49, kWhite, 2);')
    visual = visual.replace(
        'ui::paragraph(list, fonts.regular, it.blurb, x, sheet.y + 208, 25, 700, 36,'
        '\\n                      kWhite.with_alpha(0.82f), 2);',
        'if (it.blurb && it.blurb[0])\\n'
        '            ui::paragraph(list, fonts.regular, it.blurb, x, sheet.y + 221, '
        '22, 690, 31, kWhite.with_alpha(0.82f), 2);')
    # Avoid byte-wise ASCII uppercasing: it breaks accented French headings.
    visual = visual.replace('ui::upper(shelves_[static_cast<std::size_t>(row_)].title)',
                            'shelves_[static_cast<std::size_t>(row_)].title')
    visual = visual.replace('ui::upper(it.genre)', 'it.genre')
    visual = visual.replace('it.progress > 0.0f ? "Resume" : "Play"',
                            'it.title_id[0] ? "Jouer" : "Indisponible"')
    extra = visual.find('        const Rect more{x + 240, 540, 64, 64};')
    extra_end = visual.find('        list.pop_opacity();', extra)
    if extra < 0 or extra_end < 0:
        raise SystemExit("Upstream hero actions changed; review required")
    visual = visual[:extra] + visual[extra_end:]
    time_start = visual.find('        ui::text(list, fonts.regular, "21:47"')
    time_end = visual.find('        list.circle(1800, 82, 22,', time_start)
    if time_start < 0 or time_end < 0:
        raise SystemExit("Upstream top bar clock changed; review required")
    clock = """        // The console clock, not a hardcoded demo time.
        char clock_text[8] = "--:--";
        const std::time_t wall = std::time(nullptr);
        if (const std::tm *local = std::localtime(&wall))
            std::strftime(clock_text, sizeof(clock_text), "%H:%M", local);
        ui::text(list, fonts.regular, clock_text, 1760, 92, 26,
                 kWhite.with_alpha(0.8f), gfx::Align::right);
"""
    visual = visual[:time_start] + clock + visual[time_end:]
    if '"21:47"' in visual or 'std::snprintf(text, sizeof(text), "%.1f"' in visual:
        raise SystemExit("Fake clock or rating remains in Aurora")
    aurora.write_text(visual, encoding="utf-8")

    # Give the title a clear, stand-alone NiakPS5 identity instead of UI Lab.
    print(f"NiakPS5 title staged as {TITLE_ID}; one home design, real catalogue only")

CATALOG_CPP = r'''// SPDX-License-Identifier: GPL-3.0-or-later
// NiakPS5 read-only PS5 installed title catalogue (no invented installed games).
#include "demo/catalog.hpp"
#ifdef __cplusplus
extern "C" {
#endif
#include "niak/catalog.h"
#include "niak/shadowmount_api.h"
#ifdef __cplusplus
}
#endif
#include "platform/ps5/system.hpp"
#include "niak/title_meta.hpp"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <vector>

namespace hui::demo
{
Catalog::Catalog()
{
    std::vector<NiakGame> games(NIAKPS5_MAX_GAMES);
    const int db_count = niak_scan_games("/system_data/priv/mms/app.db", "",
                                         games.data(), games.size());
    std::size_t count = db_count > 0 ? static_cast<std::size_t>(db_count) : 0;
    // PS5 user title sandbox may deny app.db. Discover valid /data/homebrew
    // structures independently, even when app.db is missing or inaccessible.
    std::vector<NiakGame> api_games(NIAKPS5_MAX_GAMES);
    const int api_count = niak_scan_shadowmount(api_games.data(), api_games.size());
    if (api_count > 0)
    {
        for (int n = 0; n < api_count && count < games.size(); ++n)
        {
            const NiakGame &candidate = api_games[static_cast<std::size_t>(n)];
            std::size_t i=0;
            for (;i<count;++i)if(std::strcmp(games[i].id,candidate.id)==0)break;
            if (i==count)games[count++]=candidate;
            else if (candidate.title[0])std::snprintf(games[i].title,sizeof(games[i].title),
                        "%s",candidate.title);
        }
    }
    // A sandbox may deny app.db. Independently walk available installed
    // title folders, including user-installed PS5 streaming/media applications.
    std::vector<NiakGame> folders(NIAKPS5_MAX_GAMES);
    const int folder_count=niak_scan_installed_folders(
        "",folders.data(),folders.size());
    if(folder_count>0)
        for(int n=0;n<folder_count && count<games.size();++n) {
            const NiakGame &found=folders[static_cast<std::size_t>(n)];
            std::size_t i=0;
            for(;i<count;++i)if(std::strcmp(games[i].id,found.id)==0)break;
            if(i==count)games[count++]=found;
            else {
                if(found.application_category)
                    games[i].application_category=found.application_category;
                if(!games[i].installed_at[0])
                    std::snprintf(games[i].installed_at,sizeof(games[i].installed_at),
                                  "%s",found.installed_at);
            }
        }
    std::vector<NiakGame> homebrews(NIAKPS5_MAX_GAMES);
    const int home_count = niak_scan_homebrews("", homebrews.data(), homebrews.size());
    if (home_count > 0)
    {
        for (int n = 0; n < home_count && count < games.size(); ++n)
        {
            const NiakGame &candidate = homebrews[static_cast<std::size_t>(n)];
            bool already_seen = false;
            for (std::size_t i = 0; i < count; ++i)
                if (std::strcmp(games[i].id, candidate.id) == 0)
                    already_seen = true;
            if (!already_seen)
                games[count++] = candidate;
            else {
                // Preserve the explicit homebrew origin even when app.db
                // discovered the same title first.
                for (std::size_t i=0;i<count;++i)
                    if (std::strcmp(games[i].id,candidate.id)==0) {
                        games[i].is_homebrew=1;
                        games[i].discovered_from_homebrew=1;
                        break;
                    }
            }
        }
    }
    sys::log("[NiakPS5] catalog: db=%d, folders=%d, homebrew=%d, api=%d, unique=%zu",
             db_count, folder_count, home_count, api_count, count);
    if (count > 0)
    {
        for (std::size_t n = 0; n < count; ++n)
        {
            const NiakGame &game = games[n];
            NiakTitleMetadata meta;
            const bool known=niak_title_metadata(game.id,meta);
            const bool has_real_name=game.title[0] && std::strcmp(game.title,game.id)!=0;
            owned_titles_.emplace_back(has_real_name ? game.title : known ? meta.name : game.id);
            const std::string summary=known ? niak_title_summary(meta) : "";
            const std::string description=niak_title_overview(game.id);
            // Unknown metadata stays empty rather than showing invented prose.
            // Keep factual metadata visible even when LaunchBox also has a
            // full editorial overview; show verified facts FIRST.
            std::string detail=summary;
            if(!description.empty()) {
                if(!detail.empty())detail+=" — ";
                detail+=description;
            }
            if(detail.size()>900)detail.resize(900);
            owned_blurbs_.emplace_back(std::move(detail));
            Item item{};
            item.title = owned_titles_.back().c_str();
            item.studio = game.is_homebrew ? "Application" : "Jeu installé";
            item.genre = game.is_homebrew ? "Homebrew" :
                         (game.id[0]=='C' ? "PS4" : "PS5");
            // The current scanner has no trusted category for native titles.
            // Homebrew folders are initially classified as applications.
            if (game.application_category==1)item.application=false;
            else if(game.application_category==2)item.application=true;
            else if (known && meta.category=="Jeu")item.application=false;
            else if (known && meta.category=="Application")item.application=true;
            else if (std::strcmp(game.title,"Mes vidéos")==0 ||
                     std::strcmp(game.title,"My Videos")==0)
                item.application=true;
            else item.application=game.is_homebrew!=0;
            const char *last=game.last_access;
            const char *installed=game.installed_at;
            const char *recent=std::strcmp(last,installed)>=0?last:installed;
            std::snprintf(item.recently_used,sizeof(item.recently_used),"%s",recent);
            item.blurb = owned_blurbs_.back().c_str();
            item.homebrew = game.is_homebrew != 0;
            item.year = 0;
            item.rating = 0;
            item.progress = 0;
            item.hours = 0;
            item.players = 1;
            item.dark = gfx::Color::rgb(0x081719);
            item.mid = gfx::Color::rgb(0x183e44);
            item.accent = gfx::Color::rgb(0x91f5df);
            std::snprintf(item.title_id, sizeof(item.title_id), "%s", game.id);
            items_.push_back(item);
        }
    }
    else
    {
        // A truthful non-launchable placeholder, not a fictitious installed game.
        owned_titles_.emplace_back("Bibliothèque indisponible");
        Item item{};
        item.title = owned_titles_.back().c_str();
        item.studio = "NIAKPS5";
        item.genre = "VERIFICATION";
        item.blurb = db_count < 0 && home_count < 0
                ? "Accès refusé à app.db et /data/homebrew depuis cette application."
                : db_count < 0
                    ? "app.db inaccessible; aucun dossier homebrew valide et accessible."
                    : "Aucun titre installé accessible dans ce contexte.";
        item.year = 0;
        item.rating = 0;
        item.progress = 0;
        item.hours = 0;
        item.players = 1;
        item.dark = gfx::Color::rgb(0x081719);
        item.mid = gfx::Color::rgb(0x163039);
        item.accent = gfx::Color::rgb(0x91f5df);
        items_.push_back(item);
    }
}
} // namespace hui::demo
'''

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    prepare(args.kit.resolve(), args.project.resolve(), args.revision)
