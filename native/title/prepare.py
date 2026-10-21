#!/usr/bin/env python3
"""Prepare a dedicated NiakPS5 GPU-native title from pinned PS5_VKHomebrewUI.
Run ONLY on a fresh staging checkout; does not change system or console files.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

TITLE_ID = "PPSA99386"

def replace_once(path, old, new):
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one anchor in {path}: {old[:60]!r}; found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

def prepare(kit: Path, project: Path):
    registry = kit / "src/concepts/registry.cpp"
    reg = registry.read_text()
    begin = reg.index("    static constexpr ConceptFactory kFactories[] = {")
    end = reg.index("    };", begin) + len("    };")
    reg = reg[:begin] + "    static constexpr ConceptFactory kFactories[] = {concepts::make_aurora};" + reg[end:]
    registry.write_text(reg)

    aurora = kit / "src/concepts/aurora.cpp"
    replace_once(aurora, '#include "ui/motion.hpp"', '#include "ui/motion.hpp"\n#include "platform/ps5/system.hpp"')
    replace_once(aurora, 'namespace hui::concepts\n{', 'extern "C" int sceSystemServiceLaunchApp(const char *, const char **, void *);\n\nnamespace hui::concepts\n{')
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
    new = '''        // A single real-library shelf; never include the upstream demo catalogue.
        shelves_.resize(1);
        shelves_[0].title = "Bibliotheque PS5";
        for (int i = 0; i < static_cast<int>(items.size()); ++i)
            shelves_[0].items.push_back(i);'''
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
                    feedback.play(audio::Cue::error);
                }
                else
                {
                    const int rc = sceSystemServiceLaunchApp(selected.title_id, nullptr, nullptr);
                    sys::log("[NiakPS5] launch %.9s => 0x%08x", selected.title_id,
                             static_cast<unsigned>(rc));
                    feedback.play(rc == 0 ? audio::Cue::launch : audio::Cue::error);
                }
                sheet_open_ = false;
            }'''
    replace_once(aurora, old_launch, new_launch)
    # The single-design title does not display the UI Lab tour banner.
    shell = kit / "src/app/shell.cpp"
    replace_once(shell, '    banner_ = kBannerSeconds;\n}\n', '    banner_ = 0.0f;\n}\n')
    catalog_h = kit / "src/demo/catalog.hpp"
    replace_once(catalog_h, '#include <cstdint>', '#include <cstdint>\n#include <deque>\n#include <string>')
    replace_once(catalog_h, '    std::uint32_t cover = 0;', '    char title_id[16] = {};\n    std::uint32_t cover = 0;')
    replace_once(catalog_h, '    std::vector<Item> items_;',
                 '    std::deque<std::string> owned_titles_;\n    std::vector<Item> items_;')

    src_niak = kit / "src/niak"
    src_niak.mkdir(parents=True, exist_ok=True)
    for filename in ("catalog.c", "catalog.h", "shadowmount_api.c", "shadowmount_api.h"):
        shutil.copy2(project / "native" / filename, src_niak / filename)
    for filename in ("daily_backdrop.cpp", "daily_backdrop.hpp"):
        shutil.copy2(project / "native" / "title" / filename, src_niak / filename)
    replace_once(kit / "src/main.cpp", '#include "demo/catalog.hpp"',
                 '#include "demo/catalog.hpp"\n#include "niak/daily_backdrop.hpp"')
    replace_once(kit / "src/main.cpp", '    demo::Catalog catalog;',
                 '    niak_load_daily_backdrops(renderer);\n    demo::Catalog catalog;')
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
    replace_once(aurora, '#include <cstdio>', '#include <cstdio>\n#include <ctime>')
    visual = aurora.read_text(encoding="utf-8")
    start = visual.find('        std::snprintf(text, sizeof(text), "%s  ')
    end = visual.find('        const Rect play{x, 540, 220, 64};', start)
    if start < 0 or end < 0:
        raise SystemExit("Upstream hero metadata changed; review necessary")
    visual = visual[:start] + """        // Only display information actually available from the installed-title scan.
        const char *id = it.title_id[0] ? it.title_id : "INDISPONIBLE";
        std::snprintf(text, sizeof(text), "%s  /  %s", it.genre, id);
        ui::text(list, fonts.regular, text, x, 366, 25, kWhite.with_alpha(0.8f));
        ui::paragraph(list, fonts.regular, it.blurb, x, 432, 27, 820, 40,
                      kWhite.with_alpha(0.85f), 2);
        ui::text(list, fonts.regular,
                 it.title_id[0] ? "DETECTE SUR CETTE CONSOLE" : "ACCES AU CATALOGUE A VERIFIER",
                 x, 505, 20, it.accent);

""" + visual[end:]
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
                            '"Retirer favori (session)" : "Ajouter favori (session)"')
    visual = visual.replace('                                         "Close"};', '                                         "Fermer"};')
    visual = visual.replace('"Choose"}, {ui::Button::circle, "Back"', 
                            '"Choisir"}, {ui::Button::circle, "Retour"')
    visual = visual.replace('"Details"},\n                                      {ui::Button::triangle, "Favorite"', 
                            '"Details"},\n                                      {ui::Button::triangle, "Favori (session)"')
    visual = visual.replace('ui::text(list, fonts.semibold, "B", 1800, 91, 22,',
                            'ui::text(list, fonts.semibold, "N", 1800, 91, 22,')
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
        }
    }
    sys::log("[NiakPS5] read-only catalog: app.db=%d, homebrew folders=%d, api=%d, unique=%zu",
             db_count, home_count, api_count, count);
    if (count > 0)
    {
        for (std::size_t n = 0; n < count; ++n)
        {
            const NiakGame &game = games[n];
            owned_titles_.emplace_back(game.title);
            Item item{};
            item.title = owned_titles_.back().c_str();
            item.studio = game.discovered_from_homebrew == 2 ? "SHADOWMOUNT API" : game.discovered_from_homebrew ? "DECOUVERTE /DATA" : "INSTALLE";
            item.genre = game.discovered_from_homebrew == 2 ? "PS5 / PS4" : game.discovered_from_homebrew ? "HOMEBREW" : "PS5";
            item.blurb = game.discovered_from_homebrew == 2
                ? "Titre renvoye par l'API locale ShadowMountPlus. Lancement a verifier."
                : game.discovered_from_homebrew
                    ? "Dossier present dans /data/homebrew. Enregistrement non confirme."
                    : "Jeu detecte dans la base PS5. Lancement a verifier.";
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
        owned_titles_.emplace_back("Bibliotheque indisponible");
        Item item{};
        item.title = owned_titles_.back().c_str();
        item.studio = "NIAKPS5";
        item.genre = "VERIFICATION";
        item.blurb = db_count < 0 && home_count < 0
                ? "Acces refuse a app.db et /data/homebrew depuis cette application."
                : db_count < 0
                    ? "app.db inaccessible; aucun dossier homebrew valide et accessible."
                    : "Aucun titre installe accessible dans ce contexte.";
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
    args = parser.parse_args()
    prepare(args.kit.resolve(), args.project.resolve())
