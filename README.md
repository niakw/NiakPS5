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
pour la journée, y compris après fermeture et réouverture de NiakPS5.
Le choix manuel est réinitialisé lors du prochain jour local ; aucune autre
commande ne déclenche cette action.

## Installation par FTP : **glisser-déposer uniquement**

Dans les artifacts du dernier run vert, télécharger **NiakPS5-PPSA99386**.
GitHub fournit une première archive ; l'extraire, puis extraire le ZIP
`NiakPS5-FTP-glisser-deposer.zip` qu'elle contient. Cette deuxième archive
conserve les droits exécutables `0755` (GitHub les efface dans la première).
On obtient un seul dossier **`data/`** :

```text
data/
├── homebrew/
│   └── PPSA99386/
│       ├── eboot.bin
│       ├── sce_sys/
│       ├── sce_module/
│       ├── assets/niak-templates/  (6 gabarits PS4/PS5 inclus)
│       └── tools/niakps5/         (payload compagnon interne)
└── pldmgr/
    └── payloads/
        └── niakps5/
            ├── niakps5.elf
            └── niakps5.elf.json
```

**Sur le FTP de la console, à la racine `/`, glisser le dossier `data/`
en choisissant FUSIONNER les dossiers existants**. Ne pas choisir une option
supprimant le dossier `data` actuel ! Aucun terminal, Python ou script
d'installation n'est nécessaire. Ne pas recopier `data/` dans `/data/`,
ce qui créerait par erreur `/data/data/`.

Le paquet **ne contient pas** `autoload.txt`, `pldmgr_config.txt` ni
de fichier système Sony : ta configuration PLDmgr existante reste intacte.
Si `niakps5.elf` est déjà inscrit dans ton autoload, son binaire est mis
à jour lors de la copie. **S'il n'est pas inscrit, le simple FTP ne peut
pas l'activer automatiquement**, et NiakPS5 ne modifiera pas ce fichier.

La présence du dossier ne garantit pas son référencement par le service de
titres PS5 : ShadowMountPlus ou le mécanisme d'enregistrement déjà en place
doit reconnaître `PPSA99386`. Les droits de lecture catalogue, l'exécution
du broker et le lancement de jeux sur firmware 13.60 restent à qualifier
sur console ; une CI verte ne peut pas les prouver.

Les 6 gabarits par défaut sont issus des éléments existants compressés pour
l'aperçu. Si tu préfères les originaux pleine résolution, **copie simplement**
les 6 PNG du ZIP privé sous
`/data/homebrew/PPSA99386/assets/niak-templates/`, puis relance l'app.
Aucune commande FTP n'est nécessaire.

L'autoload ne remplace pas `SceShellUI` ; le bouton PS reste géré par Sony.

## Construire et tester

```bash
python3 -m unittest discover -s native/title/tests -p 'test_*.py'
bash native/title/build.sh
```

L'assemblage récupère une révision figée de [PS5_VKHomebrewUI](https://github.com/mihawk-99/PS5_VKHomebrewUI), prépare la version NiakPS5, compile et crée `dist/PPSA99386.zip`.

Les polices Manrope et Instrument Serif sont utilisées avec leurs licences OFL. Le décodeur PNG tiers (LodePNG) conserve sa licence dans ses sources. La base graphique amont reste GPL-3.0-or-later.

## Installation complète sans toucher à PLDmgr

Si PLDmgr est déjà configuré, remplacer **ensemble** `eboot.bin` et
`niakps5.elf` avec la commande :
`python3 PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --preserve-autoload`.
Ce mode n'écrit pas sur `autoload.txt` ni sur la configuration PLDmgr
et ne redémarre pas les services de la console.

## Correctif du lancement automatique

Le payload qui démarre avec PLDmgr initialise UserService, lance les applications
avec le contexte du profil connecté, et utilise un fallback \`sceLncUtilLaunchApp\`
**uniquement** si l'appel \`sceSystemServiceLaunchApp\` retourne
\`0x80940005\`. Le succès du fallback est consigné avec l'identifiant
d'application. Une pulsation légère toutes les deux minutes et le PID
réel du courtier sont inscrits dans le journal :
\`/data/niakps5-autostart.log\`. Un processus autonome \`niakps5.elf\`
n'est pas garanti quand le payload est hébergé par le chargeur.

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
