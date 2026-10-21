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
    s=exactly(s,'const char *tabs[] = {"NIAK", "Jeux", "Multimedia", "Reglages"};',
                 'const char *tabs[] = {"NiakPS5", "Jeux", "Multimédia", "Réglages"};')
    # Up only selects the top bar from the FIRST row. From Homebrew row 1 it
    # must move back to row 0, working with both D-pad and left joystick.
    s=exactly(s,'else if (input.nav == Direction::up || input.is_pressed(Action::menu))',
                 'else if ((input.nav == Direction::up && row_ == 0) || input.is_pressed(Action::menu))')
    # Procedural covers are FBO textures (bottom-left); actual PS5 PNG images
    # are uploaded top-row-first and REQUIRE kFullUv. kCanvasUv flips the PNG.
    s=exactly(s,'list.image(it.cover, art, gfx::kCanvasUv, kWhite, 36);',
                 'list.image(it.cover, art, it.cover_is_image ? gfx::kFullUv : gfx::kCanvasUv, kWhite, 36);')
    s=exactly(s,'list.image(it.cover, rect, gfx::kCanvasUv, kWhite.with_alpha(0.82f), 22);',
                 'list.image(it.cover, rect, it.cover_is_image ? gfx::kFullUv : gfx::kCanvasUv, kWhite.with_alpha(0.82f), 22);')
    s=exactly(s,'list.image(it.cover, ring, gfx::kCanvasUv, kWhite, 26);',
                 'list.image(it.cover, ring, it.cover_is_image ? gfx::kFullUv : gfx::kCanvasUv, kWhite, 26);')
    s=exactly(s,'list.image(it.cover, art, gfx::kCanvasUv, kWhite, 28);',
                 'list.image(it.cover, art, it.cover_is_image ? gfx::kFullUv : gfx::kCanvasUv, kWhite, 28);')
    # The glyph sits on the left of the 220px-wide button; center the label
    # in the remaining area, not at the old left-aligned English text position.
    s=exactly(s,'''ui::text(list, fonts.semibold, it.title_id[0] ? "Jouer" : "Indisponible", play.x + 72,
                 play.cy() + 10, 28, Color::rgb(0x0b0d16));''',
                 '''ui::text(list, fonts.semibold, it.title_id[0] ? "Jouer" : "Indisponible",
                 play.x + 146, play.cy() + 10, 28, Color::rgb(0x0b0d16),
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
    p.write_text(s,"utf-8")
    print("Polished UI: full-UV PS5 covers, working up navigation, French glyphs and aligned Jouer")

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--kit",type=Path,required=True)
    patch(p.parse_args().kit)
