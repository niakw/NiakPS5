#!/usr/bin/env python3
"""Connect NiakPS5's visible top tabs to actual DualSense focus and pages.
Runs on the pinned PS5 GPU UI checkout after prepare.py, fail closed on drift.
"""
from pathlib import Path
import argparse

def once(text, before, after):
    n = text.count(before)
    if n != 1:
        raise RuntimeError(f"Expected exactly one upstream anchor: {before[:72]!r}; got {n}")
    return text.replace(before, after, 1)

def patch(kit):
    file = kit / "src/concepts/aurora.cpp"
    text = file.read_text()
    text = once(text, "        if (sheet_open_)\n            update_sheet(input, feedback);\n        else\n            update_shelves(input, feedback);",
    """        // R1 deliberately cycles available packaged wallpapers.
        // Calendar-day selection remains automatic until R1 is pressed.
        // R1 also works while a details panel is visible or another
        // top-level tab has focus. It must not silently do nothing there.
        if (input.is_pressed(Action::page_next))
        {
            niak_next_daily_backdrop();
            feedback.play(audio::Cue::tab);
        }
        if (sheet_open_)
            update_sheet(input, feedback);
        else if (top_focus_)
            update_tabs(input, feedback);
        else if (active_tab_ == 3 || (active_tab_ == 2 && shelves_.size() < 2))
            update_page(input, feedback);
        else if (input.nav == Direction::up || input.is_pressed(Action::menu))
        {
            top_focus_ = true;
            selected_tab_ = active_tab_;
            feedback.play(audio::Cue::tab);
        }
        else
            update_shelves(input, feedback);""")
    text = once(text, '        gfx::DrawList &list = frame.scene;', '''        gfx::DrawList &list = frame.scene;
        // Keep the animated aurora/smoke behind real game artwork.
        if (const std::uint32_t wallpaper = niak_daily_backdrop())
        {
            // Previously the 0.59 image alpha combined with 0.68–0.81
            // darkening left only ~11–19% of the wallpaper visible. R1 could
            // appear ineffective even with a successfully changed texture.
            // Keep a dark readability veil while preserving actual scenery.
            list.image(wallpaper, {0, 0, gfx::kVirtualWidth, gfx::kVirtualHeight},
                       gfx::kFullUv, kWhite.with_alpha(0.85f));
            list.gradient_rect({0, 0, gfx::kVirtualWidth, gfx::kVirtualHeight}, 0,
                               Color::rgb(0x081014, 0.52f),
                               Color::rgb(0x051015, 0.65f));
        }''')
    text = once(text, "        draw_top_bar(list);\n        draw_hero(list);\n        draw_shelves(list);",
    """        draw_top_bar(list);
        if (active_tab_ < 2 || (active_tab_ == 2 && shelves_.size() > 1))
        {
            draw_hero(list);
            draw_shelves(list);
        }
        else
            draw_aux_page(list);""")
    text = once(text, "    void update_shelves(const InputFrame &input, app::Feedback &feedback)\n",
    """    void update_tabs(const InputFrame &input, app::Feedback &feedback)
    {
        if (input.nav == Direction::left || input.nav == Direction::right)
        {
            selected_tab_ = std::clamp(selected_tab_ +
                (input.nav == Direction::right ? 1 : -1), 0, 3);
            feedback.play(audio::Cue::focus);
        }
        if (input.is_pressed(Action::confirm) || input.nav == Direction::down)
        {
            active_tab_ = selected_tab_;
            top_focus_ = false;
            settings_cursor_ = 0;
            row_ = active_tab_ == 2 && shelves_.size() > 1 ? 1 : 0;
            feedback.play(audio::Cue::open);
        }
        if (input.is_pressed(Action::back))
        {
            active_tab_ = 0;
            top_focus_ = false;
            feedback.play(audio::Cue::back);
        }
    }

    void update_page(const InputFrame &input, app::Feedback &feedback)
    {
        if (input.is_pressed(Action::back) || input.is_pressed(Action::menu))
        {
            top_focus_ = true;
            selected_tab_ = active_tab_;
            feedback.play(audio::Cue::back);
            return;
        }
        if (active_tab_ != 3)
        {
            if (input.nav == Direction::up)
            {
                top_focus_ = true;
                selected_tab_ = active_tab_;
            }
            return;
        }
        if (input.nav == Direction::up && settings_cursor_ == 0)
        {
            top_focus_ = true;
            selected_tab_ = active_tab_;
            return;
        }
        if (input.nav == Direction::up || input.nav == Direction::down)
        {
            settings_cursor_ = std::clamp(settings_cursor_ +
                (input.nav == Direction::down ? 1 : -1), 0, 8);
            feedback.play(audio::Cue::focus);
        }
        if (input.is_pressed(Action::confirm))
        {
            auto &s = context_.settings;
            switch (settings_cursor_)
            {
            case 0: s.resolution = (s.resolution + 1) % hui::Settings::kResolutionCount; break;
            case 1: s.ui_volume = (s.ui_volume + 1) % 11; break;
            case 2: s.music_volume = (s.music_volume + 1) % 11; break;
            case 3: s.reduced_motion = !s.reduced_motion; break;
            case 4: s.show_fps = !s.show_fps; break;
            case 5: s.haptics = !s.haptics; break;
            case 6: s.light_bar = !s.light_bar; break;
            case 7: s.sfx_volume = (s.sfx_volume + 1) % 11; break;
            case 8: sys::quit(); return; // Return to Sony Home to access native settings

            }
            context_.settings_changed = true;
            feedback.play(audio::Cue::complete);
        }
    }

    void draw_aux_page(gfx::DrawList &list) const
    {
        const auto &fonts = context_.fonts;
        const bool settings = active_tab_ == 3;
        ui::text(list, fonts.display, settings ? "Reglages" : "Multimedia",
                 96, 232, 78, kWhite);
        if (!settings)
        {
            ui::text(list, fonts.semibold, "Galerie de captures", 100, 333, 36,
                     palette_[3].value());
            ui::paragraph(list, fonts.regular,
                          "Acces aux captures PS5 non encore autorise depuis ce titre. "
                          "Aucune photo ou video personnelle n'est ouverte automatiquement.",
                          102, 407, 26, 1120, 40, kWhite.with_alpha(0.85f), 3);
            ui::text(list, fonts.regular, "Rond : revenir aux onglets", 102, 560, 22,
                     kWhite.with_alpha(0.55f));
            return;
        }
        // These are actual GPU textures loaded by this application, not
        // files merely visible through the separate FTP server.
        const auto &media=niak::case_media_stats;
        char media_label[128];
        ui::text(list,fonts.semibold,"Médias lus par NiakPS5",
                 1430,305,21,kWhite);
        std::snprintf(media_label,sizeof(media_label),
                      "%u titres | %u icônes",media.titles,media.icons);
        ui::text(list,fonts.regular,media_label,1430,346,18,kWhite);
        std::snprintf(media_label,sizeof(media_label),
                      "Rectos : %u  Versos : %u",media.fronts,media.backs);
        ui::text(list,fonts.regular,media_label,1430,379,18,kWhite);
        std::snprintf(media_label,sizeof(media_label),
                      "Tranches : %u  Panoramas : %u",media.spines,media.scenes);
        ui::text(list,fonts.regular,media_label,1430,412,18,kWhite);
        std::snprintf(media_label,sizeof(media_label),
                      "Gabarits complets : %u",media.templates);
        ui::text(list,fonts.regular,media_label,1430,445,18,kWhite);
        ui::paragraph(list,fonts.regular,
                      "0 signifie non chargé ou accès refusé, pas forcément absent du FTP.",
                      1430,480,17,410,23,kWhite.with_alpha(0.65f),3);
        const char *labels[] = {"Resolution d'affichage (redemarrage)",
                                "Volume de l'interface", "Musique de fond",
                                "Animations reduites", "Afficher FPS",
                                "Vibrations DualSense", "Couleur lumineuse",
                                "Volume des effets sonores",
                                "Retour a l'accueil Sony / parametres PS5"};
        const auto &s=context_.settings;
        char value[40];
        for (int i=0;i<9;++i)
        {
            const float y = 255.0f + 68.0f * static_cast<float>(i);
            const bool focused = !top_focus_ && settings_cursor_ == i;
            const Rect tile{100, y, 1280, 59};
            list.bordered_rect(tile, 17,
                               kWhite.with_alpha(focused ? 0.12f : 0.04f),
                               focused ? 2.4f : 0.8f,
                               focused ? palette_[3].value() : kWhite.with_alpha(0.19f));
            const char *display="";
            if(i==0) display=hui::Settings::kResolutions[s.resolution].label;
            else if(i==1 || i==2 || i==7)
            {
                std::snprintf(value,sizeof(value),"%d / 10",
                              i==1 ? s.ui_volume : i==2 ? s.music_volume : s.sfx_volume);
                display=value;
            }
            else if(i==8) display="OUVRIR LE SYSTEME";
            else
            {
                const bool on=i==3 ? s.reduced_motion : i==4 ? s.show_fps :
                              i==5 ? s.haptics : s.light_bar;
                display=on ? "ACTIVE" : "DESACTIVE";
            }
            ui::text(list, fonts.semibold, labels[i], 130, y+39, 24, kWhite);
            ui::text(list, fonts.semibold, display, 1350, y+39, 21,
                     i==8 ? palette_[3].value() : kWhite.with_alpha(0.75f),
                     gfx::Align::right);
        }
        // Detect the local marker only; the title sandbox cannot certify that
        // Payload Manager actually executed its one-shot payload.
        const bool enabled=[] {
            std::FILE *file=std::fopen("/data/niakps5-autostart.enabled","rb");
            if(!file)return false;
            std::fclose(file);return true;
        }();
        const bool disabled=[] {
            std::FILE *file=std::fopen("/data/niakps5-autostart.disable","rb");
            if(!file)return false;
            std::fclose(file);return true;
        }();
        // Refresh the actual local payload log and broker liveness together.
        // Old successes are historical, and a log can appear AFTER UI startup.
        static char journal_status[96]="Journal inaccessible";
        static bool live_broker=false;
        static std::time_t last_check=0;
        const std::time_t now=std::time(nullptr);
        if(!last_check || now<last_check || now-last_check>=15) {
            last_check=now;
            const auto read_status=[]() -> const char * {
                std::FILE *log=std::fopen("/data/niakps5-autostart.log","rb");
                if(!log)return "Journal inaccessible";
                if(std::fseek(log,0,SEEK_END)!=0) {
                    std::fclose(log);return "Journal illisible";
                }
                const long size=std::ftell(log);
                if(size<0 || std::fseek(log,size>8192?size-8192:0,SEEK_SET)!=0) {
                    std::fclose(log);return "Journal illisible";
                }
                char buffer[8193]{};
                const std::size_t count=std::fread(buffer,1,sizeof(buffer)-1,log);
                std::fclose(log);
                buffer[count]=0;
                const char *attempt=nullptr;
                for(const char *p=buffer;(p=std::strstr(p,
                         "NiakPS5 optional autostart start"));++p)
                    attempt=p;
                if(!attempt)return "Aucune exécution identifiable";
                const char *result=nullptr;
                for(const char *p=attempt;(p=std::strstr(p,
                         "sceSystemServiceLaunchApp rc="));++p)
                    result=p;
                if(!result)return "Dernière tentative sans lancement confirmé";
                return std::strncmp(result,
                    "sceSystemServiceLaunchApp rc=0x00000000",
                    sizeof("sceSystemServiceLaunchApp rc=0x00000000")-1)==0
                        ? "Dernier lancement OK (journal historique)"
                        : "Dernier lancement en erreur (journal)";
            };
            std::snprintf(journal_status,sizeof(journal_status),"%s",read_status());
            live_broker=niak_launch_broker_ready();
        }
        ui::text(list, fonts.semibold, "Démarrage automatique :", 110, 882, 22, kWhite);
        ui::text(list, fonts.regular,
                 disabled ? "Désactivé" :
                 live_broker ? "Payload actif (service local joignable)" :
                 enabled ? "Configuré (exécution non confirmée)" :
                           "Non confirmé : fichiers inaccessibles ou absents",
                 500, 882, 20, kWhite.with_alpha(0.78f));
        ui::text(list, fonts.regular, journal_status, 500, 910, 18,
                 kWhite.with_alpha(0.66f));
        ui::text(list, fonts.regular,
                 live_broker ? "Service Jouer : actif (PLDmgr)" :
                               "Service Jouer : absent ou inaccessible",
                 500, 939, 18,kWhite.with_alpha(0.75f));
        ui::text(list, fonts.regular, niak::revision, 110, 950, 20,
                 kWhite.with_alpha(0.72f));
        ui::paragraph(list, fonts.regular,
                      "Les reglages de la console restent geres par Sony. "
                      "Le dernier choix quitte NiakPS5 pour y acceder. "
                      "Rond : revenir aux onglets.",
                      104, 990, 20, 1450, 30, kWhite.with_alpha(0.55f), 2);
    }

    void update_shelves(const InputFrame &input, app::Feedback &feedback)
""")
    text = once(text, "            const bool active = i == 0;", "            const bool active = i == active_tab_;")
    text = once(text, "            x += w + 44;\n", """            if (top_focus_ && i == selected_tab_)
                list.bordered_rect({x - 15, 53, w + 30, 56}, 17,
                                   kWhite.with_alpha(0.06f), 2.6f, palette_[3].value());
            x += w + 44;
""")
    # Read the current local PS5 display name via SceUserService (not a fake logo).
    text = once(text, '#include "niak/daily_backdrop.hpp"',
                '#include "niak/daily_backdrop.hpp"\n#include "niak/profile.hpp"\n#include "niak/asset_stats.hpp"\n#include <ctime>')
    # The demo never had a real profile service. Do not fabricate a user's avatar.
    text = once(text, """        list.circle(1800, 82, 22, palette_[3].value());
        ui::text(list, fonts.semibold, "N", 1800, 91, 22, Color::rgb(0x0b0d16), gfx::Align::center);""",
    """        // Genuine PS5 profile avatar cannot be read in this sandbox.
        // Show no invented account image.
        ui::text(list, fonts.regular, "Profil non lie", 1900, 135, 18,
                 kWhite.with_alpha(0.55f), gfx::Align::right);""")
    text = once(text, 'ui::text(list, fonts.regular, "Profil non lie", 1900, 135, 18,',
                'ui::text(list, fonts.regular, niak_ps5_user_label(), 1900, 135, 18,')
    text = once(text, 'ui::text(list, fonts.regular, niak_ps5_user_label(), 1900, 135, 18,',
                '''if (const auto avatar = niak_profile_avatar())
            list.image(avatar, {1778, 60, 44, 44}, gfx::kFullUv, kWhite, 22);
        ui::text(list, fonts.regular, niak_ps5_user_label(), 1900, 135, 18,''')
    text = once(text, "    int row_ = 0;\n", """    int row_ = 0;
    int active_tab_ = 0;
    int selected_tab_ = 0;
    int settings_cursor_ = 0;
    bool top_focus_ = false;
""")
    file.write_text(text)
    print("NiakPS5: live top tabs and settings controls patched")

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--kit", type=Path, required=True)
    patch(parser.parse_args().kit)
