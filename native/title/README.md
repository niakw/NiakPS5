# NiakPS5 — véritable accueil graphique, en application PS5

### Enregistrement du titre (erreur 0x80940005)

Le diagnostic FTP `--status` vérifie désormais `sce_sys/param.json` et
les chemins `scanpath=` dans `/data/shadowmount/config.ini`, en **lecture
seule**. Il interroge aussi une **copie SQLite en mémoire** de
`/system_data/priv/mms/app.db`, sous une limite de 64 Mio. Un résultat
inaccessible ou un schéma inconnu reste « indéterminé » ; l'outil n'écrit
jamais dans app.db. Si des chemins personnalisés sont configurés et excluent
`/data/homebrew`, ShadowMountPlus ne découvrira pas `PPSA99386` à cet
emplacement. La présence de fichiers et un param.json valide ne prouvent
pas à eux seuls que le titre a été enregistré. NiakPS5 ne modifie jamais
automatiquement la configuration ShadowMountPlus.

## Récupération de la bibliothèque après le démarrage

Si le service de lancement PLDmgr arrive après la création de l'interface, un
catalogue initialement « Bibliothèque indisponible » peut maintenant récupérer
automatiquement la liste des identifiants installés. La vérification est bornée
et espacée (une tentative sur 600 images au plus, lorsque la manette est
inactive). Si le courtier transmet des titres, NiakPS5 reconstruit ses
rayons et recharge progressivement leurs visuels, **sans** redémarrer le
titre ni modifier la base de données Sony. L'inventaire reste limité aux
identifiants validés ; un titre absent des sources n'est pas inventé.

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
# donne dist/PPSA99386.zip
```

Elle télécharge les dépendances épinglées et peut prendre du temps. La source est GPL ; conserver les notices des dépendances et respecter les licences.

## Installer sur PS5 13.60

1. Conserver ton environnement jailbreak normal, avec **ShadowMountPlus** actif.
2. Copier par FTP le **dossier entier** `PPSA99386` dans `/data/homebrew/`. Ne pas déposer `eboot.bin` dans `/data/pldmgr/`.
3. **Une fois pour toutes**, copier le dossier fourni `PPSA99386/tools/niakps5/`
   sous `/data/pldmgr/payloads/`, avec `niakps5.elf` **et** `niakps5.elf.json`.
   Ajouter `niakps5.elf` en **dernière ligne** de `/data/pldmgr/autoload.txt`
   après BFpilot. Ne pas toucher aux cinq autres lignes. Le lancement via
   WebKit autoloader + PLDmgr reste inchangé ; aucun script n'est requis.
   L'inscription initiale dans autoload.txt ne peut pas être provoquée par
   une copie passive du seul dossier de l'application.
3. Laisser ShadowMountPlus enregistrer le titre ; si nécessaire, relancer son mécanisme d'enregistrement suivant sa documentation.
4. Lancer **NiakPS5** depuis son icône dans l'accueil Sony. Tester d'abord l'ouverture, le focus DualSense et le retour Sony.
5. Avant d'utiliser le bouton de lancement d'un jeu, vérifier que la liste ne contient que les titres réellement installés.

Ne pas supprimer ni remplacer `SceShellUI`, ne pas remonter `/system_ex` en écriture, ne pas réactiver l'ancien bootstrap `hbldr`.

## Lancement des titres enregistrés

NiakPS5 n'utilise plus un contexte de lancement \`NULL\` systématique.
Le payload transmet une structure \`LncAppParam\` validée, avec utilisateur
actif. En cas de refus exact \`0x80940005\`, il tente une seule fois
\`sceLncUtilLaunchApp\` pour l'application demandée. Cela n'accorde pas
de nouveaux privilèges au processus graphique et ne remplace ni une
installation ni l'enregistrement du titre. Le journal distingue les deux
codes de retour, indique le PID du courtier, et émet un heartbeat toutes
les deux minutes lorsque le service reste actif.

## Mise à jour sans réécriture de PLDmgr

Lorsque la chaîne d'autoload est déjà configurée, utiliser
`python3 PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --preserve-autoload`.
Ce mode installe l'interface et la nouvelle version du payload `niakps5.elf`
avec son sidecar, mais ne réécrit ni `autoload.txt`, ni la configuration
PLDmgr, ni les marqueurs de démarrage. Le mode normal évite également
de réécrire une configuration PLDmgr inchangée.

## Résolution des erreurs de démarrage et du catalogue

L'ELF PLDmgr initialise explicitement UserService avant de demander le profil
au premier plan. L'erreur `0x80960002` correspondait au service non initialisé ;
la réponse `UserService initialize` apparaît dans le journal du payload.
Le payload nomme son thread `NiakPS5` avec `SYS_thr_set_name`, sous réserve
des capacités du chargeur. Il ne tue pas une première instance active : un
second lancement reconnaît `PING/PONG` et quitte sans réoccuper le port.

Si l'accès à app.db, au courtier ou à ShadowMountPlus est refusé, NiakPS5
peut utiliser en **dernier recours** le fichier privé
`assets/niak-local-titles.tsv` préparé par l'installateur FTP. Les vignettes
sont alors marquées « Dernier inventaire local » : une ancienne observation
FTP ne prouve **pas** qu'un jeu reste installé ou lançable. Relancer
l'installation FTP actualise ce relevé, sans modifier la base Sony.

## Limites à valider

- Compilation et runtime de **cette adaptation** sur PS5 firmware 13.60 : **non validés matériellement**.
- Accès à `app.db` depuis un titre sandboxé : inconnu ; la version originale du scanner a été validée seulement sur PC.
- Retour et lancement PS4/PS5 : non prouvés ; une permission ou un service hôte peut être nécessaire.
- Le moteur GPU doit être testé avec l'intégralité des bibliothèques embarquées sur cette console avant d'en faire un accueil par défaut.
- La priorité suivante est une source réelle de jaquettes et une procédure d'autolancement facultative, seulement si sûre et réversible.

## Constat à partir d'un inventaire FTP (21 octobre 2026)

Les relevés fournis pour la console de test confirment l'existence de `/data/homebrew` et d'au moins un dossier de titre avec `eboot.bin`, `sce_sys/param.json` et `sce_module/libc.prx`. Ils montrent également un payload ShadowMountPlus dans `/data/pldmgr/payloads` et un cache d'icônes sous `/data/shadowmount`. Ils **ne prouvent pas** que le payload soit chargé, que NiakPS5 puisse lire ces chemins depuis son sandbox, ou que `/system_data/priv/mms/app.db` soit accessible ; ce dernier dossier n'a pas été parcouru dans l'inventaire.

Chemins connus pour une future **galerie locale, sur autorisation expresse** : `/user/av_contents/photo`, `/user/av_contents/video`, `/user/av_contents/thumbnails/photo` et `/user/av_contents/thumbnails/video`. Ces médias sont privés : pas de scan, pas de miniature ouverte, pas de téléversement ni de suppression automatique à ce stade.

NiakPS5 ne touche pas à `/system_tmp/shadowmount.sock`, aux bases de journalisation, caches système, profils, sauvegardes, clés, ni au marqueur `/data/.kstuff_noautomount`. L'inventaire FTP ne permet pas d'inférer leur fonction ou leur caractère supprimable. Ces constats valent pour une console testée, **pas** pour tous les firmwares.

La découverte de titres sur supports externes (`/mnt/usb*/homebrew`, `/mnt/ext*/homebrew`) reste à qualifier sur console ; aucun montage externe de ce type n'a été vérifié dans l'inventaire.

## Démarrage automatique (au lieu de choisir la tuile)

Consulter [AUTOSTART.md](AUTOSTART.md). Le payload auxiliaire demande l'ouverture du titre automatiquement **après la chaîne de jailbreak**, avec opt-in et désactivation. Ce n'est pas une modification ou substitution de `SceShellUI` et ce mécanisme n'est pas encore validé en 13.60. Ne pas l'activer tant que le lancement manuel du nouveau titre n'est pas validé.

## API locale ShadowMountPlus (fallback pour les permissions)

Le titre tente maintenant `POST http://127.0.0.1:10101/api/v1/games` en lecture seule avant de réunir les résultats avec app.db et /data/homebrew. Le client HTTP est borné à 2 Mio, boucle locale uniquement et délais de réception limités ; il ne demande aucun scan, montage, suppression, élévation ni changement de configuration. Cela nécessite une version de ShadowMountPlus qui expose déjà cette API (documentée dans la série 1.7). En l'absence de serveur, on conserve les autres méthodes et l'état explicite « indisponible » ; aucune donnée de la bibliothèque n'est envoyée sur Internet.

