# NiakPS5

**Votre bibliothèque. Votre manette. Votre PS5.**  
Un accueil natif pour PS5 homebrew, avec bibliothèque unifiée, lancement local et boîtiers PS4/PS5 en 3D.

[English](README.en.md) · [Installation et dépannage](native/title/README.md) · [Versions et tests](https://github.com/niakw/NiakPS5/actions)

![Accueil NiakPS5 : capture du moteur OpenGL natif sur Mesa avec données de démonstration](docs/images/niakps5-home.png)

*Capture du véritable moteur d'interface OpenGL en mode prévisualisation (Mesa, données de test). Ce n'est ni une maquette, ni une capture directement prise sur la PS5.*

## Une interface pensée pour la console

NiakPS5 rassemble les titres détectés par le service local PLDmgr, ShadowMountPlus et les sources de métadonnées accessibles en lecture seule. Naviguez à la **DualSense**, passez de **Jeux** à **Applications**, affichez les détails d'un titre et utilisez **Jouer** sans navigateur.

Les boîtiers animés privilégient, dans l'ordre, un véritable **recto/verso/tranche LaunchBox** puis une recomposition élégante à partir de ressources distinctes. Les éléments fixes PS4/PS5 servent uniquement aux faces manquantes. L'application propose un fond d'écran quotidien, une galerie de visuels enrichis, des réglages intégrés et un raccourci expérimental vers les réglages PS5.

### Ce qui fonctionne déjà sur console

Sur la console de test PS5 13.60, **48 titres ont été recensés**, la bibliothèque s'affiche et **« Jouer » peut lancer un jeu**. Le classement Jeux/Applications, les images enrichies, les descriptions et le retour après fermeture d'un jeu font encore l'objet de corrections. Une compilation verte ne prouve **pas** que ces fonctions sont validées sur le matériel.

## Aperçu des boîtiers

Les [captures OpenGL réelles des six faces PS4/PS5](https://github.com/niakw/NiakPS5/actions/workflows/native-title.yml) sont produites automatiquement en CI. Elles utilisent des images de contrôle et ne redistribuent pas les scans LaunchBox.

## Installer / mettre à jour

1. Dans [GitHub Actions](https://github.com/niakw/NiakPS5/actions/workflows/native-title.yml), choisir un run **vert sur `main`** et télécharger **`NiakPS5-PPSA99386`**.
2. Extraire l'archive une seule fois : elle contient **`data/`**. Dans le FTP PS5, fusionner ce dossier avec **`/`**, sans supprimer vos répertoires existants.
3. Lancer le titre **`PPSA99386`**, déjà enregistré via la chaîne homebrew de la console. Le paquet contient aussi le payload compagnon `niakps5.elf` ; il **ne remplace pas** la configuration PLDmgr, `autoload.txt` ou les fichiers du système Sony.

Une copie FTP seule **n'active pas** un nouvel autoload et **ne télécharge pas** les images LaunchBox. Lorsque l'autoload existant fonctionne, conservez-le.

### Récupérer les jaquettes et les descriptions

Depuis le Mac, après extraction de l'artefact, utilisez **l'outil inclus** dans NiakPS5 (aucune nouvelle app à installer sur la console) :

```bash
python3 data/homebrew/PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --port 2121 --refresh-art
```

Cette commande relève les titres installés, reconstruit un index LaunchBox local, récupère les faces/captures manquantes et conserve un cache par source. **Fermez et rouvrez NiakPS5** pour recharger les textures GPU. Pour contrôler la couverture sans modification :

```bash
python3 data/homebrew/PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --status
```

Si une ancienne image reste invalide, `--refresh-art --force-art` peut la retélécharger ; n'utilisez cette option qu'en cas de besoin. Les scans téléchargés restent sur **votre propre PS5**, et non dans le dépôt public.

**Descriptions FR :** LaunchBox fournit souvent un texte anglais. NiakPS5 l'affiche tel quel lorsqu'aucune traduction française n'existe. Pour utiliser, de manière **facultative**, l'API DeepL sur les seuls résumés publics :

```bash
export NIAK_DEEPL_API_KEY="VOTRE_CLE_API_DEEPL"
python3 data/homebrew/PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --refresh-art --translate-fr
```

L'enrichissement traduit les textes disponibles, sans envoyer les identifiants de titres ou les profils PS5. Il peut consommer votre quota DeepL. Les traductions sont conservées dans le stockage privé de NiakPS5 et l'anglais reste le repli en cas d'échec.

## Choix de conception

- **Bibliothèque vérifiable :** les installations en cours sont distinguées des derniers inventaires FTP.
- **Artworks authentiques :** pas de jaquette commerciale inventée, pas de doublon forcé entre recto et verso.
- **Interface GPU fluide :** décodage progressif des textures, budget mémoire limité et diagnostics de chargement.
- **Compatibilité PS5 :** aucun remplacement de `SceShellUI`, aucune interception du bouton PS, aucun contournement de disque ou de licence.
- **Confidentialité :** appels de lancement limités à `127.0.0.1`, clés API jamais embarquées, ni sauvegardes ni captures personnelles publiées.

## Développement

```bash
python3 -m unittest discover -s native/title/tests -p 'test_*.py'
bash native/title/build.sh
```

Le projet utilise un moteur OpenGL natif, le SDK de compilation PS5 et une révision épinglée du kit [PS5_VKHomebrewUI](https://github.com/mihawk-99/PS5_VKHomebrewUI). Une prévisualisation Mesa et une compilation PS5 sont contrôlées par CI avant tout essai physique.

**Projet homebrew expérimental, non affilié à Sony ou LaunchBox.** Les marques et visuels restent la propriété de leurs détenteurs. Code sous **GPL-3.0-or-later** ; composants tiers sous leurs licences respectives.
