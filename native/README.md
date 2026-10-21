# NiakPS5 — véritable accueil graphique, en application PS5

## Ce que l'on installe

**Un seul dossier de titre**, et non plusieurs ELF de Payload Manager :

```text
/data/homebrew/PPSA99386/
    eboot.bin
    sce_sys/param.json
    sce_sys/icon0.png
    sce_module/libc.prx
    assets/...
```

L'installation est analogue aux titres Homebrew UI Lab et PS5LM : le titre est ajouté au menu Sony par **ShadowMountPlus**, puis s'ouvre en plein écran avec OpenGL natif et le DualSense.

**Important : l'expérience visuelle NiakPS5 peut devenir ton accueil habituel de la session homebrew, mais ce dossier ne remplace pas `SceShellUI`, les écrans de sécurité Sony ou le bouton PS.** Le retour Home et les autres fonctions système demeurent gérés par la PS5. Les exemples de kits ne constituent pas une preuve de remplacement du processus `SceShellUI`.

Le code est une adaptation GPL-3.0-or-later du kit [mihawk-99/PS5_VKHomebrewUI](https://github.com/mihawk-99/PS5_VKHomebrewUI) au commit épinglé `2188642afbcc8d84d36149124f3d9e39dc1b1a05`, dont le rendu OpenGL vient de BlackBearReloaded. Le dossier de compilation conserve ses notices/licences et la base vidéo/contrôleur vérifiée par l'amont.

## Architecture

- `native/title/build.sh` récupère un **commit exact** du moteur GPU PS5, dans un dossier temporaire ignorant les sources du projet.
- `native/title/prepare.py` prépare **une seule** variante Aurora Shelf appelée NiakPS5, avec des onglets Niak/Jeux/Multimédia/Réglages et la palette menthe.
- Le catalogue de démonstration amont est **remplacé** par notre scanner `native/catalog.c`, utilisant SQLite en lecture seule. S'il n'est pas autorisé à accéder à `/system_data/priv/mms/app.db` depuis le sandbox natif, l'interface affiche clairement « Bibliothèque indisponible », **pas de jeux inventés**.
- Une sélection de jeu valide peut appeler `sceSystemServiceLaunchApp`. Ce lancement depuis un titre concurrent reste à vérifier sur le firmware 13.60 et l'échec est journalisé.
- Pour l'instant, la pochette est **procédurale** avec le titre réel, pas encore une jaquette `icon0.png` importée. Le moteur permet l'upload de textures ; cette étape reste à intégrer après le premier test de la base graphique.

## Construire sur Linux

La compilation GPU est distincte du précédent workflow ELF et demande les dépendances officielles du moteur :

```sh
bash native/title/build.sh
# donne dist/NiakPS5-title-PPSA99386.zip
```

Elle télécharge les dépendances épinglées et peut prendre du temps. La source est GPL ; conserver les notices des dépendances et respecter les licences.

## Installer sur PS5 13.60

1. Conserver ton environnement jailbreak normal, avec **ShadowMountPlus** actif.
2. Copier par FTP le **dossier entier** `PPSA99386` dans `/data/homebrew/`. Ne pas déposer `eboot.bin` dans `/data/pldmgr/`.
3. Laisser ShadowMountPlus enregistrer le titre ; si nécessaire, relancer son mécanisme d'enregistrement suivant sa documentation.
4. Lancer **NiakPS5** depuis son icône dans l'accueil Sony. Tester d'abord l'ouverture, le focus DualSense et le retour Sony.
5. Avant d'utiliser le bouton de lancement d'un jeu, vérifier que la liste ne contient que les titres réellement installés.

Ne pas supprimer ni remplacer `SceShellUI`, ne pas remonter `/system_ex` en écriture, ne pas réactiver l'ancien bootstrap `hbldr`.

## Limites à valider

- Compilation et runtime de **cette adaptation** sur PS5 firmware 13.60 : **non validés matériellement**.
- Accès à `app.db` depuis un titre sandboxé : inconnu ; la version originale du scanner a été validée seulement sur PC.
- Retour et lancement PS4/PS5 : non prouvés ; une permission ou un service hôte peut être nécessaire.
- Le moteur GPU doit être testé avec l'intégralité des bibliothèques embarquées sur cette console avant d'en faire un accueil par défaut.
- La priorité suivante est une source réelle de jaquettes et une procédure d'autolancement facultative, seulement si sûre et réversible.
