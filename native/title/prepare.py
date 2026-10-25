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
                 '#include "niak/launch_bridge.hpp"\n#include "niak/case_auto_art.hpp"\n#include "niak/case_art.hpp"\n#include "niak/game_icons.hpp"\n#include "niak/asset_stats.hpp"')
    replace_once(aurora,
        '        // ---- animation state ----',
        '''        // Only the focused GAME triggers remote LaunchBox artwork.
        // Set stream priority first to load cached media without network.
        const int index=focused_item();
        niak::case_media_stats.preferred_index=index;
        // The numeric shelf index is NOT a stable title identity: a late
        // broker catalogue rebuild can replace the game at the same slot.
        // Compare title IDs, not indices, so CDN tasks track the actual
        // foreground game and an unchanged game does not restart downloads.
        const demo::Item &selected=item(index);
        const char *art_id=(selected.application || !selected.title_id[0])?
            "" : selected.title_id;
        if(std::strcmp(last_art_title_,art_id)!=0) {
            std::snprintf(last_art_title_,sizeof(last_art_title_),"%s",art_id);
            // Cancel old CPU scan work immediately on focus change,
            // including while the user is still holding navigation.
            niak_select_prepared_case_focus(art_id[0]?art_id:nullptr);
            niak_select_game_background_focus(art_id[0]?art_id:nullptr);
            niak_select_case_art(art_id[0]?art_id:nullptr);
        }
        // ---- animation state ----''')
    replace_once(aurora,'    int shown_ = 0;',
                 '    char last_art_title_[16] = {};\n    int shown_ = 0;')
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
                 '    char title_id[16] = {};\n    bool homebrew = false;\n    bool application = false;\n    char recently_used[48] = {};\n    bool cover_is_image = false;\n    unsigned case_reload_mask = 0;\n    std::uint32_t case_front = 0;\n    std::uint32_t case_back = 0;\n    std::uint32_t case_spine = 0;\n    std::uint32_t case_scene = 0;\n    std::uint32_t case_template_front = 0;\n    std::uint32_t case_template_back = 0;\n    std::uint32_t case_template_spine = 0;\n    std::uint32_t logo_art = 0;\n    std::uint32_t case_poster = 0;\n    std::uint32_t case_hero = 0;\n    std::uint32_t case_shot1 = 0;\n    std::uint32_t case_shot2 = 0;\n    std::uint32_t cover = 0;')
    replace_once(catalog_h, '    std::vector<Item> items_;',
                 '    std::deque<std::string> owned_titles_;\n    std::deque<std::string> owned_blurbs_;\n    niak::CoverStreamState cover_stream_;\n    std::size_t icon_retry_cursor_ = 0;\n    unsigned case_hydration_step_ = 0;\n    int last_case_focus_ = -1;\n    int retained_case_focus_ = -1;\n    unsigned last_case_completed_ = 0;\n    std::array<unsigned,7> last_case_sides_{};\n    std::deque<std::uint32_t> retiring_case_textures_;\n    std::vector<Item> items_;')
    replace_once(catalog_h, '#include "gfx/draw_list.hpp"',
                 '#include "gfx/draw_list.hpp"\n#include "niak/cover_stream_state.hpp"')
    replace_once(catalog_h,
        '    bool build_covers(gfx::Renderer &renderer, const ui::Fonts &fonts);',
        '    bool build_covers(gfx::Renderer &renderer, const ui::Fonts &fonts);\n'
        '    bool refresh_if_unavailable(gfx::Renderer &renderer,\n'
        '                                const ui::Fonts &fonts);\n'
        '    bool stream_next_covers(gfx::Renderer &renderer, const ui::Fonts &fonts,\n'
        '                            std::size_t budget);\n'
        '    bool has_pending_covers() const {return cover_stream_.remaining()!=0;}\n'
        '    bool refresh_selected_case_art(gfx::Renderer &renderer);\n'
        '    bool refresh_pending_game_icons(gfx::Renderer &renderer);\n'
        '    bool refresh_pending_case_background(gfx::Renderer &renderer);\n'
        '    bool refresh_pending_case_art(gfx::Renderer &renderer);\n'
        '    bool refresh_pending_case_templates(gfx::Renderer &renderer);\n'
        '    bool release_one_retired_case_texture(gfx::Renderer &renderer);\n'
        '    void retry_missing_game_icons();')
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
                     "broker_catalog.cpp","broker_catalog.hpp","broker_snapshot.h","local_inventory.h","local_inventory_merge.hpp",
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
    // A catalogue rebuild flushes detached handles before discarding Items.
    while(!retiring_case_textures_.empty()) {
        auto texture=retiring_case_textures_.front();
        retiring_case_textures_.pop_front();
        niak_destroy_case_texture(renderer,texture);
    }
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
        item.case_template_spine=0;\n        item.case_reload_mask=0;''')
    replace_once(art_file, '#include "gfx/renderer.hpp"',
                 '#include "gfx/renderer.hpp"\n#include "niak/game_icons.hpp"\n#include "niak/case_art.hpp"\n#include "niak/case_auto_art.hpp"\n#include "niak/asset_stats.hpp"\n#include <algorithm>\n#include <cstring>')
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
            // Stream icons only on PS5. The selected game gets its case
            // textures through bounded idle-time hydration below. Host QA
            // keeps eager fixture loading to check the complete 3D sleeve.
#if !defined(__PROSPERO__)
            // On the host, render BOTH fixture games and all six real pieces.
            // Do not depend on the console's selected-index streaming hint.
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
#endif // Host fixtures are eager; PS5 case textures hydrate while idle.
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
    icon_retry_cursor_=0;
    case_hydration_step_=0;
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
// Enqueue at most two missing title IDs per ~600 idle frames. Never repeat
// local file decoding just to retry a temporarily unavailable HTTP endpoint.
// Focus gets priority; one round-robin entry also recovers the rest of the
// library when the local service starts after NiakPS5.
void Catalog::retry_missing_game_icons() {
#if defined(__PROSPERO__)
    const int focused=niak::case_media_stats.preferred_index;
    if(focused>=0 && static_cast<std::size_t>(focused)<items_.size()) {
        const Item &item=items_[static_cast<std::size_t>(focused)];
        if(item.title_id[0] && !item.cover_is_image)
            niak_request_missing_game_icon(item.title_id);
    }
    if(items_.empty())return;
    for(std::size_t n=0;n<items_.size();++n) {
        const auto index=(icon_retry_cursor_+n)%items_.size();
        const Item &item=items_[index];
        if(!item.title_id[0] || item.cover_is_image)continue;
        niak_request_missing_game_icon(item.title_id);
        icon_retry_cursor_=(index+1)%items_.size();
        break;
    }
#endif
}

// The single HTTP worker never holds a GPU texture or Item pointer. Consume
// one response after navigation settles, replacing a generated tile in place.
bool Catalog::refresh_pending_game_icons(gfx::Renderer &renderer) {
    char id[16]{};
    const auto accept=[](const char *prepared,void *opaque)->bool {
        auto &catalog=*static_cast<Catalog *>(opaque);
        const auto match=std::find_if(
            catalog.items_.begin(),catalog.items_.end(),
            [&](const Item &item) {
                return item.title_id[0] &&
                    std::strcmp(item.title_id,prepared)==0;
            });
        return match!=catalog.items_.end() && !match->cover_is_image;
    };
    const auto handle=niak_take_downloaded_game_icon(
        renderer,id,accept,this);
    if(!handle)return false;
    const auto it=std::find_if(items_.begin(),items_.end(),
        [&](const Item &item) {
            return item.title_id[0] && std::strcmp(item.title_id,id)==0;
        });
    if(it==items_.end() || it->cover_is_image) {
        renderer.destroy_texture(handle);
        return false;
    }
    if(it->cover)renderer.destroy_texture(it->cover);
    it->cover=handle;
    it->cover_is_image=true;
    ++niak::case_media_stats.icons;
    return true;
}

// One local CPU-decoded pic1 texture may arrive after a selection change.
// Only the current game without an official front may own that GPU handle.
// Deferred GPU-owned textures are no longer referenced by their old Items.
bool Catalog::release_one_retired_case_texture(gfx::Renderer &renderer) {
    if(retiring_case_textures_.empty())return false;
    auto texture=retiring_case_textures_.front();
    retiring_case_textures_.pop_front();
    niak_destroy_case_texture(renderer,texture);
    return true;
}

bool Catalog::refresh_pending_case_background(gfx::Renderer &renderer) {
    char title_id[16]{};
    float aspect=16.0f/9.0f;
    const int focus=niak::case_media_stats.preferred_index;
    const bool focused=focus>=0 &&
        static_cast<std::size_t>(focus)<items_.size();
    const Item *selected=focused?
        &items_[static_cast<std::size_t>(focus)]:nullptr;
    const char *expected=selected && !selected->application &&
        !selected->case_front && !selected->case_scene?
        selected->title_id:nullptr;
    auto texture=niak_take_downloaded_game_background(
        renderer,title_id,&aspect,expected);
    if(!texture)return false;
    if(focus<0 || static_cast<std::size_t>(focus)>=items_.size()) {
        niak_destroy_case_texture(renderer,texture);
        return false;
    }
    Item &item=items_[static_cast<std::size_t>(focus)];
    if(std::strcmp(item.title_id,title_id)!=0 || item.application ||
       item.case_front || item.case_scene) {
        niak_destroy_case_texture(renderer,texture);
        return false;
    }
    item.case_scene=texture;
    item.case_scene_aspect=aspect;
    ++niak::case_media_stats.scenes;
    return true;
}

// The worker returns only already scaled pixels. Refuse obsolete titles
// BEFORE allocating their textures, then bind one approved scan per idle frame.
// Shared PS4/PS5 mastheads, back strips and spines become available after
// their worker decode. Attach only to missing faces of the selected game;
// originals always supersede the template. No decoding occurs here.
bool Catalog::refresh_pending_case_templates(gfx::Renderer &renderer) {
    bool changed=niak_upload_one_prepared_case_template(renderer);
    const int focus=niak::case_media_stats.preferred_index;
    if(focus<0 || static_cast<std::size_t>(focus)>=items_.size())return changed;
    Item &item=items_[static_cast<std::size_t>(focus)];
    if(!item.title_id[0] || item.application)return changed;
    const char *platform=item.title_id[0]=='C'?"ps4":"ps5";
    const auto attach=[&](std::uint32_t &target,std::uint32_t original,
                          const char *side) {
        if(original || target)return;
        const auto loaded=niak_get_ready_case_template(platform,side);
        if(loaded){target=loaded;changed=true;}
    };
    attach(item.case_template_front,item.case_front,"front");
    attach(item.case_template_back,item.case_back,"back");
    attach(item.case_template_spine,item.case_spine,"spine");
    return changed;
}

bool Catalog::refresh_pending_case_art(gfx::Renderer &renderer) {
    const int focus=niak::case_media_stats.preferred_index;
    if(focus<0 || static_cast<std::size_t>(focus)>=items_.size())return false;
    Item &selected=items_[static_cast<std::size_t>(focus)];
    if(!selected.title_id[0] || selected.application)return false;
    // The worker's decoded RGBA result may be obsolete by the time we poll:
    // check official faces, fallback visibility, and pending CDN refreshes
    // BEFORE allocating a GPU texture. The worker slot is consumed even
    // when the catalogue no longer needs this specific side.
    const auto accept=[](const char *side,void *context)->bool {
        const Item &item=*static_cast<const Item *>(context);
        if(std::strcmp(side,"front")==0)
            return !item.case_front || (item.case_reload_mask & (1u<<0));
        if(std::strcmp(side,"back")==0)
            return !item.case_back || (item.case_reload_mask & (1u<<1));
        if(std::strcmp(side,"spine")==0)
            return !item.case_spine || (item.case_reload_mask & (1u<<2));
        if(std::strcmp(side,"logo")==0)
            return !item.case_front && !item.logo_art;
        if(std::strcmp(side,"poster")==0)
            return !item.case_front && !item.case_poster;
        if(std::strcmp(side,"hero")==0)
            return (!item.case_front || !item.case_back) &&
                (!item.case_hero || (item.case_reload_mask & (1u<<4)));
        if(std::strcmp(side,"shot1")==0)
            return !item.case_back &&
                (!item.case_shot1 || (item.case_reload_mask & (1u<<5)));
        if(std::strcmp(side,"shot2")==0)
            return !item.case_back &&
                (!item.case_shot2 || (item.case_reload_mask & (1u<<6)));
        return false;
    };
    char side[16]{};
    float aspect=1.0f;
    auto handle=niak_take_prepared_case_art(
        renderer,selected.title_id,side,&aspect,accept,&selected);
    if(!handle)return false;
    std::uint32_t *destination=nullptr;
    float *destination_aspect=nullptr;
    if(std::strcmp(side,"front")==0)destination=&selected.case_front;
    else if(std::strcmp(side,"back")==0)destination=&selected.case_back;
    else if(std::strcmp(side,"spine")==0)destination=&selected.case_spine;
    else if(std::strcmp(side,"logo")==0) {
        destination=&selected.logo_art;
        destination_aspect=&selected.logo_art_aspect;
    } else if(std::strcmp(side,"poster")==0) {
        destination=&selected.case_poster;
        destination_aspect=&selected.poster_aspect;
    } else if(std::strcmp(side,"hero")==0) {
        destination=&selected.case_hero;
        destination_aspect=&selected.case_hero_aspect;
    } else if(std::strcmp(side,"shot1")==0) {
        destination=&selected.case_shot1;
        destination_aspect=&selected.case_shot1_aspect;
    } else if(std::strcmp(side,"shot2")==0) {
        destination=&selected.case_shot2;
        destination_aspect=&selected.case_shot2_aspect;
    }
    const bool redundant=(selected.case_front &&
        (std::strcmp(side,"logo")==0 || std::strcmp(side,"poster")==0)) ||
        (selected.case_back &&
        (std::strcmp(side,"shot1")==0 || std::strcmp(side,"shot2")==0 ||
         (std::strcmp(side,"hero")==0 && selected.case_front)));
    // A CDN replacement is allowed to supersede a resident official face.
    // The OLD texture remains visible throughout disk read and worker decode;
    // destroy it only when the new GPU texture has already been allocated.
    unsigned side_index=7u;
    for(const auto &entry : {
        std::pair<const char *,unsigned>{"front",0u},
        {"back",1u},{"spine",2u},{"hero",4u},
        {"shot1",5u},{"shot2",6u}}) {
        if(std::strcmp(side,entry.first)==0) {
            side_index=entry.second;
            break;
        }
    }
    const unsigned bit=side_index<7u?(1u<<side_index):0u;
    const bool refreshing=bit && (selected.case_reload_mask & bit);
    if(!destination || redundant || (*destination && !refreshing)) {
        niak_destroy_case_texture(renderer,handle);
        return false;
    }
    if(*destination)niak_destroy_case_texture(renderer,*destination);
    *destination=handle;
    selected.case_reload_mask&=~bit;
    if(destination_aspect)*destination_aspect=aspect;
    if(selected.case_front) {
        niak_destroy_case_texture(renderer,selected.logo_art);
        niak_destroy_case_texture(renderer,selected.case_poster);
        niak_destroy_case_texture(renderer,selected.case_scene);
        selected.case_template_front=0;
    }
    if(selected.case_back) {
        if(selected.case_front)
            niak_destroy_case_texture(renderer,selected.case_hero);
        niak_destroy_case_texture(renderer,selected.case_shot1);
        niak_destroy_case_texture(renderer,selected.case_shot2);
        selected.case_template_back=0;
    }
    if(selected.case_spine)selected.case_template_spine=0;
    auto &stats=niak::case_media_stats;
    stats.fronts=stats.backs=stats.spines=stats.scenes=stats.templates=0;
    for(const Item &item:items_) {
        stats.fronts+=item.case_front!=0;
        stats.backs+=item.case_back!=0;
        stats.spines+=item.case_spine!=0;
        stats.scenes+=item.case_scene!=0;
        stats.templates+=item.case_template_front!=0 &&
                         item.case_template_back!=0 &&
                         item.case_template_spine!=0;
    }
    return true;
}

bool Catalog::refresh_selected_case_art(gfx::Renderer &renderer)
{
    const int index=niak::case_media_stats.preferred_index;
    const auto case_status=niak_case_art_download_status();
    const unsigned completed=case_status.completed;
    if(index<0 || static_cast<std::size_t>(index)>=items_.size())return false;
    const bool same_focus=index==last_case_focus_;
    // A focus change must not decode an entire sleeve in one idle frame.
    // Eleven stages also permit individually refreshing newly cached sides.
    if(same_focus && completed==last_case_completed_ &&
       case_hydration_step_>=11u)
        return false;
    if(!same_focus || completed!=last_case_completed_)
        case_hydration_step_=0;
    if(same_focus && completed!=last_case_completed_)
        niak_invalidate_prepared_case_art(
            items_[static_cast<std::size_t>(index)].title_id);
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
                 &old.case_shot2}) {
                if(!*texture)continue;
                retiring_case_textures_.push_back(*texture);
                *texture=0;
            }
            // Bound the queue during repeated rapid transitions. In normal
            // operation, release just one retired GPU handle per idle tick.
            while(retiring_case_textures_.size()>27u)
                release_one_retired_case_texture(renderer);
            // Shared templates have their own lifecycle.
            old.case_template_front=0;
            old.case_template_back=0;
            old.case_template_spine=0;
            old.case_reload_mask=0;
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
        case_hydration_step_=11u; // No retail box for app/system placeholders.
        recount_case_faces();
        return false;
    }
    bool changed=false;
    // Do not destroy an official face when the CDN commits a newer scan:
    // CPU preparation is asynchronous, and removal here creates a blank
    // face until the worker and GPU upload have finished.
    // The source's per-side epochs are scoped to the current selection.
    for(unsigned side=0;side<updated.size();++side) {
        // Logo art is not displayed as a separate front overlay on PS5.
        if(updated[side] && side!=3u)
            selected.case_reload_mask|=(1u<<side);
    }
    const auto missing=[&](std::uint32_t &texture,const char *side,
                           float *aspect=nullptr) {
        unsigned bit=0;
        for(const auto &entry : {
            std::pair<const char *,unsigned>{"front",0u},
            {"back",1u},{"spine",2u},{"hero",4u},
            {"shot1",5u},{"shot2",6u}}) {
            if(std::strcmp(side,entry.first)==0) {
                bit=(1u<<entry.second);
                break;
            }
        }
        if(texture && !(selected.case_reload_mask & bit))return;
        // PS5 queues new artwork and returns zero. Keep the resident
        // texture intact until refresh_pending_case_art accepts the new one.
        const auto refreshed=niak_load_case_art(
            renderer,selected.title_id,side,aspect);
        if(refreshed) {
            if(texture)niak_destroy_case_texture(renderer,texture);
            texture=refreshed;
            selected.case_reload_mask&=~bit;
            changed=true;
        }
    };
    const char *platform=selected.title_id[0]=='C'?"ps4":"ps5";
    // At most ONE expensive image decode/upload for each idle tick.
    // Front/back/spine are prioritized ahead of the recomposed paper faces.
    switch(case_hydration_step_++) {
    case 0: missing(selected.case_front,"front"); break;
    case 1: missing(selected.case_back,"back"); break;
    case 2: missing(selected.case_spine,"spine"); break;
    case 3:
        if(!selected.case_front && !selected.case_template_front)
            selected.case_template_front=niak_load_case_template(
                renderer,platform,"front");
        break;
    case 4:
        if(!selected.case_front && !selected.case_scene)
            selected.case_scene=niak_load_game_background(
                renderer,selected.title_id,&selected.case_scene_aspect);
        break;
    case 5:
        if(!selected.case_front)
            missing(selected.case_poster,"poster",&selected.poster_aspect);
        break;
    case 6:
        // One fanart allocation can serve either missing face.
        if(!selected.case_front || !selected.case_back)
            missing(selected.case_hero,"hero",&selected.case_hero_aspect);
        break;
    case 7:
        if(!selected.case_back && !selected.case_template_back)
            selected.case_template_back=niak_load_case_template(
                renderer,platform,"back");
        break;
    case 8:
        if(!selected.case_back)
            missing(selected.case_shot1,"shot1",&selected.case_shot1_aspect);
        break;
    case 9:
        if(!selected.case_back)
            missing(selected.case_shot2,"shot2",&selected.case_shot2_aspect);
        break;
    case 10:
        if(!selected.case_spine && !selected.case_template_spine)
            selected.case_template_spine=niak_load_case_template(
                renderer,platform,"spine");
        break;
    default: break;
    }
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
        // Limit successful asynchronous GPU uploads to one idle frame.
        // A completed download is left in its single-result worker slot
        // until a later tick; do not decode or wait here.
#if defined(__PROSPERO__)
        // One retired case texture consumes the idle frame's GPU budget.
        bool gpu_budget_used=navigation_idle &&
            catalog.release_one_retired_case_texture(renderer);
        if(navigation_idle && !gpu_budget_used &&
           (frames%4u==0 || first_idle_focus) &&
           catalog.has_pending_covers()) {
            (void)catalog.stream_next_covers(renderer,fonts,1);
            gpu_budget_used=true;
        }
        if(navigation_idle && !gpu_budget_used)
            gpu_budget_used=catalog.refresh_pending_game_icons(renderer);
        if(navigation_idle && !gpu_budget_used)
            gpu_budget_used=catalog.refresh_pending_case_art(renderer);
        if(navigation_idle && !gpu_budget_used)
            gpu_budget_used=catalog.refresh_pending_case_templates(renderer);
        if(navigation_idle && !gpu_budget_used)
            gpu_budget_used=catalog.refresh_pending_case_background(renderer);
        if(navigation_idle && !gpu_budget_used)
            niak_profile_poll_avatar(renderer);
#else
        // Host preview remains eager, but detached GPU handles still drain.
        if(navigation_idle)
            (void)catalog.release_one_retired_case_texture(renderer);
        if(navigation_idle && (frames%4u==0 || first_idle_focus))
            (void)catalog.stream_next_covers(renderer,fonts,1);
        if(navigation_idle) {
            (void)catalog.refresh_pending_game_icons(renderer);
            (void)catalog.refresh_pending_case_art(renderer);
            (void)catalog.refresh_pending_case_templates(renderer);
            (void)catalog.refresh_pending_case_background(renderer);
            niak_profile_poll_avatar(renderer);
        }
#endif
        // Missing icons can recover after ShadowMountPlus starts late.
        // Unlike initial streaming, retry does not re-read local files.
        if(navigation_idle && frames>0 && frames%600u==0)
            catalog.retry_missing_game_icons();
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
#include "niak/local_inventory_merge.hpp"
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace hui::demo
{
Catalog::Catalog()
{
    reload();
}

// Worker-owned read-only scans; the renderer only compares prepared IDs.
// New title/permission sources can appear after startup without blocking
// DualSense navigation on directory walks, SQLite or broker connections.
namespace {
struct InventoryProbeResult {
    std::vector<std::string> installed;
    std::vector<std::string> applications;
    // Owner-local FTP overlays are facts about names/categories, NOT proof
    // of installation. They can arrive after Catalog construction.
    std::vector<NiakGame> metadata;
};
struct InventoryProbeState {
    std::mutex mutex;
    InventoryProbeResult ready_data;
    bool running=false;
    bool ready=false;
    std::chrono::steady_clock::time_point last_started{};
};
InventoryProbeState &inventory_probe_state() {
    // Detached workers do not reference a particular Catalogue instance.
    static InventoryProbeState *state=new InventoryProbeState;
    return *state;
}
void collect_inventory_ids(std::vector<std::string> &ids,
                           const std::vector<NiakGame> &buffer,int count,
                           std::vector<std::string> *apps=nullptr) {
    for(int n=0;n<count && n<static_cast<int>(buffer.size());++n) {
        const NiakGame &game=buffer[static_cast<std::size_t>(n)];
        const char *id=game.id;
        if(!id[0])continue;
        if(std::find(ids.begin(),ids.end(),id)==ids.end())
            ids.emplace_back(id);
        // The late scan must detect category changes for titles that were
        // already on the shelf as generic games. Media manifests and actual
        // installed launcher names are stronger evidence than the stale
        // initial category. Do not infer applications from their description.
        if(apps && (game.application_category==2 ||
                    niak_known_application(game.title)) &&
           std::find(apps->begin(),apps->end(),id)==apps->end())
            apps->emplace_back(id);
    }
}
InventoryProbeResult scan_inventory_background() {
    InventoryProbeResult result;
    std::vector<NiakGame> records(NIAKPS5_MAX_GAMES);
    int count=niak_scan_broker_games(records.data(),records.size());
    if(count>0)collect_inventory_ids(result.installed,records,count);
    count=niak_scan_installed_folders("",records.data(),records.size());
    if(count>0)collect_inventory_ids(result.installed,records,count,
                                      &result.applications);
    count=niak_scan_homebrews("",records.data(),records.size());
    if(count>0)collect_inventory_ids(result.installed,records,count,
                                      &result.applications);
    count=niak_scan_shadowmount(records.data(),records.size());
    if(count>0)collect_inventory_ids(result.installed,records,count,
                                      &result.applications);
    count=niak_scan_games("/system_data/priv/mms/app.db","",
                          records.data(),records.size());
    if(count>0)collect_inventory_ids(result.installed,records,count,
                                      &result.applications);
    count=niak_snapshot_read(NIAK_APPS_SNAPSHOT_APP_FILE,
                             records.data(),records.size());
    if(count<0)count=niak_snapshot_read(NIAK_APPS_SNAPSHOT_APP_SOURCE,
                                        records.data(),records.size());
    if(count<0)count=niak_snapshot_read(NIAK_APPS_SNAPSHOT_FILE,
                                        records.data(),records.size());
    if(count>0)collect_inventory_ids(result.applications,records,count);
    // Both staged and private local overlays are read on THIS worker, never
    // during a normal UI tick. The private overlay wins duplicate IDs.
    std::vector<NiakGame> overlay(NIAKPS5_MAX_GAMES);
    const int overlays=niak_merge_local_inventories(
        "/app0/assets/niak-local-titles.tsv",
        "/data/homebrew/PPSA99386/assets/niak-local-titles.tsv",
        overlay.data(),overlay.size());
    if(overlays>0) {
        overlay.resize(static_cast<std::size_t>(overlays));
        result.metadata=std::move(overlay);
    }
    return result;
}
void start_inventory_probe() {
    std::thread([] {
        auto result=scan_inventory_background();
        auto &state=inventory_probe_state();
        std::lock_guard<std::mutex> lock(state.mutex);
        state.ready_data=std::move(result);
        state.running=false;
        state.ready=true;
    }).detach();
}
} // namespace

bool Catalog::refresh_if_unavailable(gfx::Renderer &renderer,
                                     const ui::Fonts &fonts)
{
    InventoryProbeResult result;
    bool ready=false;
    bool schedule=false;
    {
        auto &state=inventory_probe_state();
        std::lock_guard<std::mutex> lock(state.mutex);
        if(state.ready) {
            result=std::move(state.ready_data);
            state.ready=false;
            ready=true;
        } else if(!state.running) {
            const auto now=std::chrono::steady_clock::now();
            if(state.last_started.time_since_epoch().count()==0 ||
               now-state.last_started>=std::chrono::seconds(30)) {
                state.last_started=now;
                state.running=true;
                schedule=true;
            }
        }
    }
    if(schedule)start_inventory_probe();
    if(!ready)return false;

    // A nonempty shelf can still be missing newly mounted applications.
    // Avoid full rebuilds unless title identity or verified app type changed.
    bool changed=false;
    for(const std::string &id:result.installed) {
        const auto existing=std::find_if(items_.begin(),items_.end(),
            [&](const Item &entry) {
                return std::strcmp(entry.title_id,id.c_str())==0;
            });
        if(existing==items_.end()) {
            changed=true;
            break;
        }
    }
    if(!changed)for(const std::string &id:result.applications) {
        for(const Item &entry:items_)
            if(!entry.application &&
               std::strcmp(entry.title_id,id.c_str())==0) {
                changed=true;
                break;
            }
        if(changed)break;
    }
    if(!changed)for(const NiakGame &record:result.metadata) {
        // An FTP manifest can update the French display name of a live
        // title without adding a new installed ID. Never promote a stale
        // standalone FTP record into a visible or launchable application.
        if(std::find(result.installed.begin(),result.installed.end(),
                     record.id)==result.installed.end())continue;
        const auto existing=std::find_if(items_.begin(),items_.end(),
            [&](const Item &entry) {
                return std::strcmp(entry.title_id,record.id)==0;
            });
        if(existing==items_.end())continue;
        if((record.title[0] &&
            std::strcmp(existing->title,record.title)!=0) ||
           (record.application_category==2 && !existing->application)) {
            changed=true;
            break;
        }
    }
    if(!changed)return false;

    release_covers(renderer);
    items_.clear();
    owned_titles_.clear();
    owned_blurbs_.clear();
    last_case_focus_=-1;
    retained_case_focus_=-1;
    case_hydration_step_=0;
    last_case_completed_=0;
    last_case_sides_={};
    reload();
    (void)build_covers(renderer,fonts);
    return !items_.empty() && items_[0].title_id[0]!=0;
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
    // Both local overlays enrich ONLY live IDs. The private FTP overlay
    // wins on exact ID collisions, without resurrecting uninstalled titles.
    std::vector<NiakGame> observed(games.size());
    int packaged_count=-1,private_count=-1;
    const int cached_count=niak_merge_local_inventories(
        "/app0/assets/niak-local-titles.tsv",
        "/data/homebrew/PPSA99386/assets/niak-local-titles.tsv",
        observed.data(),observed.size(),&packaged_count,&private_count);
    sys::log("[NiakPS5] title overlays: packaged/private/merged=%d/%d/%d",
             packaged_count,private_count,cached_count);
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
    }
    // If every live source is unavailable/empty, do NOT display historical
    // FTP entries as installed applications. Keep a truthful placeholder
    // and let the asynchronous broker recovery repopulate verified IDs.
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
            item.studio=item.application ?
                "Application installée" : "Jeu installé";
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
        item.blurb = cached_count>0 && count==0
            ? "Ancien inventaire FTP disponible, mais aucun titre installé n'est actuellement vérifié. Les entrées obsolètes restent masquées."
            : broker_count==0
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