## Fonds de jeux récents : état précis

`fetch_daily_games.py` exploite l'API **Steam Store** au moment de la compilation pour trouver des jeux réellement sortis depuis moins de 365 jours, récupérer au maximum sept captures horizontales et les préparer dans les assets de l'application. Aucun identifiant personnel de PS5 n'est envoyé. Une rotation fondée sur la date locale choisit une image par jour ; l'aurore/fumée reste présente et sert de fallback si les ressources n'existent pas. La CI reconstruit le paquet chaque matin.

**État actuel :** le lot de fonds est renouvelé à la compilation et le client PS5 tente aussi une mise à jour HTTPS quotidienne vers un cache privé dans `/download0`. Le client revient automatiquement aux images embarquées si l'API réseau ou le serveur n'est pas disponible. Ce rafraîchissement n'a pas encore été confirmé sur une véritable console avec le firmware cible ; l'interface ne prétend pas qu'une récupération en ligne a eu lieu quand seul le fond de secours est affiché. Les captures appartiennent à leurs éditeurs ; leurs droits doivent être respectés.

## Package FTP unique (sans imbriquation)

La compilation fournit **exactement** `dist/PPSA99386.zip`. À l'intérieur, une seule racine : `PPSA99386/`, suivie de `eboot.bin`, `sce_sys/`, `sce_module/` et `assets/`. Les fichiers intermédiaires, le programme `niakps5_autostart.elf` et les autres ZIP ne sont **jamais** inclus dans ce paquet. Droits UNIX explicites dans l'archive et le dossier de build : dossiers 0755, `eboot.bin` et `tools/niakps5/niakps5.elf` 0755, autres fichiers 0644. Le packager rejette les symlinks et les archives imbriquées.

