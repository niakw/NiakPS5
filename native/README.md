# NiakPS5 — lanceur natif PS5

## État réel

Cette branche ajoute un **lanceur SDL2 plein écran**, distinct de la maquette web et conçu pour devenir l'accueil quotidien d'une PS5 jailbreakée. Il scanne la base d'applications PS5 **en lecture seule** et permet, via la touche croix, d'appeler l'API native de lancement d'un jeu installé.

Il **ne remplace pas encore le processus système** \`SceShellUI\`. La touche PS, les menus système protégés, les notifications et les réglages Sony restent gérés par le firmware. Aucun patch permanent, remplacement de fichier système, écriture dans \`app.db\`, injection de processus ou enregistrement forcé comme shell système.

### Architecture

\`\`\`text
WebKit autoloader / elfldr (après jailbreak)
                 |
      niakps5_diagnostic.elf (prévalidation sans lancement)
                 | présence fichiers / notification / log
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

**Sortie de secours, uniquement si l'interface native peut démarrer :** touche rond ferme l'application et revient normalement à l'accueil Sony. Comportement encore non validé sur PS5 13.60. Il n'existe **aucun** mécanisme d'autodémarrage qui persiste au redémarrage du firmware sans l'environnement de jailbreak.

## Choix du moteur

L'audit des [trois kits d'interface OpenGL/Vulkan](ENGINE.md) a identifié la séparation moteur/UI/plateforme comme direction. Le code comporte désormais des modules de rendu SDL accéléré si disponible, de cache texture et de navigation animée. **Ce n'est pas encore le backend OpenGL/Vulkan des références** ; le port GPU dédié reste à réaliser.

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

## Installation de diagnostic (réversible)

**Voir [DIAGNOSTIC.md](DIAGNOSTIC.md).** L'archive PS5 ne contient plus l'ancien bootstrap bigapp. Installer seulement ces éléments sous `/data` :

```text
/data/pldmgr/niakps5_diagnostic.elf    <- lancer depuis Payload Manager
/data/niakps5/niakps5_ui.elf          <- vérifier sa présence
/data/niakps5/assets/manrope.ttf
/data/niakps5/assets/instrument-serif.ttf
```

Le diagnostic affiche une notification et écrit `/data/niakps5-diagnostic.log`, visible par FTP. Il ne crée pas de faux titre système, ne remonte pas `/system_ex` et ne lance pas de processus graphique.

**Important :** l'ancien bootstrap dépendait d'un chargeur `hbldr` avec mécanisme de création d'une fausse application dans `/system_ex/app/FAKE00000`, d'attachement à `SceSysCore` et parfois d'un ancien fichier PS Now. Il pouvait échouer silencieusement, ou provoquer des changements de système. Ce mécanisme n'a pas été validé sur 13.60 : **ne le relancez pas**.

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
