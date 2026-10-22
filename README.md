# NiakPS5

Accueil graphique **expérimental** pour PS5 jailbreakée (titre `PPSA99386`), développé sur la **seule branche `main`**. Ce dépôt fournit un titre natif plein écran basé sur OpenGL, et non un ancien lanceur SDL Payload Manager.

## État des fonctionnalités

| Fonction | État |
| --- | --- |
| Interface native OpenGL et navigation DualSense | Testées sur la console de développement |
| Catalogue via ShadowMountPlus 1.7 sur `127.0.0.1:10101` | Découverte des identifiants confirmée sur la console |
| Véritables icônes de jeux | Intégrées avec `GET /api/v1/games/icon`, **validation console en attente** |
| Noms des jeux | API ShadowMountPlus + `app.db` en lecture seule quand accessible, certains titres peuvent encore afficher l'ID |
| Nom du profil local PS5 | Requête UserService, **validation console en attente** |
| Avatar PS5 | Copie locale PNG/DDS liée au profil actif ; **validation sur console en attente** |
| Réglages NiakPS5 | Fonctionnels, configurent seulement l'application |
| Réglages système Sony | **Non intégrés** : accessibles via le Control Center/accueil d'origine |
| Médias personnels/captures | **Non activés**, confidentialité par défaut |
| Bouton PS et retour après jeu | Gestion par `SceShellUI` ; pas de remplacement vérifié |
| Fonds jeux récents | Sélection quotidienne dans un lot Steam préparé à la compilation ; pas de téléchargement live PS5 |

Les tests CI prouvent la compilation et les contrats logiciels, **pas** la compatibilité matérielle de chaque fonctionnalité.

## Un seul ZIP FTP

```text
PPSA99386.zip
└── PPSA99386/
    ├── eboot.bin
    ├── sce_sys/
    ├── sce_module/
    ├── assets/
    └── tools/
        ├── niakps5.elf
        ├── ftp_install.py
        └── AUTOSTART.md
```

Aucune archive imbriquée. Le dossier `PPSA99386` s'installe sous `/data/homebrew/PPSA99386`.

Le payload `tools/niakps5.elf` est **distinct** de l'application graphique : il peut demander l'ouverture du titre **une fois après le jailbreak**. Il n'est pas exécuté automatiquement du seul fait d'avoir extrait le ZIP. Après avoir vérifié le fonctionnement manuel du titre, l'installation FTP peut être réalisée sur PC avec :

```bash
python3 PPSA99386/tools/ftp_install.py --host IP_PS5 --port 2121 --autoload
```

Le script copie également `tools/niakps5.elf` dans `/data/pldmgr/payloads/niakps5/niakps5.elf` et préserve/sauvegarde `/data/pldmgr/autoload.txt`. Sans `--autoload`, seule l'application est copiée. Voir [documentation détaillée](native/title/README.md).

L'autoload **ne remplace pas** `SceShellUI`. Le bouton PS et les fonctions système Sony continuent d'être contrôlés par la console. Un redémarrage ou une désactivation de l'autoload restaure le comportement d'origine.

## Construire et tester

```bash
python3 -m unittest discover -s native/title/tests -p 'test_*.py'
bash native/title/build.sh
```

L'assemblage récupère une révision figée de [PS5_VKHomebrewUI](https://github.com/mihawk-99/PS5_VKHomebrewUI), prépare la version NiakPS5, compile et crée `dist/PPSA99386.zip`.

Les polices Manrope et Instrument Serif sont utilisées avec leurs licences OFL. Le décodeur PNG tiers (LodePNG) conserve sa licence dans ses sources. La base graphique amont reste GPL-3.0-or-later.

## Confidentialité et sécurité

Le dépôt ne doit contenir **aucune** adresse personnelle ou IP privée, identifiant de compte, mot de passe FTP, clé API, capture privée ou base de données de la console. Les accès catalogue et icônes passent par une API **loopback** qui doit rester liée à `127.0.0.1` ; aucune donnée de profil n'est envoyée sur Internet. Les captures personnelles ne sont ni collectées ni transférées.

Les outils de packaging n'écrivent pas dans `/system` ni `/system_ex` et ne remplacent pas le processus `SceShellUI`. Ne pas ajouter de hook expérimental du bouton PS au démarrage. Un nettoyage du contenu courant du dépôt ne purge pas automatiquement son historique Git : toute information sensible détectée dans l'historique nécessiterait un traitement distinct.
