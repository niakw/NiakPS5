#!/usr/bin/env python3
"""Final native UI fixes applied after prepare.py and patch_home.py.
Strict matching deliberately fails CI whenever the pinned upstream UI changes.
"""
from pathlib import Path
import argparse

def exactly(text, old, new, count=1):
    n=text.count(old)
    if n!=count: raise RuntimeError(f"Expected {count} matches, found {n}: {old[:80]!r}")
    return text.replace(old,new)

def patch(kit):
    p=kit/"src/concepts/aurora.cpp"
    s=p.read_text("utf-8")
    s=exactly(s,'const char *tabs[] = {"NIAK", "Jeux", "Multimédia", "Réglages"};',
                 'const char *tabs[] = {"NiakPS5", "Jeux", "Multimédia", "Réglages"};')
    # Up only selects the top bar from the FIRST row. From Homebrew row 1 it
    # must move back to row 0, working with both D-pad and left joystick.
    s=exactly(s,'else if (input.nav == Direction::up || input.is_pressed(Action::menu))',
                 'else if ((input.nav == Direction::up && row_ == 0) || input.is_pressed(Action::menu))')
    # Procedural covers are FBO textures (bottom-left); actual PS5 PNG images
    # are uploaded top-row-first and REQUIRE kFullUv. kCanvasUv flips the PNG.
    s=exactly(s,'list.image(it.cover, art, gfx::kCanvasUv, kWhite, 36);',
                 'niak_draw_rotating_case(list,it,art,'
                 'context_.settings.reduced_motion ? 0.0f : clock_ - case_selected_at_, fonts);')
    s=exactly(s,'list.image(it.cover, rect, gfx::kCanvasUv, kWhite.with_alpha(0.82f), 22);',
                 '''if(it.cover) {
                    list.image(it.cover,rect,
                               it.cover_is_image ? gfx::kFullUv : gfx::kCanvasUv,
                               kWhite.with_alpha(0.82f),22);
                } else {
                    // During idle-only streaming, unprocessed games must
                    // occupy visible shelf cards rather than empty holes.
                    // This is a neutral title card, NOT a loading screen.
                    list.rounded_rect(rect,22,it.dark);
                    list.bordered_rect(rect,22,
                        Color::rgb(0x000000,0.0f),1.5f,it.accent.with_alpha(0.55f));
                    ui::text(list,fonts.semibold,it.genre,
                             rect.x+16,rect.y+34,17,kWhite.with_alpha(0.63f));
                    ui::paragraph(list,fonts.semibold,it.title,
                                  rect.x+15,rect.y+85,19,rect.w-30,24,kWhite,3);
                }''')
    # Focused game tile is itself the animated physical PS4/PS5 case, not a
    # splash screen or a new loader. Unfocused tiles remain native flat icons;
    # homebrew titles always retain their app icon.
    s=exactly(s,'list.image(it.cover, ring, gfx::kCanvasUv, kWhite, 26);',
                 'list.image(it.cover, ring, it.cover_is_image ? gfx::kFullUv : gfx::kCanvasUv, kWhite, 26);')
    # Reset the case's on-card animation on each D-pad/stick focus change.
    s=exactly(s,'                shelf.column = next;',
                 '                shelf.column = next;\n                case_selected_at_ = clock_;')
    s=exactly(s,'                row_ = next;',
                 '                row_ = next;\n                case_selected_at_ = clock_;')
    s=exactly(s,'    bool top_focus_ = false;',
                 '    bool top_focus_ = false;\n    float case_selected_at_ = 0.0f;')
    s=exactly(s,'            row_ = active_tab_ == 2 && shelves_.size() > 1 ? 1 : 0;',
                 '            row_ = active_tab_ == 2 && shelves_.size() > 1 ? 1 : 0;\n            case_selected_at_ = clock_;')
    # The details sheet displays the same selected-game case in place of the
    # square app icon. No loading page, timer, or launch handoff is introduced.
    s=exactly(s,'list.image(it.cover, art, gfx::kCanvasUv, kWhite, 28);',
                 'list.image(it.cover, art, it.cover_is_image ? gfx::kFullUv : gfx::kCanvasUv, kWhite, 28);')
    s=exactly(s,'#include "niak/profile.hpp"', '#include "niak/profile.hpp"\n#include "niak/case_renderer.hpp"\n#include "niak/asset_stats.hpp"')
    s=exactly(s,'        if (focused_item() != shown_)',
              '        niak::case_media_stats.preferred_index=focused_item();\n'
              '        if (focused_item() != shown_)')
    # Show the authentic clear logo when LaunchBox provided one, AND the title.
    # Keep the name readable even if the logo scan has transparent margins.
    s=exactly(s,'ui::text(list, fonts.display, it.title, x - 4, 304, 88, kWhite);',
       '''if (it.logo_art)
            list.image(it.logo_art, {x + 460, 220, 300, 85}, gfx::kFullUv, kWhite);
        ui::text(list, fonts.display, it.title, x - 4, 304, 88, kWhite);''')
    # Keep the long title inside the available left column.
    s=exactly(s,'ui::text(list, fonts.display, it.title, x - 4, 304, 88, kWhite);',
        'ui::paragraph(list, fonts.display, it.title, x - 4, 285, '
        '66, 1110, 73, kWhite, 2);')
    # The glyph sits on the left of the 220px-wide button; center the label
    # in the remaining area, not at the old left-aligned English text position.
    s=exactly(s,'''ui::text(list, fonts.semibold, it.title_id[0] ? "Jouer" : "Indisponible", play.x + 72,
                 play.cy() + 10, 28, Color::rgb(0x0b0d16));''',
                 '''ui::text(list, fonts.semibold, it.title_id[0] ? "Jouer" : "Indisponible",
                 play.x + 132, play.cy() + 10, 28, Color::rgb(0x0b0d16),
                 gfx::Align::center);''')
    translations={
        '"DETECTE SUR CETTE CONSOLE"':'"DÉTECTÉ SUR CETTE CONSOLE"',
        '"ACCES AU CATALOGUE A VERIFIER"':'"ACCÈS AU CATALOGUE À VÉRIFIER"',
        '"Reglages" : "Multimedia"':'"Réglages" : "Multimédia"',
        '"Acces aux captures PS5 non encore autorise depuis ce titre. "':'"Accès aux captures PS5 non encore autorisé depuis ce titre. "',
        '"Animations reduites"':'"Animations réduites"',
        '"OUVRIR LE SYSTEME"':'"QUITTER NIAKPS5"',
        '"Les reglages de la console restent geres par Sony. "':'"Les réglages de la console restent gérés par Sony. "',
        '"Le dernier choix quitte NiakPS5 pour y acceder. "':'"Le dernier choix revient à Sony, sans ouvrir les paramètres. "',
        '"Croix : modifier  /  Haut : barre de navigation  /  Rond : retour"':'"Croix : modifier  /  Haut : navigation  /  Rond : retour"',
    }
    s=s.replace("Resolution d'affichage (redemarrage)","Résolution d'affichage (redémarrage)")
    s=s.replace("Retour a l'accueil Sony / parametres PS5","Quitter vers l'accueil Sony")
    for a,b in translations.items():
        if a in s:s=s.replace(a,b)
    s=s.replace('"Bibliotheque PS5"','"Bibliothèque PS5"')
    s=s.replace('"Aucune photo ou video personnelle"','"Aucune photo ou vidéo personnelle"')
    s=s.replace('"Rond : revenir aux onglets"','"Rond : revenir aux onglets"')
    # Upstream UI fallback hints must never leak through if staging changes.
    s=s.replace('ui::Button::cross, "Choose"', 'ui::Button::cross, "Choisir"')
    s=s.replace('ui::Button::circle, "Back"', 'ui::Button::circle, "Retour"')
    s=s.replace('"Remove from favorites"', '"Retirer des favoris"')
    s=s.replace('"Add to favorites"', '"Ajouter aux favoris"')
    s=s.replace('"Resume"', '"Reprendre"')
    s=s.replace('"Play"', '"Jouer"')
    s=s.replace('"Close"', '"Fermer"')
    if ('ui::Button::cross, "Choose"' in s or
            'ui::Button::circle, "Back"' in s):
        raise RuntimeError("English DualSense hint remains in generated UI")
    s=s.replace('"Details"','"Détails"')
    s=s.replace('"Profil non lie"','"Profil non lié"')
    p.write_text(s,"utf-8")
    print("Polished UI: full-UV PS5 covers, working up navigation, French glyphs and aligned Jouer")

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--kit",type=Path,required=True)
    patch(p.parse_args().kit)
