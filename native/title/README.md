# NiakPS5 — Guide technique / Technical notes

[Guide utilisateur FR](../../README.md) · [User guide EN](../../README.en.md)

## Chaîne d'installation

La CI compile un titre natif `PPSA99386` et un payload compagnon PLDmgr, puis publie un unique dossier `data/`. Il n'inclut jamais d'`autoload.txt` ni de configuration utilisateur. Sur une console où le payload fonctionne déjà, conserver l'autoload existant et fusionner `data/` par FTP.

Le workflow publie **deux familles d'aperçus réels OpenGL** : l'écran d'accueil (`NiakPS5-OpenGL-home`) et six angles de boîtier PS4/PS5 (`NiakPS5-OpenGL-interface-preview`). Ces images sont générées par le même moteur sous Mesa avec des **fixtures de test**, non par un générateur d'images.

## Chaîne LaunchBox et cache

1. `launchbox_index.py` extrait les données publiques et distingue les plateformes et régions. Front PS5 prioritaire, back PS4 compatible, captures/fanarts PC complémentaires si le jeu correspond sans ambiguïté.
2. **Dans l'application**, `case_auto_art.cpp` demande en arrière-plan les images publiques qui manquent (HTTPS LaunchBox), les décode en JPEG/PNG et les enregistre sous `/download0/niak-case-*`. Le cache est relu au lancement suivant. Si la sandbox bloque HTTPS, le rendu recomposé reste utilisable. L'outil FTP facultatif peut, en dépannage, transférer des scans vers `/data/NiakPS5/assets/niak-cases/`.
3. Un cache privé `source-cache-v2.tsv` mémorise **titre + face + fichier source**. Une image n'est réutilisée que si sa provenance correspond et que son WebP est intégralement décodable. Un élément manquant, corrompu ou obsolète est traité **indépendamment**, sans supprimer les autres faces.
4. Au démarrage, `case_art.cpp` lit les scans réels avant toute recomposition. Les faces officielles ne reçoivent pas les gabarits. `cover_stream_state.hpp` espace les créations de textures GPU. **Le téléchargement natif peut actualiser la jaquette pendant la même session** ; l'arrivée de fichiers FTP est aussi observée périodiquement. Une relance reste possible si des transferts tardifs ne sont pas visibles.
5. Le téléchargement natif est automatiquement tenté sans outil externe, **mais non encore validé sur PS5 13.60**. Une simple copie FTP du paquet n'effectue aucun téléchargement. Les fichiers commerciaux ne sont jamais redistribués via GitHub.

```bash
python3 data/homebrew/PPSA99386/tools/ftp_install.py --host PS5_IP --status
python3 data/homebrew/PPSA99386/tools/ftp_install.py --host PS5_IP --refresh-art
# Seulement pour réparer un cache persistant incorrect :
python3 data/homebrew/PPSA99386/tools/ftp_install.py --host PS5_IP --refresh-art --force-art
```

Ces commandes sont réservées au **dépannage** (cache incorrect ou diagnostic), et ne constituent pas une installation obligatoire des jaquettes. Les visuels doivent être tentés automatiquement par l'application. Un défaut réseau PS5 ne doit jamais bloquer la bibliothèque.

## Traduction / Localization

Les commandes, réglages et diagnostics de l'interface utilisateur sont en français. La description d'un jeu se limite à **trois phrases issues de la source, 360 caractères au maximum** ; le catalogue n'est ni réécrit ni traduit en masse. Les résumés LaunchBox sont souvent en anglais : il n'existe aucune traduction française garantie.

Le fichier privé `assets/niak-overviews-fr.tsv` est prioritaire lorsqu'une traduction française existe. Il peut être produit volontairement par `--refresh-art --translate-fr` avec une clé API DeepL dans la variable `NIAK_DEEPL_API_KEY` du Mac. La PS5 ne fait aucun appel de traduction et ne stocke pas la clé. En cas d'échec, le résumé original reste affiché.

The LaunchBox original is preserved when there is no French version. Optional DeepL API translation happens on the owner's computer, **never inside the PS5 UI** and only after the user explicitly requests it.

## Correctifs de sûreté / Safety guarantees

Le lancement et les snapshots restent limités au service local `127.0.0.1:19187`. Aucun accès arbitraire à `app.db` en écriture, aux sauvegardes, aux profils ou au shell Sony. La redirection après fermeture d'un jeu ne s'arme qu'après un lancement demandé dans NiakPS5 et doit observer réellement le jeu avant un retour unique.

L'accès aux réglages PS5 est un **lien expérimental** et peut être refusé selon le firmware. Le code ne doit pas annoncer un succès de lancement ou d'ouverture de page sans validation console.

## Vérifier les révisions

```bash
python3 -m unittest discover -s native/title/tests -p 'test_*.py' -v
bash native/title/build.sh
```

**La compilation est un contrôle, pas une preuve matérielle.** Conserver une seule branche `main`, ne jamais embarquer de captures personnelles, d'IP, de clés API ni de configurations privées dans Git.
