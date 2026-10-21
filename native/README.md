# NiakPS5 — un seul ELF PS5 (expérimental)

## Installation : un fichier

La distribution PS5 contient **un seul** exécutable `NiakPS5.elf` à copier dans :

```text
/data/pldmgr/NiakPS5.elf
```

À lancer dans Payload Manager **après** l'environnement jailbreak habituel. **Aucun autre fichier NiakPS5 n'est à copier** : interface native, logique SQLite, navigation DualSense, palettes et fontes Manrope / Instrument Serif sont compilées dans cet ELF. Les illustrations de jeux sont lues dans les répertoires de la console, sans être intégrées comme des jeux factices.

### Attention : compatibilité matérielle

La compilation croisée et les tests PC prouvent la validité du binaire, **pas** sa capacité à ouvrir une fenêtre graphique dans le processus créé par Payload Manager sur une PS5 firmware 13.60. Ce chemin exécute SDL2 **directement** ; il ne crée pas de processus "bigapp". Un processus de payload n'a pas nécessairement les droits ou les services vidéo d'une application installée.

En cas d'échec ou d'écran inchangé, vérifiez la notification et le fichier `/data/niakps5.log` par FTP. Le binaire appelle `sceKernelSendNotificationRequest` au démarrage et en cas d'erreur SDL ; en fonction du loader et du firmware, les notifications peuvent aussi ne pas être visibles. Le log est uniquement écrit sous `/data`, jamais dans `/system_ex`.

**L'ancienne méthode `niakps5_bootstrap.elf` + `niakps5_ui.elf` est abandonnée** pour la distribution par défaut. Le chemin expérimental `hbldr` et son risque de montage système sont isolés hors du build normal. Ne plus lancer l'ancien bootstrap.

Si l'exécution directe ne reçoit pas d'accès vidéo, il faudra ensuite porter le lanceur en application homebrew native correctement hébergée. Ne pas résoudre ce problème en remplaçant ou en remountant les fichiers système Sony.

## Build

```sh
export PS5_PAYLOAD_SDK=/chemin/vers/ps5-payload-sdk
native/fetch-sqlite.sh
make -C native
ls -lh native/build/NiakPS5.elf
```

Le script `native/tools/embed_assets.py` génère `native/build/embedded_assets.h` à partir des deux fonts sous `native/assets/`. C'est **une étape de compilation locale**, pas un fichier à installer sur la console. Les polices sont ensuite ouvertes depuis la mémoire via `SDL_RWFromConstMem`, sans extraction sur disque.

Le moteur SDL2 initialise l'affichage en plein écran 1920×1080, tente l'accélération vidéo disponible et possède un repli logiciel. La base `/system_data/priv/mms/app.db` est consultée en lecture seule, avec vérification des installations détectées et appel `sceSystemServiceLaunchApp` pour les jeux sélectionnés. Ces appels devront être validés sur le firmware cible.

## Délimitation

- Pas de remplacement de `SceShellUI`, ni de capture du bouton PS.
- Pas d'autoloader tant que l'exécution directe n'a pas été validée.
- Pas d'injection de processus, `ptrace`, remontage `/system_ex` ou modification de base Sony.
- Les fichiers `diagnostic.c` et `bootstrap.c` demeurent dans le dépôt pour l'historique et les études, **non présents dans le ELF livré**.
- Sources et attribution GPL-3.0-or-later ; polices SIL OFL, notices conservées dans `fonts/`.
