# NiakPS5 — comparaison technique et plan du moteur graphique

Statut : audit au 21 octobre 2026. Objectif : **accueil PS5 principal après l'exploit**, sans écraser `SceShellUI`. Le launcher native est autonome, les binaires sont compilables, mais aucun essai matériel 13.60 n'est enregistré.

## Références étudiées

| Référence | Nature | Moteur |
| --- | --- | --- |
| [Phononenom/ps5-homebrew-ui](https://github.com/Phononenom/ps5-homebrew-ui) | Branche/fork du kit BlackBearReloaded | OpenGL 4.6, EGL PS5 |
| [J7mbo/ps5-homebrew-ui](https://github.com/J7mbo/ps5-homebrew-ui) | Branche/fork du même kit | OpenGL 4.6, EGL PS5 |
| [mihawk-99/PS5_VKHomebrewUI](https://github.com/mihawk-99/PS5_VKHomebrewUI) | Fork du kit pour backend Vulkan | OpenGL ET Vulkan RADV dans un contexte intégré |

**Important : ce ne sont pas trois moteurs incompatibles.** La majorité de leurs composants, concepts, médias et fichiers `src/` reposent sur le projet d'origine [blackbearreloaded/ps5-homebrew-ui](https://github.com/blackbearreloaded/ps5-homebrew-ui). Les différences sont surtout le backend GPU et les workflows/outillages.

Leur principal usage est un **kit UI démonstrateur** (catalogue fictif, thèmes, écrans et fonctionnalités UX), non un clone complet des services Sony. Il ne suffit donc pas d'en recopier la couche de rendu pour lancer des titres PS5 ou remplacer les menus système.

## Décisions

### Adopté dans NiakPS5 (actuel)

- **Présentation indépendante des données :** `native/catalog.c` parcourt les jeux réellement installés en lecture seule ; l'identité et l'affichage sont séparés.
- **Rendu natif avec négociation :** `native/ui_renderer.c` essaie les backends SDL2 accélérés disponibles, avec repli logiciel explicite. Cela ne garantit **pas** un GPU SDL sur PS5. Le backend effectif est exposé à l'écran.
- **Cache graphique borné :** 24 textures de jaquettes au plus (LRU) et 128 textures de texte (LRU), nettoyées à la fermeture. Fin des reconstructions systématiques à chaque flèche.
- **Focus et navigation :** `native/ui_motion.c` fournit easing avec vraie durée entre deux frames, répétition progressive de gauche/droite au stick ou à la croix directionnelle et tests déterministes.
- **Fond réactif sans saccades inutiles :** délai de stabilisation de 135 ms avant de charger l'image du jeu choisi, pour éviter de décoder chaque image lors d'un défilement rapide.
- **Tests PC/CI :** captures automatiques SDL2 avec base de jeux factice, tests du catalogue et de la navigation, et compilation croisée ELF séparée.

### À développer pour obtenir le rendu console-grade des références

1. **Backend OpenGL/EGL dédié (prioritaire).** Capter la fenêtre EGL PS5 avec `ps5-opengl` et `ps5-native-app-boilerplate`, sous une interface `gfx::Renderer`. Ne pas supposer que le SDL2 présent sur PS5 est GPU accéléré.
2. **UI en commandes indépendantes du backend :** rectangle/arrondi, image, glyphes SDF, clip, couleur, transparence et ordre des calques ; éviter les appels SDL directement dans chaque écran.
3. **Batching GPU + SDF :** même atlas typographique et shader pour focus, cartes, ombres, flou. Budget : latence d'entrée faible, 60 fps en 1080p natif d'abord, puis résolution 4K si le matériel et le rendu le permettent.
4. **Transition de fond et focus interrompables :** conserver les caches, crossfade entre fonds, easing sans accumulation d'allocations, image progressive et gestion des erreurs GPU.
5. **Sons/haptique et états réels :** cue focus/sélection discret, haptique respectant les préférences et aucune interférence avec overlays Sony.
6. **Option Vulkan ultérieure :** considérer `VkRenderer` du fork mihawk seulement si la pile RADV/Vulkan retenue est déjà fonctionnelle sur notre mode d'exécution. Aucun besoin de développer OpenGL et Vulkan en parallèle immédiatement.
7. **Intégration console :** accès base/titres, reprise de session, lancement jeux, retour de jeu, suspension, erreurs, services systèmes disponibles ; chaque chemin doit être vérifié sur PS5 13.60.

### Architecture visée

```text
                      NiakPS5 (identité NiakTV)
                               |
                   Screens / UI state / Focus
                               |
                 UiDrawList / GfxRenderer (API)
                     /                  \
            OpenGL/EGL GPU         SDL2 repli
                  |                    |
       PS5 ps5-opengl stack      moteur existant
                   \                  /
                    catalogue réel / profil
                            |
                 PS5 backend read-only
                     /            \
                    app.db       appmeta
                            |
                 lanceur natif SCE
                            |
                   retour Sony garanti
```

**Pas d'injection dans `SceShellUI`**, pas de destruction de fichiers système, pas de modifications de partitions firmware pour imposer le launcher. L'autoloader reste désactivable et l'accueil d'origine est préservé.

## Mesures de validation

- **Fonctionnel :** liste réelle, filtres CUSA/PPSA, images, lancement du jeu, retour après jeu, sortie via rond, absence de faux installés.
- **Performance :** frame time moyen et p99, temps d'apparition du focus, nombre de chargements de textures par seconde, RAM haute/basse, consommation CPU au repos et après 20 défilements rapides.
- **Rendu :** captures 1920×1080 puis 3840×2160, même proportions et même palette que NiakTV, pas de card stretched, couverture 16:9.
- **Robustesse :** déconnexion de manette, réveil/suspend, corruption/absence `app.db`, rescan, crash du launcher, système Sony encore accessible.
- **Automatisation :** pas d'activation au démarrage sans test manuel réussi, sauvegarde du `autoload.txt` et restauration validée.

## Attribution

Concepts et méthodes étudiés dans les trois forks listés ; **leur moteur source n'a pas été importé** et leurs écrans de démonstration ne sont pas redistribués ici. Toute intégration ultérieure de code tiers devra conserver l'attribution GPL, la licence et les notices.
