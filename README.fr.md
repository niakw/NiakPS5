# NiakPS5

**Votre bibliothèque. Votre manette. Votre PS5.**

Un accueil **natif et plein écran** pour PS5 homebrew, avec navigation DualSense, jeux et applications, lancement local et boîtiers PS4/PS5 animés en 3D.

[English](README.md) · [Notes techniques](native/title/README.md) · [Versions et captures](https://github.com/niakw/NiakPS5/actions/workflows/native-title.yml)

![Capture réelle de l'accueil NiakPS5 via le moteur OpenGL et Mesa, avec données de démonstration](docs/images/niakps5-home.png)

*Capture du moteur OpenGL de NiakPS5 en prévisualisation Mesa (données de test). Pas une maquette ni une capture provenant directement de la console.*

## Une interface conçue pour la manette

Naviguez entre **Jeux**, **Applications** et **Réglages** avec la DualSense. Retrouvez les titres installés, leurs icônes, leurs informations disponibles, des fonds du jour et une animation de boîtier 3D sans passer par un navigateur.

### Les jaquettes s'enrichissent automatiquement

NiakPS5 privilégie les véritables rectos, versos et tranches LaunchBox. **Seule la sélection d'un jeu** déclenche une demande de visuels au CDN : parcourir les autres jeux ne provoque pas de téléchargement. Le traitement en arrière-plan privilégie les faces officielles, valide JPEG/PNG puis utilise le cache privé. Une image récupérée peut apparaître sur le boîtier 3D sélectionné **sans relancer l'application**. Aucun script Mac n'est nécessaire pour cette tentative.

L'accès HTTPS dépend des autorisations réseau du firmware et de la disponibilité de LaunchBox. Si une image n'est pas disponible, le boîtier conserve son rendu recomposé avec les éléments PS4/PS5 appropriés. Les scans commerciaux ne sont pas inclus dans le paquet GitHub et aucune capture personnelle n'est publiée.

La description d'un jeu reste **courte : trois phrases maximum** issues des métadonnées disponibles, sans récit inventé. Les résumés LaunchBox étant souvent en anglais, l'application les affiche dans leur langue d'origine si elle n'a pas de traduction française. Elle ne traduit pas automatiquement tout le catalogue.

## État du projet

Sur la PS5 13.60 de test, **48 titres ont été trouvés**, la bibliothèque s'affiche et « Jouer » a permis de démarrer un jeu. Le classement des applications, le téléchargement natif des visuels, le raccourci système et le retour après fermeture exigent encore une validation matérielle des derniers correctifs. Les [captures OpenGL des boîtiers](https://github.com/niakw/NiakPS5/actions/workflows/native-title.yml) et la compilation native sont vérifiées séparément en CI.

## Installation et mise à jour

1. Télécharger l'artefact **`NiakPS5-PPSA99386`** d'un [run vert sur `main`](https://github.com/niakw/NiakPS5/actions/workflows/native-title.yml).
2. Extraire une seule fois l'archive ; fusionner son dossier **`data/`** à la racine FTP **`/`** de la PS5 **sans effacer les dossiers existants**.
3. Ouvrir, via un chargeur homebrew compatible déjà configuré (par exemple ShadowMountPlus), le titre **`PPSA99386`** sur la console. Le payload compagnon est livré dans le même dossier à copier.

Le paquet **ne modifie pas** `autoload.txt`, la configuration PLDmgr ni les fichiers du système Sony. Si un autoload NiakPS5 existe déjà et fonctionne, conservez-le. La simple copie FTP ne peut ni enregistrer un nouveau titre PS5 ni créer une entrée d'autoload manquante.

Le cache d'artwork automatique est interne à NiakPS5. Les outils FTP supplémentaires sont documentés **uniquement pour le diagnostic ou la réparation** dans les [notes techniques](native/title/README.md), pas comme une étape normale de mise à jour.

## Confidentialité et limites

NiakPS5 n'intercepte pas le bouton PS, ne remplace pas `SceShellUI` et ne contourne aucune exigence de disque ou de licence. Le lancement des jeux passe par un courtier local sur `127.0.0.1`. Le téléchargement des images ne transmet à LaunchBox que leurs noms de fichiers publics, sans profil PS5 ni identifiant de jeu privé. Les visuels tiers restent la propriété de leurs auteurs.

Code **GPL-3.0-or-later**, licences tierces conservées. Projet indépendant, non affilié à Sony ni LaunchBox.
