# Diagnostic du démarrage — NiakPS5 / PLDMGR

**Important : arrêtez d'utiliser l'ancien `niakps5_bootstrap.elf` jusqu'à clarification du firmware et du mode bigapp.**

## Ce qui se passe avec l'ancien ELF

- L'ancien `niakps5_bootstrap.elf` est un **chargeur**, pas une interface.
- Il cherche l'interface dans `/data/niakps5/niakps5_ui.elf`, à la racine de `/data`, quelle que soit sa position sous `/data/pldmgr`.
- Il utilise un dérivé de `hbldr` de Nativehbl / websrv. Ce dernier peut remonter `/system_ex` en écriture, créer `/system_ex/app/FAKE00000`, accrocher `SceSysCore` et arrêter l'application bigapp active. Cette méthode **n'est pas non intrusive** et n'est pas validée sur firmware 13.60.
- Il dépend notamment du chemin PS Now `/system_ex/app/NPXS40106/eboot.bin`, susceptible d'être absent sur firmware récent. **Ne recréez pas ce chemin et ne copiez pas d'eboot système à la main.**
- Un outil externe tel que Homebrew Launcher PKG/ShadowMount peut être nécessaire au mode d'exécution, ce qui n'est pas couvert par une simple compilation ELF.

## Diagnostic sécurisé

Le nouvel ELF `niakps5_diagnostic.elf` **ne lance pas le shell graphique**. Il fait des tests d'existence en lecture seule et montre le résultat en notification PS5, puis écrit une trace dans `/data/niakps5-diagnostic.log`.

Le diagnostic ne fait **aucune** opération `mount`, `ptrace`, `kill`, `kernel_set_ucred`, lancement d'app ou modification de `/system_ex`. La seule écriture intentionnelle est son propre fichier de log sous `/data`.

Depuis l'archive de diagnostic, installez exactement :

```text
/data/
├── pldmgr/
│   └── niakps5_diagnostic.elf  <- celui à lancer depuis Payload Manager
└── niakps5/
    ├── niakps5_ui.elf
    └── assets/
        ├── manrope.ttf
        └── instrument-serif.ttf
```

Démarrez d'abord votre environnement jailbreak habituel, puis **lancez uniquement `niakps5_diagnostic.elf`**. Même si rien ne s'affiche, récupérez `/data/niakps5-diagnostic.log` par FTP et partagez-en le contenu.

Si le fichier de log est absent, le payload n'a peut-être pas été exécuté du tout (problème d'ELF loader / PLDMGR) ou il n'a pas pu ouvrir le log. Vérifiez les journaux Payload Manager/elfldr.

Ne réessayez pas de lancer le bigapp tant que ce premier diagnostic n'est pas compris.

## Limites

Une notification positive signifie que les fichiers sont présents, **pas** que `hbldr`, SDL2, le GPU ou `sceSystemServiceLaunchApp` fonctionnent. Il faudra ensuite choisir une méthode d'hébergement native compatible 13.60, idéalement comme application homebrew enregistrée avec ses fichiers privés plutôt que par injection hasardeuse.
