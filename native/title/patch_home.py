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
    text = once(text, '#include "niak/daily_backdrop.hpp"',
                '#include "niak/daily_backdrop.hpp"\n'
                '#include "niak/one_shot_install.hpp"\n'
                '#include "niak/launch_log_status.h"')
    text = once(text, "        if (sheet_open_)\n            update_sheet(input, feedback);\n        else\n            update_shelves(input, feedback);",
    """        // L1/R1 navigate the four top-level menu tabs in either direction.
        // They never touch the daily wallpaper or alter a game's saved state.
        const bool l1 = input.is_pressed(Action::page_prev);
        const bool r1 = input.is_pressed(Action::page_next);
        if (l1 != r1)
        {
            active_tab_ = (active_tab_ + (r1 ? 1 : 3)) % 4;
            selected_tab_ = active_tab_;
            top_focus_ = false;
            sheet_open_ = false;
            settings_cursor_ = 0;
            row_ = (active_tab_ == 2 && shelves_.size() > 1) ? 1 : 0;
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
            // Keep one wallpaper for the calendar day. L1/R1 only switch
            // top tabs; the Settings action alone changes today's choice.
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
                (input.nav == Direction::down ? 1 : -1), 0, 9);
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
            case 8: niak_next_daily_backdrop(); feedback.play(audio::Cue::complete); return;
            case 9: sys::quit(); return; // Return to Sony Home to access native settings

            }
            context_.settings_changed = true;
            feedback.play(audio::Cue::complete);
        }
    }

    void draw_aux_page(gfx::DrawList &list) const
    {
        const auto &fonts = context_.fonts;
        const bool settings = active_tab_ == 3;
        ui::text(list, fonts.display, settings ? "Réglages" : "Multimédia",
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
        // Display the one-shot helper result independently from the live
        // PLDmgr broker. A copied ELF does not imply that it is resident.
        const int install_status=niak::payload_install_status;
        // These are actual GPU textures loaded by this application, not
        // files merely visible through the separate FTP server.
        const auto &media=niak::case_media_stats;
        char media_label[128];
        ui::text(list,fonts.semibold,"Médias lus par NiakPS5",
                 1430,305,21,kWhite);
        std::snprintf(media_label,sizeof(media_label),
                      "Chargés : %u/%u | icônes : %u",
                      media.titles,media.total_titles,media.icons);
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
        std::snprintf(media_label,sizeof(media_label),
                      "Mémoire scans 3D : %.1f Mio (RGBA8)",
                      double(media.case_texture_bytes)/1048576.0);
        ui::text(list,fonts.regular,media_label,1430,477,18,kWhite);
        ui::paragraph(list,fonts.regular,
                      "0 signifie non chargé ou accès refusé, pas forcément absent du FTP.",
                      1430,520,17,410,23,kWhite.with_alpha(0.65f),3);
        ui::text(list,fonts.semibold,"Installation du payload ELF",
                 1430,612,20,kWhite);
        const char *install_label= install_status==1
            ? "Fichiers mis à jour. Relancer la chaîne jailbreak."
            : install_status==0
            ? "Payload identique au paquet installé."
            : install_status==-1
            ? "elfldr ou élévation indisponible (port 9021)."
            : install_status==-2
            ? "Installation refusée : fichiers ou droits invalides."
            : "Pas de tentative (aperçu hôte).";
        ui::paragraph(list,fonts.regular,install_label,
                      1430,650,18,420,27,kWhite.with_alpha(0.78f),3);
        const char *labels[] = {"Resolution d'affichage (redemarrage)",
                                "Volume de l'interface", "Musique de fond",
                                "Animations reduites", "Afficher FPS",
                                "Vibrations DualSense", "Couleur lumineuse",
                                "Volume des effets sonores",
                                "Changer le fond du jour",
                                "Retour à l’accueil Sony"};
        const auto &s=context_.settings;
        char value[40];
        for (int i=0;i<10;++i)
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
            else if(i==8) display="CHANGER";
            else if(i==9) display="QUITTER NIAKPS5";
            else
            {
                const bool on=i==3 ? s.reduced_motion : i==4 ? s.show_fps :
                              i==5 ? s.haptics : s.light_bar;
                display=on ? "ACTIVE" : "DESACTIVE";
            }
            ui::text(list, fonts.semibold, labels[i], 130, y+39, 24, kWhite);
            ui::text(list, fonts.semibold, display, 1350, y+39, 21,
                     i==9 ? palette_[3].value() : kWhite.with_alpha(0.75f),
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
                switch(niak_last_launch_result(buffer)) {
                case NIAK_LAUNCH_LOG_SYSTEM_OK:
                    return "SystemService : lancement accepté (journal)";
                case NIAK_LAUNCH_LOG_LNC_OK:
                    return "LncUtil : lancement accepté (journal)";
                case NIAK_LAUNCH_LOG_LNC_FAILED:
                    return "SystemService + LncUtil refusés (journal)";
                case NIAK_LAUNCH_LOG_SYSTEM_FAILED:
                    return "SystemService refusé ; repli non confirmé";
                case NIAK_LAUNCH_LOG_NO_ATTEMPT:
                    return "Aucune tentative de lancement récente";
                default:
                    return "Aucun démarrage du payload identifiable";
                }
            };
            std::snprintf(journal_status,sizeof(journal_status),"%s",read_status());
        }
        // The liveness function caches PING for one second; this runs each
        // Settings repaint so a newly started payload is shown promptly.
        live_broker=niak_launch_broker_ready();
        ui::text(list, fonts.semibold, "Démarrage automatique :", 110, 882, 22, kWhite);
        ui::text(list, fonts.regular,
                 disabled ? "Désactivé" :
                 live_broker ? "Payload actif (service local joignable)" :
                 enabled ? "Marqueur présent, mais service indisponible" :
                           "Service local non joignable (PING échoué)",
                 500, 882, 20, kWhite.with_alpha(0.78f));
        ui::text(list, fonts.regular,
                 live_broker && std::strcmp(journal_status,"Journal inaccessible")==0
                   ? "Service actif ; journal inaccessible depuis le sandbox"
                   : journal_status, 500, 910, 18,
                 kWhite.with_alpha(0.66f));
        ui::text(list, fonts.regular,
                 live_broker ? "Service Jouer : actif (PLDmgr)" :
                               "Service Jouer : absent ou inaccessible",
                 500, 939, 18,kWhite.with_alpha(0.75f));
        ui::text(list, fonts.regular, niak::revision, 110, 950, 20,
                 kWhite.with_alpha(0.72f));
        ui::paragraph(list, fonts.regular,
                      "Les réglages système restent accessibles via l’accueil Sony. "
                      "Le dernier choix quitte uniquement NiakPS5. "
                      "Rond : revenir aux onglets.",
                      104, 990, 20, 1450, 30, kWhite.with_alpha(0.55f), 2);
    }

    void update_shelves(const InputFrame &input, app::Feedback &feedback)
""")
    text = once(text, "            const bool active = i == 0;", "            const bool active = i == active_tab_;")
    # Real GPU screenshot review: tabs are too faint on light scenery.
    # A subtle dark band and stronger inactive text keep their contrast
    # without hiding the dynamic wallpaper or adding a second UI layer.
    text = once(text,
        '        const char *tabs[] = {"NIAK", "Jeux", "Multimédia", "Réglages"};',
        '        list.rounded_rect({70, 45, 655, 75}, 22, Color::rgb(0x06101c, 0.28f));\n'
        '        const char *tabs[] = {"NIAK", "Jeux", "Multimédia", "Réglages"};')
    text = once(text,
        'kWhite.with_alpha(active ? 1.0f : 0.55f)',
        'kWhite.with_alpha(active ? 1.0f : 0.88f)')
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
