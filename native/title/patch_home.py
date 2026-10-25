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
                '#include "niak/case_auto_art.hpp"\n'
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
            draw_aux_page(list);
        // Attribution under the footer glyphs, not inside game metadata.
        ui::text(list, context_.fonts.regular, niak_daily_backdrop_caption(),
                 1825, 1061, 15, kWhite.with_alpha(0.52f),
                 gfx::Align::right);""")
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
            case 9:
                settings_link_tried_=true;
                settings_link_rc_=niak_open_system_settings();
                feedback.play(settings_link_rc_==0?
                              audio::Cue::complete:audio::Cue::back);
                return; // Keep UI alive if firmware refuses the deep link.

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
        const NiakArtDownloadStatus cdn=niak_case_art_download_status();
        std::snprintf(media_label,sizeof(media_label),
                      "LaunchBox : %u indexés · %u reçus · élév. %s",
                      cdn.indexed,cdn.completed,
                      niak::payload_process_elevated?"oui":"non");
        ui::text(list,fonts.regular,media_label,1430,524,17,kWhite);
        std::snprintf(media_label,sizeof(media_label),
                      "En file : %u · Échecs : %u · Essais : %u",
                      cdn.queued,cdn.network_failed,cdn.requests);
        ui::text(list,fonts.regular,media_label,1430,550,17,kWhite);
        std::snprintf(media_label,sizeof(media_label),
                      "Sans médias : %u · Corrompus : %u · Stockage : %u",
                      cdn.unmatched,cdn.decode_failed,cdn.write_failed);
        ui::text(list,fonts.regular,media_label,1430,578,15,
                 kWhite.with_alpha(0.7f));
        const char *const cdn_stages[]={
            "aucune","initialisation","template","connexion","requête",
            "envoi","statut HTTP","lecture","taille","nom invalide",
            "libcurl/OpenSSL"};
        const int cdn_stage=cdn.last_network_stage>=0 &&
            cdn.last_network_stage<11?cdn.last_network_stage:0;
        // Keep the precise hexadecimal PS5 result AND identify known
        // certificate, HTTPS authorization, DNS and remote HTTP errors.
        // No bypass of TLS verification or additional network request.
        const unsigned cdn_code=static_cast<unsigned>(cdn.last_network_error);
        const char *cdn_hint="inconnu";
        switch(cdn_code) {
          case 0: cdn_hint="aucune erreur"; break;
          case 403: cdn_hint="CDN interdit"; break;
          case 404: cdn_hint="image absente"; break;
          case 408: cdn_hint="délai HTTP"; break;
          case 429: cdn_hint="limite CDN"; break;
          case 0x8095F00Cu: cdn_hint="sceSsl refus après élévation"; break;
          case static_cast<unsigned>(-10060): cdn_hint="certificat OpenSSL"; break;
          case static_cast<unsigned>(-10028): cdn_hint="délai libcurl"; break;
          case 0x80435060u: cdn_hint="certificat TLS"; break;
          case 0x80435061u: cdn_hint="négociation TLS"; break;
          case 0x8043506Bu: cdn_hint="HTTPS interdit"; break;
          case 0x80436002u: cdn_hint="DNS indisponible"; break;
          case 0x80436003u: cdn_hint="délai DNS"; break;
          default:
            if(cdn_code>=500u && cdn_code<=599u)
                cdn_hint="serveur CDN"; 
            break;
        }
        std::snprintf(media_label,sizeof(media_label),
                      "HTTP 0x%08X (%s; %s) · expirés %u",
                      cdn_code,cdn_hint,cdn_stages[cdn_stage],cdn.exhausted);
        ui::paragraph(list,fonts.regular,media_label,
                      1430,600,14,400,18,kWhite.with_alpha(0.85f),2);
        ui::text(list,fonts.semibold,"Installation du payload ELF",
                 1430,661,20,kWhite);
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
                      1430,691,16,398,21,kWhite.with_alpha(0.78f),2);
        const char *labels[] = {"Resolution d'affichage (redemarrage)",
                                "Volume de l'interface", "Musique de fond",
                                "Animations reduites", "Afficher FPS",
                                "Vibrations DualSense", "Couleur lumineuse",
                                "Volume des effets sonores",
                                "Changer le fond du jour",
                                "Ouvrir les réglages PS5 (essai)"};
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
            else if(i==9) display="OUVRIR";
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
        static unsigned broker_pid=0;
        static std::time_t last_check=0;
        const std::time_t now=std::time(nullptr);
        if(!last_check || now<last_check || now-last_check>=15) {
            last_check=now;
            broker_pid=niak_launch_broker_pid();
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
                    return "SystemService : appel accepté (lancement à vérifier)";
                case NIAK_LAUNCH_LOG_LNC_OK:
                    return "LncUtil : lancement accepté (journal)";
                case NIAK_LAUNCH_LOG_LNC_FAILED:
                    return "LncUtil refusé ou identifiant invalide (journal)";
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
        // A legacy marker must never hide why the broker is unreachable.
        // The snapshot can restore the library without enabling Jouer.
        char service_diagnostic[160];
        std::snprintf(service_diagnostic,sizeof(service_diagnostic),"%s%s",
                      enabled ? "Marqueur présent ; " : "",
                      niak_launch_broker_diagnostic());
        // Diagnostics belong in the RIGHT status rail, never across the
        // ten clickable settings rows on the left.
        ui::text(list, fonts.semibold, "Démarrage automatique",
                 1430, 766, 20, kWhite);
        ui::paragraph(list, fonts.regular,
                 disabled ? "Désactivé" :
                 live_broker ? "Payload actif (service local joignable)" :
                               service_diagnostic,
                 1430, 796, 16, 398, 21, kWhite.with_alpha(0.78f), 2);
        ui::paragraph(list, fonts.regular,
                 live_broker && std::strcmp(journal_status,"Journal inaccessible")==0
                   ? "Service actif ; journal inaccessible depuis la sandbox"
                   : journal_status, 1430, 862, 15, 398, 20,
                 kWhite.with_alpha(0.66f), 2);
        char broker_identity[96];
        if(live_broker && broker_pid)
            std::snprintf(broker_identity,sizeof(broker_identity),
                          "Service Jouer : actif, PID %u",broker_pid);
        else
            std::snprintf(broker_identity,sizeof(broker_identity),"%s",
                live_broker ? "Service Jouer : actif (PID non disponible)" :
                              "Service Jouer : absent ou inaccessible");
        ui::paragraph(list, fonts.regular, broker_identity,
                 1430, 930, 16, 398, 20,kWhite.with_alpha(0.75f),2);
        ui::text(list, fonts.regular, niak::revision, 110, 950, 20,
                 kWhite.with_alpha(0.72f));
        ui::paragraph(list, fonts.regular,
                      settings_link_tried_ ?
                        (settings_link_rc_==0 ?
                         "Raccourci PS5 demandé ; ouverture à vérifier sur console." :
                         "Accès ShellUI refusé. Réglages PS5 accessibles via accueil Sony.") :
                        "Réglages PS5 : raccourci système expérimental. "
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
    bool settings_link_tried_ = false;
    int settings_link_rc_ = -1;
    bool top_focus_ = false;
""")
    # A late PLDmgr inventory can rebuild the Catalog while the user is on
    # a game or Settings. Save navigation BY TITLE ID before old shelf indices
    # disappear; never dereference those indices after the Catalog is replaced.
    text = once(text, "class Aurora final : public app::Concept", """
struct NiakNavigationSnapshot {
    char title_id[16]{};
    int active_tab=0, settings_cursor=0;
    bool top_focus=false, valid=false;
};
NiakNavigationSnapshot &niak_navigation_snapshot() {
    static auto *saved=new NiakNavigationSnapshot;
    return *saved;
}
class Aurora final : public app::Concept""")
    text = once(text, "        shown_ = previous_ = focused_item();", """
        // The old concept was destroyed only after its Catalog refreshed.
        // Its per-frame copied title ID is stable; its old shelf indices
        // are not. Find that ID in the NEW catalogue, or keep safe defaults.
        const auto &nav=niak_navigation_snapshot();
        if(nav.valid) {
            active_tab_=std::clamp(nav.active_tab,0,3);
            settings_cursor_=std::clamp(nav.settings_cursor,0,9);
            top_focus_=nav.top_focus;
            bool found=false;
            if(nav.title_id[0]) {
                for(std::size_t r=0;r<shelves_.size() && !found;++r) {
                    Shelf &shelf=shelves_[r];
                    for(std::size_t column=0;column<shelf.items.size();++column) {
                        const int item_index=shelf.items[column];
                        if(std::strcmp(items[static_cast<std::size_t>(item_index)].title_id,
                                       nav.title_id)!=0)continue;
                        row_=static_cast<int>(r);
                        shelf.column=static_cast<int>(column);
                        found=true;
                        break;
                    }
                }
            }
            // If this game's verified category changed, follow it to its
            // NEW shelf; preserve Settings when Settings was already open.
            if(active_tab_!=3 && found) {
                if(shelves_.size()>1) {
                    if(row_==1)active_tab_=2;
                    else if(active_tab_==2)active_tab_=1;
                }
            }
            // The secondary shelf may disappear when its last item is
            // reclassified or uninstalled. Never reopen an empty tab.
            if(active_tab_==2 && shelves_.size()<2)active_tab_=0;
            selected_tab_=active_tab_;
        }
        row_position_.snap(float(row_));
        std::snprintf(last_selected_title_,sizeof(last_selected_title_),
                      "%s",item(focused_item()).title_id);
        shown_ = previous_ = focused_item();""")
    text = once(text, "    const app::ConceptInfo &info() const override", """
    ~Aurora() override {
        // Do not read context_.catalog here: it was already rebuilt, and
        // shelf indices from the old Concept may be out of bounds.
        auto &nav=niak_navigation_snapshot();
        std::snprintf(nav.title_id,sizeof(nav.title_id),
                      "%s",last_selected_title_);
        nav.active_tab=active_tab_;
        nav.settings_cursor=settings_cursor_;
        nav.top_focus=top_focus_;
        nav.valid=true;
    }

    const app::ConceptInfo &info() const override""")
    text = once(text, "        // ---- animation state ----", """
        // Capture the displayed title AFTER controller navigation and
        // BEFORE the background inventory probe can rebuild the catalogue.
        std::snprintf(last_selected_title_,sizeof(last_selected_title_),
                      "%s",item(focused_item()).title_id);
        // ---- animation state ----""")
    text = once(text, "    int active_tab_ = 0;", """
    char last_selected_title_[16]{};
    int active_tab_ = 0;""")
    file.write_text(text)
    print("NiakPS5: tabs, Settings and title-ID navigation restored on catalogue refresh")

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--kit", type=Path, required=True)
    patch(parser.parse_args().kit)
