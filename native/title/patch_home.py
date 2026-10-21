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
        else if (active_tab_ >= 2)
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
                       gfx::kFullUv, kWhite.with_alpha(0.38f));
            list.gradient_rect({0, 0, gfx::kVirtualWidth, gfx::kVirtualHeight}, 0,
                               Color::rgb(0x081014, 0.18f),
                               Color::rgb(0x051015, 0.76f));
        }''')
    text = once(text, "        draw_top_bar(list);\n        draw_hero(list);\n        draw_shelves(list);",
    """        draw_top_bar(list);
        if (active_tab_ < 2)
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
                (input.nav == Direction::down ? 1 : -1), 0, 3);
            feedback.play(audio::Cue::focus);
        }
        if (input.is_pressed(Action::confirm))
        {
            auto &s = context_.settings;
            switch (settings_cursor_)
            {
            case 0: s.reduced_motion = !s.reduced_motion; break;
            case 1: s.show_fps = !s.show_fps; break;
            case 2: s.haptics = !s.haptics; break;
            case 3: s.light_bar = !s.light_bar; break;
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
        const char *labels[] = {"Animations reduites", "Afficher FPS",
                                "Vibrations DualSense", "Couleur lumineuse manette"};
        const bool values[] = {context_.settings.reduced_motion, context_.settings.show_fps,
                               context_.settings.haptics, context_.settings.light_bar};
        for (int i = 0; i < 4; ++i)
        {
            const float y = 288.0f + 108.0f * static_cast<float>(i);
            const bool focused = !top_focus_ && settings_cursor_ == i;
            const Rect tile{100, y, 1180, 82};
            list.bordered_rect(tile, 22,
                               kWhite.with_alpha(focused ? 0.13f : 0.05f),
                               focused ? 2.8f : 1.0f,
                               focused ? palette_[3].value() : kWhite.with_alpha(0.18f));
            ui::text(list, fonts.semibold, labels[i], 132, y + 52, 28, kWhite);
            ui::text(list, fonts.semibold, values[i] ? "ACTIVE" : "DESACTIVE",
                     1242, y + 52, 22,
                     values[i] ? palette_[3].value() : kWhite.with_alpha(0.54f),
                     gfx::Align::right);
        }
        ui::text(list, fonts.regular,
                 "Croix : modifier  /  Haut : barre de navigation  /  Rond : retour",
                 102, 804, 21, kWhite.with_alpha(0.6f));
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
