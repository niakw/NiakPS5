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
    replace_once(aurora, '#include "niak/launch_bridge.hpp"',
                 '#include "niak/launch_bridge.hpp"\n#include "niak/case_auto_art.hpp"\n#include "niak/asset_stats.hpp"')
    replace_once(aurora,
        '        // ---- animation state ----',
        '''        // Only the focused GAME triggers remote LaunchBox artwork.
        // Set stream priority first to load cached media without network.
        const int index=focused_item();
        niak::case_media_stats.preferred_index=index;
        if(index!=last_art_selection_) {
            last_art_selection_=index;
            const demo::Item &selected=item(index);
            niak_select_case_art(selected.application?nullptr:selected.title_id);
        }
        // ---- animation state ----''')
    replace_once(aurora,'    int shown_ = 0;',
                 '    int last_art_selection_ = -1;\n    int shown_ = 0;')
    replace_once(aurora, '"Aurora Shelf",', '"NiakPS5",')
    replace_once(aurora, '"A console home screen: hero panel, cover shelves, frosted details",',
                 '"Votre console. Votre espace. Accueil natif NiakPS5.",')
    replace_once(aurora, '''        const char *tabs[] = {"Home", "Library", "Store", "Captures"};''',
                 '''        const char *tabs[] = {"NIAK", "Jeux", "Multimédia", "Réglages"};''')
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

    # The UI must rebuild its shelf indices after a late-arriving catalogue;
    # replacing the Catalog alone would leave Aurora's old placeholder index.
    shell_h = kit / "src/app/shell.hpp"
    replace_once(shell_h,
        '    void update(const InputFrame &input, float dt);',
        '    void update(const InputFrame &input, float dt);\n'
        '    void reload_catalog_views();')
    replace_once(shell, 'audio::SoundSet Shell::sound_set() const', '''void Shell::reload_catalog_views()
{
    // Destroy concepts BEFORE they can dereference old catalogue item strings.
    // Keep Settings, telemetry, audio and renderer ownership unchanged.
    concepts_.clear();
    for (ConceptFactory factory : concept_registry())
        concepts_.push_back(factory(context_));
    current_ = previous_ = 0;
    transition_.running = false;
    info_open_ = false;
    banner_ = 0.0f;
    if (!concepts_.empty())
        concepts_[0]->enter();
}

audio::SoundSet Shell::sound_set() const''')

    catalog_h = kit / "src/demo/catalog.hpp"
    replace_once(catalog_h, '#include <cstdint>', '#include <cstdint>\n#include <deque>\n#include <string>')
    replace_once(catalog_h, '    std::uint32_t cover = 0;',
                 '    float case_scene_aspect = 16.0f/9.0f;\n    float logo_art_aspect = 3.0f;\n    float poster_aspect = 0.72f;\n'
                 '    float case_hero_aspect = 16.0f/9.0f;\n'
                 '    float case_shot1_aspect = 16.0f/9.0f;\n'
                 '    float case_shot2_aspect = 16.0f/9.0f;\n'
                 '    char title_id[16] = {};\n    bool homebrew = false;\n    bool application = false;\n    char recently_used[48] = {};\n    bool cover_is_image = false;\n    std::uint32_t case_front = 0;\n    std::uint32_t case_back = 0;\n    std::uint32_t case_spine = 0;\n    std::uint32_t case_scene = 0;\n    std::uint32_t case_template_front = 0;\n    std::uint32_t case_template_back = 0;\n    std::uint32_t case_template_spine = 0;\n    std::uint32_t logo_art = 0;\n    std::uint32_t case_poster = 0;\n    std::uint32_t case_hero = 0;\n    std::uint32_t case_shot1 = 0;\n    std::uint32_t case_shot2 = 0;\n    std::uint32_t cover = 0;')
    replace_once(catalog_h, '    std::vector<Item> items_;',
                 '    std::deque<std::string> owned_titles_;\n    std::deque<std::string> owned_blurbs_;\n    niak::CoverStreamState cover_stream_;\n    int last_case_focus_ = -1;\n    int retained_case_focus_ = -1;\n    unsigned last_case_completed_ = 0;\n    std::array<unsigned,7> last_case_sides_{};\n    std::vector<Item> items_;')
    replace_once(catalog_h, '#include "gfx/draw_list.hpp"',
                 '#include "gfx/draw_list.hpp"\n#include "niak/cover_stream_state.hpp"')
    replace_once(catalog_h,
        '    bool build_covers(gfx::Renderer &renderer, const ui::Fonts &fonts);',
        '    bool build_covers(gfx::Renderer &renderer, const ui::Fonts &fonts);\n'
        '    bool refresh_if_unavailable(gfx::Renderer &renderer,\n'
        '                                const ui::Fonts &fonts);\n'
        '    bool stream_next_covers(gfx::Renderer &renderer, const ui::Fonts &fonts,\n'
        '                            std::size_t budget);\n'
        '    bool refresh_selected_case_art(gfx::Renderer &renderer);')
    replace_once(catalog_h, '  private:\n', '  private:\n    void reload();\n')

    src_niak = kit / "src/niak"
    src_niak.mkdir(parents=True, exist_ok=True)
    if not re.fullmatch(r"[0-9a-f]{7,12}",revision):
        raise ValueError("Invalid Git revision")
    (src_niak/"version.hpp").write_text(
        '#pragma once\nnamespace niak {inline constexpr const char *revision = "'
        + revision + '";}\n',encoding="utf8")
    for filename in ("catalog.c", "catalog.h", "shadowmount_api.c", "shadowmount_api.h", "shadowmount_http.h"):
        shutil.copy2(project / "native" / filename, src_niak / filename)
    # The native catalog also builds directly with -I native in host tests:
    # preserve its title/ subdirectory in the pinned PS5 source tree.
    catalog_headers=src_niak / "title"
    catalog_headers.mkdir(parents=True,exist_ok=True)
    for name in ("localized_name.h","title_category.h"):
        shutil.copy2(project / "native" / "title" / name,catalog_headers / name)
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
                     "case_auto_art.cpp","case_auto_art.hpp",
                     "launch_bridge.cpp","launch_bridge.hpp","socket_guard.h","loopback_connect.h","http_icon_response.hpp",
                     "icon_endpoint_policy.hpp","case_texture_scale.hpp","cover_stream_state.hpp","asset_stats.hpp",
                     "broker_catalog.cpp","broker_catalog.hpp","broker_snapshot.h","local_inventory.h",
                     "launch_log_status.h","case_fallback_layout.hpp","case_back_media.hpp",
                     "case_footer_alpha.hpp",
                     "app_classification.hpp","localized_name.h","title_category.h"):
        shutil.copy2(project / "native" / "title" / filename, src_niak / filename)
    for filename in ("profile.cpp", "profile.hpp", "avatar_dds.cpp", "avatar_dds.hpp"):
        shutil.copy2(project / "native" / "title" / filename, src_niak / filename)
    for filename in ("elevation.cpp", "elevation.hpp", "protocol.hpp",
                     "one_shot_install.cpp", "one_shot_install.hpp"):
        shutil.copy2(project / "native" / "title" / "elevation" / filename,
                     src_niak / filename)
    for filename in ("lodepng.cpp", "lodepng.h", "stb_image.h"):
        shutil.copy2(project / "native" / "title" / "vendor" / filename, src_niak / filename)
    # Host Mesa previews include src/niak but exclude src/platform.
    # The curl resolver/socket shim belongs ONLY to the actual PS5 build.
    platform_shim=kit / "src" / "platform" / "ps5"
    platform_shim.mkdir(parents=True,exist_ok=True)
    for filename in ("console_curl.c", "console_curl.h"):
        shutil.copy2(project / "native" / "title" / "vendor" / filename,
                     platform_shim / filename)
    art_file = kit / "src/demo/catalog_art.cpp"
    replace_once(art_file, 'void Catalog::release_covers(gfx::Renderer &renderer)\n{\n    for (Item &item : items_)',
                 '''void Catalog::release_covers(gfx::Renderer &renderer)
{
    // Six platform templates are SHARED by every title. Destroy only once.
    niak_release_case_templates(renderer);
    for (Item &item : items_)''')
    replace_once(art_file, '''        renderer.destroy_texture(item.cover);
        item.cover = 0;''',
                 '''        for(std::uint32_t *texture : {&item.case_front, &item.case_back,
                                      &item.case_spine, &item.case_scene,
                                      &item.logo_art,&item.case_poster,
                                      &item.case_hero,&item.case_shot1,
                                      &item.case_shot2}) {
            niak_destroy_case_texture(renderer,*texture);
        }
        if(item.cover)renderer.destroy_texture(item.cover);
        item.cover = 0;
        item.case_template_front=0;
        item.case_template_back=0;
        item.case_template_spine=0;''')
    replace_once(art_file, '#include "gfx/renderer.hpp"',
                 '#include "gfx/renderer.hpp"\n#include "niak/game_icons.hpp"\n#include "niak/case_art.hpp"\n#include "niak/case_auto_art.hpp"\n#include "niak/asset_stats.hpp"\n#include <algorithm>')
    replace_once(art_file, '    release_covers(renderer);\n    constexpr float kSize',
                 '    release_covers(renderer);\n    niak::case_media_stats={};\n    constexpr float kSize')
    replace_once(art_file, '    for (Item &item : items_)\n    {\n        gfx::BackdropSpec spec;',
                 """    for (Item &item : items_)
    {
        // Prefer the true installed app icon from the local system catalogue.
        // If absent/forbidden/corrupt, generate the existing neutral placeholder.
        if (item.title_id[0]) {
            if(item.application) {
                // Applications show native icons, never downloadable game art.
                item.cover=niak_load_game_icon(renderer,item.title_id);
                item.cover_is_image=item.cover!=0;
                ++niak::case_media_stats.titles;
                niak::case_media_stats.icons+=item.cover!=0;
            } else {
            // GPU-heavy retail case art belongs to the SELECTED game.
            // Streaming the remaining library decodes only its local icons.
            // Offline Mesa demo fixtures still exercise all physical faces.
#if defined(__PROSPERO__)
            if(index==niak::case_media_stats.preferred_index) {
#endif
            item.case_front = niak_load_case_art(renderer,item.title_id,"front");
            item.case_back = niak_load_case_art(renderer,item.title_id,"back");
            item.case_spine = niak_load_case_art(renderer,item.title_id,"spine");
            // Only used to reconstruct missing 3D sleeves, never library tiles.
            if(!item.case_front)
                item.case_scene = niak_load_game_background(
                    renderer,item.title_id,&item.case_scene_aspect);
            const char *platform=item.title_id[0]=='C'?"ps4":"ps5";
            // Only a MISSING individual face uses an invariant template.
            // Official front/back scans must never be overlaid or rebuilt.
            if(!item.case_front) {
                item.case_template_front=niak_load_case_template(
                    renderer,platform,"front");
                item.case_poster=niak_load_case_art(
                    renderer,item.title_id,"poster",&item.poster_aspect);
            }
            // Share one LaunchBox hero texture across both missing paper faces.
            if(!item.case_front || !item.case_back)
                item.case_hero=niak_load_case_art(
                    renderer,item.title_id,"hero",&item.case_hero_aspect);
            if(!item.case_back) {
                item.case_template_back=niak_load_case_template(
                    renderer,platform,"back");
                item.case_shot1=niak_load_case_art(
                    renderer,item.title_id,"shot1",&item.case_shot1_aspect);
                item.case_shot2=niak_load_case_art(
                    renderer,item.title_id,"shot2",&item.case_shot2_aspect);
            }
            if(!item.case_spine)
                item.case_template_spine=niak_load_case_template(
                    renderer,platform,"spine");
#if defined(__PROSPERO__)
            } // selected case only, never preload the full shelf.
#endif
            item.cover = niak_load_game_icon(renderer, item.title_id);
            auto &stats=niak::case_media_stats;
            ++stats.titles;
            stats.fronts+=item.case_front!=0;
            stats.backs+=item.case_back!=0;
            stats.spines+=item.case_spine!=0;
            stats.scenes+=item.case_scene!=0;
            stats.icons+=item.cover!=0;
            stats.templates+=item.case_template_front!=0 &&
                             item.case_template_back!=0 &&
                             item.case_template_spine!=0;
            } // game-only case media
        }
        if (item.cover)
        {
            item.cover_is_image = true;
            ++index;
            continue;
        }
        gfx::BackdropSpec spec;""")
    # Only the first, focused title is decoded before the first displayed
    # frame. Subsequent titles are streamed on the graphics thread in small
    # increments; native GL texture creation must never run on a CPU worker.
    replace_once(art_file,
        '    release_covers(renderer);\n    niak::case_media_stats={};\n    constexpr float kSize',
        '''    release_covers(renderer);
    niak::case_media_stats={};
    cover_stream_.reset(items_.size());
    last_case_focus_=-1;
    retained_case_focus_=-1;
    const auto case_status=niak_case_art_download_status();
    last_case_completed_=case_status.completed;
    last_case_sides_=case_status.sides_completed;
    niak::case_media_stats.total_titles=static_cast<unsigned>(
        std::count_if(items_.begin(),items_.end(),
            [](const Item &item){return item.title_id[0]!=0;}));
    return stream_next_covers(renderer,fonts,1);
}

bool Catalog::stream_next_covers(gfx::Renderer &renderer,
                                 const ui::Fonts &fonts,std::size_t budget)
{
    constexpr float kSize''')
    replace_once(art_file,
        '    int index = 0;\n    for (Item &item : items_)\n    {\n        // Prefer the true installed app icon',
        '''    budget=std::min(budget,cover_stream_.remaining());
    for(std::size_t step=0;step<budget;++step)
    {
        const int hint=niak::case_media_stats.preferred_index;
        const auto priority=hint>=0?static_cast<std::size_t>(hint):
                                    niak::CoverStreamState::invalid;
        const auto choice=cover_stream_.take(priority);
        if(choice==niak::CoverStreamState::invalid)break;
        Item &item=items_[choice];
        int index=static_cast<int>(choice);
        // Prefer the true installed app icon''')
    # Only the currently selected game gets newly downloaded case textures,
    # and those GPU uploads run on the renderer thread (not the HTTP worker).
    replace_once(art_file, '\n} // namespace hui::demo',
    """
bool Catalog::refresh_selected_case_art(gfx::Renderer &renderer)
{
    const int index=niak::case_media_stats.preferred_index;
    const auto case_status=niak_case_art_download_status();
    const unsigned completed=case_status.completed;
    if(index<0 || static_cast<std::size_t>(index)>=items_.size())return false;
    const bool same_focus=index==last_case_focus_;
    if(same_focus && completed==last_case_completed_)
        return false;
    if(index!=last_case_focus_) {
        // Keep only the current and immediate previous 3D case resident.
        // Previous focus survives one transition to avoid visual popping.
        const int retire=retained_case_focus_;
        if(retire>=0 && retire!=index && retire!=last_case_focus_ &&
           static_cast<std::size_t>(retire)<items_.size()) {
            Item &old=items_[static_cast<std::size_t>(retire)];
            for(std::uint32_t *texture : {&old.case_front,&old.case_back,
                 &old.case_spine,&old.case_scene,&old.logo_art,
                 &old.case_poster,&old.case_hero,&old.case_shot1,
                 &old.case_shot2})
                niak_destroy_case_texture(renderer,*texture);
            // Shared templates have their own lifecycle.
            old.case_template_front=0;
            old.case_template_back=0;
            old.case_template_spine=0;
        }
        retained_case_focus_=last_case_focus_;
    }
    last_case_focus_=index;
    last_case_completed_=completed;
    std::array<bool,7> updated{};
    for(std::size_t side=0;side<updated.size();++side)
        updated[side]=same_focus &&
            case_status.sides_completed[side]!=last_case_sides_[side];
    last_case_sides_=case_status.sides_completed;
    // Show CURRENT resident media, not historical texture creations.
    // Reconcile only on focus changes and completed CDN downloads.
    const auto recount_case_faces=[&] {
        auto &stats=niak::case_media_stats;
        stats.fronts=stats.backs=stats.spines=stats.scenes=stats.templates=0;
        for(const Item &entry:items_) {
            stats.fronts+=entry.case_front!=0;
            stats.backs+=entry.case_back!=0;
            stats.spines+=entry.case_spine!=0;
            stats.scenes+=entry.case_scene!=0;
            stats.templates+=entry.case_template_front!=0 &&
                entry.case_template_back!=0 &&
                entry.case_template_spine!=0;
        }
    };
    Item &selected=items_[static_cast<std::size_t>(index)];
    if(selected.application || !selected.title_id[0]) {
        recount_case_faces();
        return false;
    }
    bool changed=false;
    // Only invalidate faces belonging to the SAME title. The worker's
    // completion counters are global: switching games must never interpret
    // a previous game's download as a new change for this selected game.
    // Release only the affected face, not the whole 3D case.
    for(std::pair<bool,std::uint32_t*> updated_side : {
         std::pair<bool,std::uint32_t*>{updated[0],&selected.case_front},
         {updated[1],&selected.case_back},
         {updated[2],&selected.case_spine},
         {updated[3],&selected.logo_art},
         {updated[4],&selected.case_hero},
         {updated[5],&selected.case_shot1},
         {updated[6],&selected.case_shot2}})
        if(updated_side.first)
            niak_destroy_case_texture(renderer,*updated_side.second);
    const auto missing=[&](std::uint32_t &texture,const char *side,
                           float *aspect=nullptr) {
        if(texture)return;
        texture=niak_load_case_art(renderer,selected.title_id,side,aspect);
        changed |= texture!=0;
    };
    missing(selected.case_front,"front");
    missing(selected.case_back,"back");
    missing(selected.case_spine,"spine");
    const char *platform=selected.title_id[0]=='C'?"ps4":"ps5";
    if(!selected.case_front) {
        if(!selected.case_template_front)
            selected.case_template_front=niak_load_case_template(
                renderer,platform,"front");
        if(!selected.case_scene)
            selected.case_scene=niak_load_game_background(
                renderer,selected.title_id,&selected.case_scene_aspect);
        missing(selected.case_poster,"poster",&selected.poster_aspect);
    }
    // Fanart can fill a missing FRONT when no local pic1 is available.
    // Keep one GPU upload even when both faces must be reconstructed.
    if(!selected.case_front || !selected.case_back)
        missing(selected.case_hero,"hero",&selected.case_hero_aspect);
    if(!selected.case_back) {
        if(!selected.case_template_back)
            selected.case_template_back=niak_load_case_template(
                renderer,platform,"back");
        missing(selected.case_shot1,"shot1",&selected.case_shot1_aspect);
        missing(selected.case_shot2,"shot2",&selected.case_shot2_aspect);
    }
    if(!selected.case_spine && !selected.case_template_spine)
        selected.case_template_spine=niak_load_case_template(
            renderer,platform,"spine");
    // A newly arrived official retail scan replaces ONLY its face.
    // Free fallback media no longer drawn for that face, but keep the
    // installed background while a missing FRONT still needs it.
    if(selected.case_front) {
        niak_destroy_case_texture(renderer,selected.logo_art);
        niak_destroy_case_texture(renderer,selected.case_poster);
        selected.case_template_front=0; // shared template stays resident
    }
    if(selected.case_back) {
        // A missing FRONT may still display this shared fanart background.
        if(selected.case_front)
            niak_destroy_case_texture(renderer,selected.case_hero);
        niak_destroy_case_texture(renderer,selected.case_shot1);
        niak_destroy_case_texture(renderer,selected.case_shot2);
        selected.case_template_back=0;
    }
    if(selected.case_spine)
        selected.case_template_spine=0;
    if(selected.case_front)
        niak_destroy_case_texture(renderer,selected.case_scene);
    recount_case_faces();
    return changed;
}
} // namespace hui::demo""")

    # Defer streaming when the user is holding a direction or pressing an
    # action, to avoid a blocking filesystem lookup during navigation.
    # GPU texture creation remains on the renderer's owning thread.
    replace_once(kit / "src/main.cpp",
        '        shell.update(input, dt);',
        '''        shell.update(input, dt);
        // Load the new focused title on the FIRST idle frame; during rapid
        // navigation do not decode/upload textures at every button repeat.
        const bool navigation_idle=frames>0 &&
            input.nav==Direction::none && input.pressed==0 &&
            input.held==0 && !input.focus_lost;
        static int prepared_focus=-1;
        const int focus=niak::case_media_stats.preferred_index;
        const bool first_idle_focus=navigation_idle && focus!=prepared_focus;
        if(navigation_idle && (frames%4u==0 || first_idle_focus))
            (void)catalog.stream_next_covers(renderer,fonts,1);
        if(frames>0 && frames%600u==0 && input.nav==Direction::none &&
            input.pressed==0 && input.held==0 && !input.focus_lost)
            niak_profile_refresh_avatar(renderer);
        if(navigation_idle && (frames%12u==0 || first_idle_focus))
            (void)catalog.refresh_selected_case_art(renderer);
        if(first_idle_focus)prepared_focus=focus;
        // PLDmgr or title-mount services may start AFTER Catalog construction.
        // Poll at most once per ~600 frames while the UI is idle. Rebuild both
        // catalogue art and Aurora shelves on this same renderer thread; no
        // app restart, unsafe borrowed pointers or per-frame socket traffic.
        if(!tour && frames>0 && frames%600u==0 &&
           input.nav==Direction::none && input.pressed==0 &&
           input.held==0 && !input.focus_lost &&
           catalog.refresh_if_unavailable(renderer,fonts)) {
            shell.reload_catalog_views();
            sys::log("[NiakPS5] late broker catalogue recovered: %zu titles",
                     catalog.size());
        }''')
    # A single failed procedural GPU upload must not leave the progressive
    # loader retrying the same title forever on every subsequent idle frame.
    replace_once(art_file,
        '        if (item.cover == 0)\n            return false;',
        '''        if (item.cover == 0) {
            // Already marked attempted: avoid an endless retry loop.
            return false;
        }''')
    replace_once(kit / "src/main.cpp", '#include "demo/catalog.hpp"',
                 '#include "demo/catalog.hpp"\n#include "niak/daily_backdrop.hpp"\n#include "niak/profile.hpp"\n#include "niak/one_shot_install.hpp"\n#include "niak/asset_stats.hpp"')
    replace_once(kit / "src/main.cpp",
        '    sys::log("[HUI] entry");',
        '    sys::log("[HUI] entry");\n'
        '    const int payload_install = niak::bootstrap_own_payload();\n'
        '    niak::payload_install_status = payload_install;\n'
        '    sys::log("[NiakPS5] one-shot own payload install status=%d", payload_install);')
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
#include "niak/app_classification.hpp"
#include "niak/broker_catalog.hpp"
#include "niak/broker_snapshot.h"
#include "niak/local_inventory.h"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <vector>