Dézipper le **seul dossier `PPSA99386`** puis le transférer vers `/data/homebrew/` par FTP. L'archive contient le déclencheur `tools/niakps5/niakps5.elf`, mais son extraction seule n'active pas le démarrage automatique : l'installateur FTP embarqué configure PLDmgr. Il vérifie le titre et le payload avant tout transfert. Sa compatibilité sur firmware 13.60 reste à tester sur console. Le fonctionnement du scanner ShadowMountPlus et la récupération du vrai avatar restent à valider sur console.

## Livraison FTP : autoload inclus dans le seul dossier

Le ZIP `PPSA99386.zip` possède **une unique racine `PPSA99386/`**. L'application native reste sous cette racine. Le fichier `PPSA99386/tools/niakps5/niakps5.elf` est le déclencheur de démarrage (payload classique, pas d'interface SDL). Les fichiers de configuration existants du Payload Manager ne sont jamais inclus car ils sont propres à chaque console.

Pour installer automatiquement à partir d'un PC ayant Python 3 :
```sh
python3 PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --port 2121 --autoload
```
Le script dépose le dossier dans `/data/homebrew/PPSA99386/`, copie le payload dans `/data/pldmgr/payloads/niakps5/niakps5.elf`, ajoute **son chemin absolu en dernier** dans `/data/pldmgr/autoload.txt` et active AUTOLOAD_ENABLED dans la configuration existante. Les versions actuelles de Payload Manager acceptent les chemins absolus sous `/data/pldmgr`. Il sauvegarde les deux fichiers de configuration avant changement (`.niakps5.bak`) et ne modifie pas Kstuff ou ShadowMountPlus. **À lancer seulement si le titre graphique est déjà testé.**

Le bouton PS reste géré par le shell Sony. Le démarrage reste one-shot. L'option `--return-after-game` arme séparément la surveillance d'un jeu explicitement lancé par NiakPS5, avec dix secondes de grâce. Son fonctionnement sur console 13.60, tout comme le chargement de l'avatar privé, reste à valider.

### Sources supplémentaires pour les jaquettes

Après LaunchBox, le script FTP sait consulter **TheGamesDB** (scans de boîtiers recto/verso pour plateforme PS4 ou PS5 vérifiée) et **SteamGridDB** (illustrations communautaires verticales pour le recto seulement). Ces deux services demandent une clé personnelle. Elles sont facultatives et restent dans les variables d'environnement de ton ordinateur ; elles ne sont ni copiées sur la PS5 ni intégrées au dépôt ou au ZIP.

Sur ton Mac, avec les clés personnelles que tu as obtenues auprès des services :

