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
# donne dist/PPSA99386.zip
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

**Limite actuelle :** la génération du paquet est quotidienne, mais le titre installé n'actualise pas encore ses images en HTTPS depuis la PS5. Il conserve son lot embarqué jusqu'à mise à jour du paquet. Il ne faut pas prétendre à un téléchargement journalier autonome avant l'intégration d'un transport HTTPS fiable et d'un cache atomique dans le stockage privé `/download0`. Les captures appartiennent à leurs éditeurs ; il faut respecter leurs droits.

## Package FTP unique (sans imbriquation)

La compilation fournit **exactement** `dist/PPSA99386.zip`. À l'intérieur, une seule racine : `PPSA99386/`, suivie de `eboot.bin`, `sce_sys/`, `sce_module/` et `assets/`. Les fichiers intermédiaires, le programme `niakps5_autostart.elf` et les autres ZIP ne sont **jamais** inclus dans ce paquet. Droits UNIX explicites dans l'archive et le dossier de build : dossiers 0755, `eboot.bin` 0755, autres fichiers 0644. Le packager rejette les symlinks et les archives imbriquées.

Dézipper le **seul dossier `PPSA99386`** puis le transférer vers `/data/homebrew/` par FTP. Ce format n'exécute pas à lui seul un chargeur automatique : l'autodémarrage après jailbreak, distinct du titre natif, nécessite une intégration externe vérifiée, non embarquée dans le ZIP FTP. Le fonctionnement du scanner ShadowMountPlus et la récupération du vrai avatar restent à valider sur console.

## Livraison FTP : autoload inclus dans le seul dossier

Le ZIP `PPSA99386.zip` possède **une unique racine `PPSA99386/`**. L'application native reste sous cette racine. Le fichier `PPSA99386/tools/niakps5.elf` est le déclencheur de démarrage (payload classique, pas d'interface SDL). Les fichiers de configuration existants du Payload Manager ne sont jamais inclus car ils sont propres à chaque console.

Pour installer automatiquement à partir d'un PC ayant Python 3 :
```sh
python3 PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --port 2121 --autoload
```
Le script dépose le dossier dans `/data/homebrew/PPSA99386/`, copie le payload dans `/data/pldmgr/payloads/niakps5/niakps5.elf`, ajoute **son chemin absolu en dernier** dans `/data/pldmgr/autoload.txt` et active AUTOLOAD_ENABLED dans la configuration existante. Les versions actuelles de Payload Manager acceptent les chemins absolus sous `/data/pldmgr`. Il sauvegarde les deux fichiers de configuration avant changement (`.niakps5.bak`) et ne modifie pas Kstuff ou ShadowMountPlus. **À lancer seulement si le titre graphique est déjà testé.**

Le bouton PS reste géré par le shell Sony. Le déclencheur est one-shot : il ne rétablit pas le titre automatiquement après chaque jeu. Une implémentation sûre du retour à l'accueil et de l'avatar privé nécessite une validation distincte ; le ZIP ne prétend pas les inclure déjà.

## Titres réels, fonds PS5 et limites des descriptions

Le paquet inclut désormais une base textuelle hors ligne de titres PS4 et PS5 (andshrew/PlayStation-Titles, MIT), enrichie pour certains jeux avec genres, éditeur et sortie depuis sharpemu/sharpemu-site. Elle est utilisée lorsque ShadowMountPlus fournit seulement un identifiant PPSA/CUSA. L'installeur FTP peut en outre créer un fichier privé `niak-local-titles.tsv` à partir des `sce_sys/param.json` des applications homebrew.

La description affichée provient des **métadonnées factuelles disponibles**, et non d'un résumé éditorial inventé. Les œuvres sans résumé disponible ne reçoivent pas une intrigue fictive. Les noms et images publiés par les ayants droit restent leurs marques et créations.

Les 14 visuels embarqués dans `assets/niak-daily` proviennent d'un relevé GitHub des sorties récentes PS5 et des images d'éditeurs PlayStation. Un bug TGA empêchait précédemment le chargement des images en rejetant leur pied de fichier standard de 26 octets ; ce bug est corrigé. Le titre sélectionne désormais un visuel différent chaque jour selon sa date locale. **La bibliothèque de visuels installée n'est pas encore renouvelée automatiquement par HTTPS** : la CI produit de nouveaux paquets régulièrement, mais leur installation sur console reste distincte.

Un élément « Paramètres PS5 » ne doit pas prétendre ouvrir directement un service Sony non supporté : l'option quitte vers l'accueil Sony. Aucun accès à des réglages sensibles ou fonction système n'a été contourné.
