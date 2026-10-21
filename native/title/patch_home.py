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
    """        if (sheet_open_)
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
            list.image(wallpaper, {0, 0, gfx::kVirtualWidth, gfx::kVirtualHeight},
                       gfx::kFullUv, kWhite.with_alpha(0.59f));
            list.gradient_rect({0, 0, gfx::kVirtualWidth, gfx::kVirtualHeight}, 0,
                               Color::rgb(0x081014, 0.68f),
                               Color::rgb(0x051015, 0.81f));
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
        ui::paragraph(list, fonts.regular,
                      "Les reglages de la console restent geres par Sony. "
                      "Le dernier choix quitte NiakPS5 pour y acceder. "
                      "Rond : revenir aux onglets.",
                      104, 935, 20, 1450, 30, kWhite.with_alpha(0.55f), 2);
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
                '#include "niak/daily_backdrop.hpp"\n#include "niak/profile.hpp"')
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