```sh
export NIAK_THEGAMESDB_KEY="votre-cle-thegamesdb"
export NIAK_STEAMGRIDDB_KEY="votre-cle-steamgriddb"
python3 PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --refresh-art
```

Ordre : **LaunchBox → TheGamesDB (recto/verso) → SteamGridDB (illustration de recto)**. La dernière source est une illustration de bibliothèque communautaire, pas nécessairement une jaquette PS5 physique officielle. Les faces arrière et tranches non trouvées conservent le traitement de secours du boîtier ; une fausse tranche n'est jamais téléchargée. La recherche rejette les noms ambigus et vérifie la plateforme TheGamesDB avant de télécharger. Les images vont uniquement dans le cache privé du titre sur la console ; respecter les droits et limites des fournisseurs. Sans clés, LaunchBox et les visuels de secours fonctionnent comme avant.

## Gabarits 3D PS4/PS5 fournis par l'utilisateur

Six images PNG privées (ps4-front, ps4-back, ps4-spine, ps5-front, ps5-back, ps5-spine) sont acceptées sous `PPSA99386/assets/niak-templates/`.
Décompresser `NiakPS5-gabarits-prives.zip` au même emplacement que le dossier `PPSA99386/` extrait, puis utiliser l'installation FTP habituelle. `--refresh-art` transfère également les gabarits sans réinstaller le titre. `--status` affiche le nombre de fichiers présents. Quitter complètement NiakPS5 puis le relancer après modification : les textures sont chargées au démarrage.

Le rendu garde la priorité aux véritables scans recto, verso et tranche. À défaut, le moteur recombine l'icône ou artwork connu, la description disponible et les gabarits PS4/PS5 sur le boîtier fermé. Les parties hautes du recto, basses du verso et les tranches proviennent des éléments envoyés par le propriétaire, non de GitHub ni des builds CI. L'identifiant historique au pied des tranches est masqué. Sans gabarits, le rendu procédural neutre reste disponible.

Attention : les notes légales, classifications et logos présents dans les exemples sont propres aux jeux originaux. Ils ne constituent pas des informations officielles pour les autres titres. L'assemblage est un habillage personnel, distinct d'une jaquette authentique.

## Diagnostic local et récupération des jaquettes

Une copie manuelle du ZIP par FTP ne télécharge **pas** les images privées LaunchBox et ne configure **pas** l'autoload. L'installeur FTP livré dans l'archive, lui, configure PLDmgr par défaut ; `--no-autoload` désactive explicitement cette étape. Utiliser le script embarqué dans le dossier extrait pour obtenir ces fonctions sans publier les jaquettes :

```sh
python3 PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --status
python3 PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --refresh-art
python3 PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --refresh-art --force-art
```

- `--status` est en lecture seule. Il contrôle la présence du titre, des images, du payload, de la configuration PLDmgr et d'un dernier lancement inscrit au journal. **Un succès historique n'est pas une preuve de l'autoload au démarrage actuel.**
- `--refresh-art` conserve les images déjà transférées, puis essaie de télécharger les rectos, versos et tranches LaunchBox des titres accessibles par FTP, jusqu'à 150 jeux (réglable avec `--art-limit`).
- `--force-art` n'est accepté qu'avec `--refresh-art`. Il retélécharge les images même si une ancienne version existe. Rien n'est écrit dans `app.db` ou les fichiers des autres homebrews.
- Un titre sans jaquette compatible affiche une boîte 3D neutre avec son icône locale (si accessible), sans étirer cette icône en illustration commerciale. Les rangées de bibliothèque et la fiche de détails conservent les icônes 2D.
- La catégorie Jeu/Application est lue depuis les `sce_sys/param.json` accessibles. Sans cette source, le titre conserve une catégorie de repli et n'invente pas de données.

La récupération LaunchBox nécessite une connexion sur l'ordinateur qui exécute le script, et des permissions FTP suffisantes pour accéder aux dossiers PS5. Ni la présence d'un index ni une compilation verte ne prouvent que les scans sont effectivement présents sur la console.

## Titres réels, fonds PS5 et limites des descriptions

