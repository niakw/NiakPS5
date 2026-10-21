# NiakPS5 — lanceur natif PS5

## État réel

Cette branche ajoute un **lanceur SDL2 plein écran**, distinct de la maquette web et conçu pour devenir l'accueil quotidien d'une PS5 jailbreakée. Il scanne la base d'applications PS5 **en lecture seule** et permet, via la touche croix, d'appeler l'API native de lancement d'un jeu installé.

Il **ne remplace pas encore le processus système** \`SceShellUI\`. La touche PS, les menus système protégés, les notifications et les réglages Sony restent gérés par le firmware. Aucun patch permanent, remplacement de fichier système, écriture dans \`app.db\`, injection de processus ou enregistrement forcé comme shell système.

### Architecture

\`\`\`text
WebKit autoloader / elfldr (après jailbreak)
                 |
      niakps5_bootstrap.elf
                 | hbldr_launch (bigapp)
                 v
           niakps5_ui.elf
            /          \
    SQLite READ-ONLY   SDL2 natif + DualSense
    app.db + dossiers  palette NiakTV / focus
            \          /
           jeux installés
                 |
       sceSystemServiceLaunchApp
                 |
         jeu PS4/PS5 installé
\`\`\`

**Sortie de secours :** touche rond ferme l'application native et rend la main à l'accueil Sony. Il n'existe **aucun** mécanisme d'autodémarrage qui persiste au redémarrage du firmware sans l'environnement de jailbreak.

## Fonctionnalités natives intégrées

- Affichage SDL2 plein écran 1920 × 1080, navigation DualSense (croix, rond, carré, triangle et flèches) et clavier en environnement de développement.
- Palettes Menthe / Violet / Bleu / Graphite, typographie Manrope + Instrument Serif, lecture de l'heure, focus menthe et jaquettes des jeux installés.
- Lecture SQLite seule à \`/system_data/priv/mms/app.db\`, interrogation de \`tbl_appbrowse\`, puis chemins de repli \`tbl_appinfo\` et \`tbl_contentinfo\`.
- Filtrage CUSA/PPSA à 5 chiffres, exclusion des identifiants de shell NPXS, vérification des dossiers d'installation avant affichage, images depuis \`/user/appmeta/<TITLEID>/\` (si présentes).
- Lancement via \`sceSystemServiceLaunchApp\` uniquement sur un identifiant validé et présent dans la bibliothèque détectée.
- Pas de privilèges demandés pour le scanner SQLite lui-même ; l'élévation du bootstrap est celle requise par le mécanisme bigapp et est à valider sur le firmware cible.

## Compiler

**Prérequis PS5 :** SDK compatible PacBrew ayant SDL2, SDL2_image, SDL2_ttf, les bibliothèques SCE et les en-têtes FreeBSD. Le \`ps5-payload-sdk\` de base peut ne pas comprendre toutes les bibliothèques multimédias ; la construction native nécessite cette variante.

\`\`\`sh
export PS5_PAYLOAD_SDK=/chemin/vers/ps5-payload-sdk-pacbrew
cd native
./fetch-sqlite.sh
make
\`\`\`

Les deux exécutables attendus, une fois la compilation croisée réussie, sont :
- \`native/build/niakps5_bootstrap.elf\` : celui que charge le WebKit autoloader / elfldr.
- \`native/build/niakps5_ui.elf\` : l'interface graphique à copier sur le stockage.

Cette compilation **n'a pas encore été validée sur console**, et aucune compatibilité précise PS5 13.60 ne doit être présumée avant essais réels.

## Installation expérimentale et réversible

**Ne pas activer d'autostart avant de réussir un lancement manuel.** Exiger un jailbreak opérationnel et le Homebrew Launcher PKG compatible avec \`hbldr\`, comme pour Nativehbl.

1. Copier par FTP **uniquement** les fichiers du lanceur vers :
   - \`/data/niakps5_bootstrap.elf\`
   - \`/data/niakps5/niakps5_ui.elf\`
   - \`/data/niakps5/assets/manrope.ttf\`
   - \`/data/niakps5/assets/instrument-serif.ttf\`
2. Charger \`/data/niakps5_bootstrap.elf\` avec le gestionnaire de payloads ou le chargeur ELF déjà fonctionnel (il doit lancer le bigapp graphique).
3. Tester : jaquettes, liste des jeux réellement installés, navigation et ouverture d'un jeu.
4. Vérifier le retour à l'accueil Sony via **rond**, sans redémarrage ou plantage.
5. **Après validation uniquement**, configurer le chemin du bootstrap dans l'autoloader que vous utilisez, avec délai pour laisser etaHEN/loader initialiser ses services. Garder une méthode de désactivation de l'autoloader.

### Restauration

Désactiver l'entrée autoloader NiakPS5 ou ne plus charger le bootstrap ELF. L'application native ne modifie pas le shell Sony. Aucun désinstalleur système n'est nécessaire. Les seuls fichiers NiakPS5 créés sont les fichiers copiés par l'utilisateur dans \`/data/niakps5/\` et le bootstrap dédié.

## Validation

\`\`\`sh
# Ubuntu / CI : logique de catalogue avec base SQLite factice
sudo apt-get install libsqlite3-dev
cc -std=c11 -Wall -Wextra -Werror -I native native/catalog.c native/tests/catalog_test.c -lsqlite3 -o /tmp/niak-catalog-test
/tmp/niak-catalog-test
\`\`\`

CI hôte : vérifie les filtres de titre, la lecture seule, les chemins de jeux, l'absence de faux installés et la compilation statique de l'interface. **Ne valide pas le lancement ni les hooks PS5.**

## Crédits

Le bootstrap utilise le backend \`hbldr\` GPL-3.0 de John Törnblom, récupéré du projet [Rufidj/Nativehbl](https://github.com/Rufidj/Nativehbl), issu de [ps5-payload-dev/websrv](https://github.com/ps5-payload-dev/websrv). Les fichiers tiers originaux sont conservés sous \`native/gpl/\` avec leur attribution. \`sqlite3.c\` est téléchargé depuis un commit verrouillé de \`itsPLK/ps5-pkg-manager\` (SQLite domaine public). L'interface et la logique de catalogue sont originales, sous GPL-3.0-or-later. Respectez les licences des polices et des illustrations.

**Point à investiguer :** un accès à l'API native de la PS5 ne prouve pas le succès du lancement depuis un processus bigapp sur 13.60. La fonctionnalité doit encore être testée matériellement.
