# NiakPS5

Accueil graphique **expérimental** pour PS5 jailbreakée (titre `PPSA99386`), développé sur la **seule branche `main`**. Ce dépôt fournit un titre natif plein écran basé sur OpenGL, et non un ancien lanceur SDL Payload Manager.

## État des fonctionnalités

| Fonction | État |
| --- | --- |
| Interface native OpenGL et navigation DualSense | Testées sur la console de développement ; L1/R1 changent les onglets |
| Catalogue via ShadowMountPlus 1.7 sur `127.0.0.1:10101` | Découverte des identifiants confirmée sur la console |
| Véritables icônes de jeux | Intégrées avec `GET /api/v1/games/icon`, **validation console en attente** |
| Noms des jeux | API ShadowMountPlus + `app.db` en lecture seule quand accessible, certains titres peuvent encore afficher l'ID |
| Nom du profil local PS5 | Requête UserService, **validation console en attente** |
| Avatar PS5 | Copie locale PNG/DDS liée au profil actif ; masqué si le profil change sans relance ; **validation sur console en attente** |
| Réglages NiakPS5 | Fonctionnels, configurent seulement l'application |
| Réglages système Sony | **Non intégrés** : accessibles via le Control Center/accueil d'origine |
| Médias personnels/captures | **Non activés**, confidentialité par défaut |
| Bouton PS | Toujours géré par `SceShellUI` ; aucune interception ni remplacement du shell |
| Service « Jouer » | Courtier local PLDmgr sur `127.0.0.1:19187`, protocole et autorisations testés sur hôte ; **lancement sur console non validé** |
| Démarrage automatique | Installation du payload compagnon et de PLDmgr via le script FTP ; **validation matérielle 13.60 en attente** |
| Retour optionnel après jeu | Déclenché seulement après une demande « Jouer » acceptée ; attente monotone de 10 s, même si NiakPS5 a été ouvert manuellement ; **validation console en attente** |
| Boîtiers PS4/PS5 3D | Recto/tranche/verso et reconstitution lorsque les scans privés sont absents ; rendu contrôlé par captures OpenGL, **validation console en attente** |
| Fonds jeux récents | Sélection quotidienne dans un lot Steam préparé à la compilation ; pas de téléchargement live PS5 |

Les validations GitHub prouvent les tests hôte, la compilation native et les captures OpenGL sur Mesa, **pas** le lancement des jeux ni la compatibilité matérielle sur une console PS5 13.60. Une demande de lancement acceptée n'est pas une preuve que le jeu a réellement démarré.

## Navigation et fond d'écran

**L1/R1** naviguent entre NIAK, Jeux, Multimédia et Réglages. Ils ne changent jamais le fond.
Le fond d'écran est sélectionné automatiquement selon la date locale (une sélection
par jour). **Réglages → Changer le fond du jour** permet de forcer une autre image
pour la journée ; aucune autre commande ne déclenche cette action.

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

**Téléchargement GitHub Actions :** prends l'artefact **`NiakPS5-PPSA99386`**.
GitHub le télécharge directement comme **une seule archive ZIP** contenant
`PPSA99386/eboot.bin`, `PPSA99386/sce_sys/`, etc. Il n'y a plus de
`PPSA99386.zip` à l'intérieur : une seule extraction suffit.

**Compilation locale :** `bash native/title/build.sh` produit également
`dist/PPSA99386.zip`, déjà au même format. Le workflow vérifie cette archive
et ses permissions, puis retire le fichier ZIP interne avant de laisser GitHub
compresser le dossier d'installation dans son unique artefact.

Le payload `tools/niakps5.elf` est **distinct** de l'application graphique : il peut demander l'ouverture du titre **une fois après le jailbreak**. Il n'est pas exécuté automatiquement du seul fait d'avoir extrait le ZIP. L'installation FTP complète se fait depuis un ordinateur connecté au réseau local de la PS5 avec :

```bash
python3 PPSA99386/tools/ftp_install.py --host IP_PS5 --port 2121 --autoload
```

Le script copie également `tools/niakps5.elf` dans `/data/pldmgr/payloads/niakps5/niakps5.elf` et préserve/sauvegarde `/data/pldmgr/autoload.txt`. Par défaut, l'installateur configure aussi l'autoload. Avec `--no-autoload`, seule l'application est copiée. Voir [documentation détaillée](native/title/README.md).

L'autoload **ne remplace pas** `SceShellUI`. Le bouton PS et les fonctions système Sony continuent d'être contrôlés par la console. Un redémarrage ou une désactivation de l'autoload restaure le comportement d'origine.

## Construire et tester

```bash
python3 -m unittest discover -s native/title/tests -p 'test_*.py'
bash native/title/build.sh
```

L'assemblage récupère une révision figée de [PS5_VKHomebrewUI](https://github.com/mihawk-99/PS5_VKHomebrewUI), prépare la version NiakPS5, compile et crée `dist/PPSA99386.zip`.

Les polices Manrope et Instrument Serif sont utilisées avec leurs licences OFL. Le décodeur PNG tiers (LodePNG) conserve sa licence dans ses sources. La base graphique amont reste GPL-3.0-or-later.

## Diagnostics du catalogue

Le payload initialise UserService avant de demander le profil actif (erreur
`0x80960002` corrigée à la source), identifie son thread `NiakPS5`
sur les chargeurs compatibles et reconnaît un courtier déjà en service.
Les requêtes `GAMES` journalisent le nombre d'identifiants accessibles.

Si toutes les sources en direct restent inaccessibles, l'interface utilise en
dernier recours le relevé local `assets/niak-local-titles.tsv` de la dernière
installation FTP, sans prétendre que ses titres sont encore installés.
Ce fallback reste à vérifier sur PS5 13.60.

## Confidentialité et sécurité

Le dépôt ne doit contenir **aucune** adresse personnelle ou IP privée, identifiant de compte, mot de passe FTP, clé API, capture privée ou base de données de la console. Les accès catalogue et icônes passent par une API **loopback** qui doit rester liée à `127.0.0.1` ; aucune donnée de profil n'est envoyée sur Internet. Les captures personnelles ne sont ni collectées ni transférées.

Les outils de packaging n'écrivent pas dans `/system` ni `/system_ex` et ne remplacent pas le processus `SceShellUI`. Ne pas ajouter de hook expérimental du bouton PS au démarrage. Un nettoyage du contenu courant du dépôt ne purge pas automatiquement son historique Git : toute information sensible détectée dans l'historique nécessiterait un traitement distinct.