Le paquet inclut désormais une base textuelle hors ligne de titres PS4 et PS5 (andshrew/PlayStation-Titles, MIT), enrichie pour certains jeux avec genres, éditeur et sortie depuis sharpemu/sharpemu-site. Elle est utilisée lorsque ShadowMountPlus fournit seulement un identifiant PPSA/CUSA. L'installeur FTP peut en outre créer un fichier privé `niak-local-titles.tsv` à partir des `sce_sys/param.json` des applications homebrew.

La description affichée provient des **métadonnées factuelles disponibles**, et non d'un résumé éditorial inventé. Les œuvres sans résumé disponible ne reçoivent pas une intrigue fictive. Les noms et images publiés par les ayants droit restent leurs marques et créations.

Les 14 visuels embarqués dans `assets/niak-daily` proviennent d'un relevé GitHub des sorties récentes PS5 et des images d'éditeurs PlayStation. Un bug TGA empêchait précédemment le chargement des images en rejetant leur pied de fichier standard de 26 octets ; ce bug est corrigé. Le titre sélectionne désormais un visuel différent chaque jour selon sa date locale. **Le titre essaie maintenant un rafraîchissement HTTPS quotidien** à partir d'un flux de sorties PS5 publiques (worker hors thread graphique, cache privé `/download0`). En cas d'échec du réseau ou de permission, il garde les 14 images du paquet et sélectionne celle du jour localement. L1/R1 naviguent entre les onglets du menu. Seule la commande « Changer le fond du jour » dans Réglages parcourt les images embarquées, sans avancer la date réelle. Ce choix reste actif jusqu'au jour suivant, même après redémarrage de NiakPS5. La disponibilité du service HTTPS natif reste à confirmer sur la console et le firmware cible.

Un élément « Paramètres PS5 » ne doit pas prétendre ouvrir directement un service Sony non supporté : l'option quitte vers l'accueil Sony. Aucun accès à des réglages sensibles ou fonction système n'a été contourné.

## Contrôles de la version et du lancement

Le moteur amont consommait les actions R1 et clic tactile avant NiakPS5.
La version à écran unique transmet ces deux actions à NiakPS5. Les captures
OpenGL doivent montrer un changement réel de fond après R1 et la fiche de
détails propre à NiakPS5 après un clic du pavé tactile.

Réglages affiche le SHA Git exact du titre compilé ainsi que le résultat d'un
PING local du service de lancement PLDmgr. La simple présence de l'ELF ou
du fichier autoload ne prouve pas que le service fonctionne.

Pour comparer les deux binaires du paquet local à l'installation PS5 :

    python3 PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --status

La commande est en lecture seule : elle compare les SHA-256 de eboot.bin
et du payload niakps5.elf. Un ancien binaire explique pourquoi l'interface
semble inchangée malgré les commits. Les accès FTP refusés sont déclarés
inconnus, jamais présumés valides.

Jouer utilise désormais le service local du payload opt-in PLDmgr, limité
à 127.0.0.1:19187, pour les identifiants d'applications installées.
Les erreurs de ce service sont affichées dans la fiche au lieu de fermer
silencieusement l'écran. Le succès effectif sur le firmware PS5 doit
toujours être constaté sur console ; il ne découle pas d'un CI vert.

Jeux et Applications sont répartis par catégorie réelle si la PS5 la rend
accessible, et triés par dernier accès puis installation. Si app.db n'est
pas lisible, le dossier d'installation fournit une date de repli approximative.

## Installation intégrée de l'ELF (optionnelle, jailbreak déjà actif)

Le paquet comprend maintenant `sandbox-elevator.elf` (mécanisme ponctuel
Eden Encore adapté à `PPSA99386`). Au démarrage du titre, si un elfldr
compatible écoute déjà sur `127.0.0.1:9021`, NiakPS5 demande une seule
fois l'accès au système de fichiers puis installe ou met à jour exclusivement
son propre `niakps5.elf` et `.elf.json` dans PLDmgr. L'entrée existante
`autoload.txt` est conservée, une ligne manquante est ajoutée sans toucher
aux autres payloads ni au fichier de configuration globale. NiakPS5
continue en sandbox si le helper échoue. Le journal natif contient
`one-shot own payload install status=` : 1=mise à jour, 0=déjà installé,
-1=helper indisponible, -2=validation/écriture refusée.
Le processus PLDmgr déjà résident conserve son ancien code jusqu'au prochain
démarrage : remplacer le fichier ELF sur disque n'effectue pas un rechargement
à chaud. La disponibilité de l'elevation doit être qualifiée sur PS5 13.60.