namespace hui::demo
{
Catalog::Catalog()
{
    reload();
}

bool Catalog::refresh_if_unavailable(gfx::Renderer &renderer,
                                     const ui::Fonts &fonts)
{
    // Only a synthetic placeholder can be refreshed here. Existing shelves
    // and real installed game identities must never be replaced mid-session.
    if(items_.size()!=1 || items_[0].title_id[0]!=0)return false;
    NiakGame probe{};
    // The PLDmgr socket may be blocked by the title sandbox even when
    // ShadowMount or an installed game directory becomes readable later.
    // Do not permanently require the broker as the ONLY recovery gate.
    const bool available=
        niak_scan_broker_games(&probe,1)>0 ||
        niak_scan_installed_folders("",&probe,1)>0 ||
        niak_scan_homebrews("",&probe,1)>0 ||
        niak_scan_shadowmount(&probe,1)>0 ||
        niak_scan_games("/system_data/priv/mms/app.db","",&probe,1)>0;
    if(!available)return false;
    release_covers(renderer);
    items_.clear();
    owned_titles_.clear();
    owned_blurbs_.clear();
    reload();
    (void)build_covers(renderer,fonts);
    return !items_.empty() && items_[0].title_id[0]!=0;
    // Only signal a view rebuild when real game identities were restored.
}

void Catalog::reload()
{
    std::vector<NiakGame> games(NIAKPS5_MAX_GAMES);
    const int db_count = niak_scan_games("/system_data/priv/mms/app.db", "",
                                         games.data(), games.size());
    std::size_t count = db_count > 0 ? static_cast<std::size_t>(db_count) : 0;
    // Same privileged ELF already hosts the strictly-local launch broker.
    // It can enumerate fixed installed game roots without elevating the GUI.
    std::vector<NiakGame> broker_games(NIAKPS5_MAX_GAMES);
    const int broker_count=niak_scan_broker_games(broker_games.data(),broker_games.size());
    if(broker_count>0)
        for(int n=0;n<broker_count && count<games.size();++n) {
            const NiakGame &candidate=broker_games[static_cast<std::size_t>(n)];
            std::size_t i=0;
            for(;i<count;++i)if(std::strcmp(games[i].id,candidate.id)==0)break;
            if(i==count)games[count++]=candidate;
        }
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
                // Use localized installed manifest titles across the entire
                // shelf, rather than retaining English app.db names.
                if(found.title[0] && std::strcmp(found.title,found.id)!=0)
                    std::snprintf(games[i].title,sizeof(games[i].title),
                                  "%s",found.title);
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
                        if(candidate.title[0] &&
                           std::strcmp(candidate.title,candidate.id)!=0)
                            std::snprintf(games[i].title,sizeof(games[i].title),
                                          "%s",candidate.title);
                        break;
                    }
            }
        }
    }
    // The PLDmgr broker sees param.json where the sandbox sees only IDs.
    // Read the second, equally fresh/validated subset: category is applied
    // ONLY to titles already in the live merged inventory, never promoted
    // from an old standalone record.
    std::vector<NiakGame> verified_apps(NIAKPS5_MAX_GAMES);
    int verified_count=niak_snapshot_read(NIAK_APPS_SNAPSHOT_APP_FILE,
                                          verified_apps.data(),verified_apps.size());
    if(verified_count<0)
        verified_count=niak_snapshot_read(NIAK_APPS_SNAPSHOT_APP_SOURCE,
                                          verified_apps.data(),verified_apps.size());
    if(verified_count<0)
        verified_count=niak_snapshot_read(NIAK_APPS_SNAPSHOT_FILE,
                                          verified_apps.data(),verified_apps.size());
    if(verified_count>0) {
        for(int j=0;j<verified_count;++j)
            for(std::size_t i=0;i<count;++i)
                if(std::strcmp(games[i].id,
                               verified_apps[static_cast<std::size_t>(j)].id)==0) {
                    games[i].application_category=2;
                    break;
                }
    }
    sys::log("[NiakPS5] verified apps: %d; inventory=%zu",
             verified_count,count);
    // Local FTP metadata enriches ONLY live IDs: never resurrect stale apps.
    std::vector<NiakGame> observed(games.size());
    int cached_count=niak_scan_local_inventory(
        "/app0/assets/niak-local-titles.tsv",observed.data(),observed.size());
    if(cached_count<0)
        cached_count=niak_scan_local_inventory(
            "/data/homebrew/PPSA99386/assets/niak-local-titles.tsv",
            observed.data(),observed.size());
    if(count>0 && cached_count>0) {
        for(int j=0;j<cached_count;++j) {
            const auto &record=observed[static_cast<std::size_t>(j)];
            for(std::size_t i=0;i<count;++i)
                if(std::strcmp(games[i].id,record.id)==0) {
                    // Fresh, broker-verified applications cannot be
                    // downgraded by a historical FTP "Jeu" label.
                    if(record.application_category &&
                       games[i].application_category!=2)
                        games[i].application_category=record.application_category;
                    // The FTP overlay is sourced from THIS installed ID's
                    // signed/validated param.json. Its fr-FR title overrides
                    // app.db's generic English titleName where available.
                    if(record.title[0])
                        std::snprintf(games[i].title,sizeof(games[i].title),
                                      "%s",record.title);
                    break;
                }
        }
    } else if(count==0 && cached_count>0) {
        // Last-known FTP list is fallback only, not a live inventory.
        for(int j=0;j<cached_count && count<games.size();++j)
            games[count++]=observed[static_cast<std::size_t>(j)];
    }
    sys::log("[NiakPS5] cached FTP fallback: %d titles (historical snapshot)",
             cached_count);
    sys::log("[NiakPS5] catalog: db=%d, broker=%d, folders=%d, homebrew=%d, api=%d, unique=%zu",
             db_count, broker_count, folder_count, home_count, api_count, count);
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
            if(game.discovered_from_homebrew==3)
                detail="Dernier inventaire FTP : présence actuelle non vérifiée.";
            if(!description.empty()) {
                if(!detail.empty())detail+=" — ";
                detail+=description;
            }
            if(detail.size()>900)detail.resize(900);
            owned_blurbs_.emplace_back(std::move(detail));
            Item item{};
            item.title = owned_titles_.back().c_str();
            // A homebrew is an installation origin, not a media category.
            // Use the verified title category below for visible labels.
            item.genre = game.id[0]=='C' ? "PS4" : "PS5";
            // The current scanner has no trusted category for native titles.
            // Homebrew folders are initially classified as applications.
            // The verified category wins over the installation origin.
            // Previously, the unconditional trailing "else" overwrote this
            // classification for virtually every game/media application.
            item.application=niak_application_category(
                game.id,owned_titles_.back().c_str(),game.application_category,
                game.is_homebrew,known && meta.category=="Application",
                known && meta.category=="Jeu");
            item.studio=game.discovered_from_homebrew==3
                ? "Dernier inventaire local" :
                item.application ? "Application installée" : "Jeu installé";
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
        // The catalog can be empty for three fundamentally different
        // reasons; avoid blaming app.db when PLDmgr DID answer successfully.
        item.blurb = broker_count==0
            ? "Inventaire local disponible, mais aucun titre valide n'est visible. Vérifier les droits et les chemins des jeux."
            : broker_count>0
                ? "Titres renvoyés par PLDmgr, mais aucun titre valide n'a été intégré. Consulter le journal NiakPS5."
            : db_count<0 && folder_count<0 && home_count<0 && api_count<0
                ? "Toutes les sources du catalogue sont inaccessibles. Vérifier que niakps5.elf est exécuté par PLDmgr."
            : db_count<0
                ? "app.db inaccessible et aucune autre source n'a fourni de titre valide."
                : "Aucun titre installé valide détecté par les sources accessibles.";
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
    // The first streamed cover must match the first focused game shelf
    // (most recently played or installed), not an arbitrary SQLite row.
    // Item pointers refer to stable string storage in owned_* deques.
    std::stable_sort(items_.begin(),items_.end(),
        [](const Item &a,const Item &b) {
            if(a.application!=b.application)return !a.application;
            const int recent=std::strcmp(a.recently_used,b.recently_used);
            if(recent!=0)return recent>0;
            return std::strcmp(a.title,b.title)<0;
        });
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
