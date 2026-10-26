# NiakPS5 : démarrage via PLDmgr (installation réversible)

## Principe et limite

L'accueil natif reste l'application \`PPSA99386\` sous \`/data/homebrew\`. Un mini-payload de lancement, exécuté **une seule fois à la fin de la chaîne de jailbreak déjà configurée**, demande au service PS5 d'ouvrir le titre. **Aucun tap sur l'icône NiakPS5 ne devrait alors être nécessaire.**

Cela n'est PAS un remplacement de \`SceShellUI\` : l'écran Sony initial, les fonctions de sécurité, le bouton PS et le menu système continuent d'exister. Sur PS5 éteinte, rien ne peut changer avant que la chaîne jailbreak se lance. Si le titre ferme, le Sony Home reste accessible.

Le mini-payload :
- n'exécute pas de SDL, ni de composant graphique ;
- ne remonte pas \`/system_ex\`, n'attache pas \`SceSysCore\`, n'effectue aucun \`ptrace\` ou modification système ;
- demande le lancement du titre avec un contexte utilisateur initialisé (taille ABI 32 octets, utilisateur actif) ; si SystemService refuse avec \`0x80940005\`, essaie \`sceLncUtilLaunchApp\` pour le même titre ;
- refuse d'interrompre un autre titre déjà au premier plan ;
- tente le lancement toutes les 3 s pendant les 12 premières tentatives, puis toutes les 30 s dans une fenêtre totale de 10 minutes pour laisser ShadowMountPlus enregistrer le titre ; ne ferme jamais un autre jeu, et garde le courtier actif après cette fenêtre ;
- fonctionne depuis l'entrée explicite dans \`/data/pldmgr/autoload.txt\` ; le marqueur historique \`/data/NiakPS5/state/autostart.enabled\` n'est plus requis ;
- ne fait rien si \`/data/NiakPS5/state/autostart.disable\` existe.

## Erreur 0x80940005 et présence réelle du payload

La console a renvoyé \`0x80940005\` avec l'ancien appel
\`sceSystemServiceLaunchApp("PPSA99386", NULL, NULL)\`. Le code est maintenant
piloté par \`launch_policy.h\` : contexte utilisateur correctement initialisé,
repli limité à cette erreur vers \`sceLncUtilLaunchApp\`, sans arrêt d'un autre
jeu, sans imitation d'un processus Sony. Une réponse positive de LncUtil
est un identifiant d'application accepté, pas un code d'erreur.

La ligne \`NiakPS5 broker process PID rc=...\` donne le PID en hexadécimal.
Le courtier écrit une preuve de présence à intervalle de deux minutes
(\`NiakPS5 broker heartbeat PID\`). Il peut être hébergé par le processus
du chargeur ELF plutôt que par un processus autonome nommé niakps5.elf.
Pour l'interface, le PING \`127.0.0.1:19187\` reste la vérification directe
du service. Le lancement peut encore échouer si le titre \`PPSA99386\` n'est
pas enregistré par le service de titres : un dossier FTP seul n'est pas
une preuve d'enregistrement. Dans ce cas il faut diagnostiquer la
registration ShadowMountPlus avant de chercher davantage de privilèges.

## Installation actuelle : glisser-déposer uniquement

L'artefact `NiakPS5-PPSA99386` est **un seul ZIP à extraire une fois**,
contenant directement l'arborescence suivante (aucun ZIP imbriqué) :

```text
data/homebrew/PPSA99386/eboot.bin
data/homebrew/PPSA99386/assets/niak-templates/{ps4,ps5}-{front,back,spine}.webp
data/pldmgr/payloads/niakps5/niakps5.elf
data/pldmgr/payloads/niakps5/niakps5.elf.json
```

Faire glisser le dossier `data/` **dans la racine `/` du FTP**, en
fusionnant les dossiers existants ; ne jamais remplacer `/data/` en entier.
Aucune commande n'est nécessaire. Le paquet n'inclut ni
`/data/pldmgr/autoload.txt` ni `pldmgr_config.txt` : l'app ne les
modifie pas non plus pendant son démarrage.

La ligne `niakps5.elf` doit déjà exister dans la configuration PLDmgr
de l'utilisateur pour un lancement automatique au prochain jailbreak.
Le dépôt d'un ELF ne peut pas créer à lui seul une entrée d'autoload.
Pour le lancement manuel, le titre doit encore être reconnu par le
service d'enregistrement de la PS5 (par exemple ShadowMountPlus).
En cas de droits insuffisants, les réglages de NiakPS5 indiquent l'état
du courtier local ; la compatibilité matérielle 13.60 n'est pas garantie.

**Sécurité :** garder le payload en lancement unique, jamais en boucle ;
`/data/NiakPS5/state/autostart.disable` désactive le service sans toucher à
l'autoload de l'utilisateur.

## Limite du remplacement du shell

Un vrai remplacement du design de \`SceShellUI\` avec ta propre disposition de menus nécessite des modifications du processus système non démontrées comme compatibles et sûres sur 13.60. Les solutions de thèmes par surcouche mémoire peuvent changer les ressources visuelles sans réécrire la partition système, mais elles ne remplacent pas le moteur de navigation et les vues React Native du shell. Il faut donc distinguer :
- **NiakPS5 UI complète au premier plan, lancée automatiquement** : cible de ce mini-payload.
- **Thème des ressources visuelles du Sony Home** : un second mode de travail, réversible, mais avec disposition Sony.
- **Remplacement du processus SceShellUI** : non pris en charge et non justifié par la validation actuelle.

## Option expérimentale : retour après la fermeture d'un jeu

L'option `--return-after-game` de l'installeur crée le marqueur `/data/NiakPS5/state/return-after-game.enabled`. Le payload reste en veille, compare l'ID de l'application au premier plan et, **seulement après avoir vu un jeu remplacer NiakPS5 puis se fermer**, tente de revenir sur l'accueil après environ dix secondes sans grand titre actif. Le moniteur est également armé quand l'utilisateur ouvre NiakPS5 manuellement, puis lance un jeu depuis son interface, même si le démarrage automatique avait échoué.

Ce mécanisme ne peut pas lire le bouton PS (intercepté par le système) et **ne peut pas remplacer le menu Sony**. Il ne se déclenche pas lorsque le jeu reste actif derrière le Control Center. Cela reste expérimental : la validation sur firmware 13.60 est indispensable avant activation. Désactivation sans désinstaller : créer `/data/NiakPS5/state/autostart.disable` ou supprimer `/data/NiakPS5/state/return-after-game.enabled`. Une réinstallation sans `--return-after-game` supprime également l'ancien marqueur de retour (sans désactiver le démarrage automatique). Le moniteur s'arrête s'il ne parvient pas à identifier l'application ou si une tentative de retour échoue. Aucun hook ni accès mémoire système.


## Comparaison avec NiakTV

Sur Android TV, `HomeRedirectService` reçoit un évènement `TYPE_WINDOW_STATE_CHANGED` d'AccessibilityService et lance `MainActivity`. Le système PS5 ne fournit pas cette API au titre NiakPS5. Le mode `--return-after-game` observe seulement les transitions entre applications PS5 en avant-plan, par périodes de deux secondes. Il ne voit ni l'appui court/long sur PS ni le contexte des fenêtres du Centre de contrôle.

Le verrou `redirect_gate.h` vérifie : un vrai autre bigapp a succédé à NiakPS5, puis une période continue d'au moins dix secondes sans grand titre actif, mesurée avec l'horloge monotone (indépendamment du nombre de requêtes réseau). Il ignore une erreur d'observation, attend au moins ~10 s avant de lancer, ne lance qu'une fois, et ne tente pas de remplacer le shell Sony. Ce mode est désactivé sans le marqueur `/data/NiakPS5/state/return-after-game.enabled`.

La redirection immédiate au bouton PS comme NiakTV nécessiterait une instrumentation spécifique de `SceShellUI`, plus invasive et non validée sur le firmware de test. Ne pas la confondre avec le mode de retour après fermeture d'un jeu.

## Authentique avatar PS5

Le payload ne lit que le profil utilisateur actuellement en avant-plan via `sceUserServiceGetForegroundUser`. Il copie, lorsqu'ils sont disponibles, `/system_data/priv/cache/profile/0x%08X/avatar.png` ou à défaut `avatar128.dds`, `avatar260.dds` ou `avatar64.dds` dans le dossier d'assets de NiakPS5. Le titre lit uniquement cette copie `/app0/assets/niak-profile.png` ou `niak-profile.dds` et décode localement les DDS BC1/DXT1 et BC3/DXT5. Aucun fichier de profil n'est ajouté au dépôt, expédié à Steam ou transféré sur Internet. **La compatibilité du chemin, des permissions et de l'affichage de l'avatar doit encore être validée sur console.**


## Installation manuelle PLDmgr (sans script FTP)

La copie de l'application reste un dossier : placer `PPSA99386/` sous
`/data/homebrew/`. Dans ce même dossier extrait, `tools/niakps5/`
contient **déjà** le payload `niakps5.elf` et son `niakps5.elf.json`,
prêts à copier ensemble sous `/data/pldmgr/payloads/niakps5/`.

Le fichier existant `/data/pldmgr/autoload.txt` doit conserver ses entrées
dans leur ordre actuel, puis se terminer par une nouvelle ligne
`niakps5.elf` (exactement ce nom, pas le chemin absolu ; aucun `!2000`
supplémentaire). **Aucune** commande Python, configuration parallèle ni
marqueur `niakps5-autostart.enabled` n'est exigé. Cette inscription dans
autoload.txt est indispensable au *premier* démarrage ; une copie passive
dans `/data/homebrew/` ne peut pas modifier la liste PLDmgr avant que
le payload ait été démarré.

Le lancement du payload crée un courtier réseau strictement local
`127.0.0.1:19187`, accessible par le titre `PPSA99386`. La bibliothèque
dépend encore des droits de lecture de l'environnement, même si le
service « Jouer » devient accessible ; aucun accès root n'est inféré.

## Initialisation du service de lancement

Le payload initialise maintenant `sceLncUtilInitialize()` après `sceUserServiceInitialize()` et journalise son code retour. Si `sceSystemServiceLaunchApp` renvoie `0x80940005`, le chemin `sceLncUtilLaunchApp` du même titre est sélectionné. Les logs `LncUtil initialize`, `sceLncUtilLaunchApp accepted app id` ou `sceLncUtilLaunchApp refused` permettent de distinguer une installation d'ELF ancienne d'un échec du repli. La présence d'un `NiakPS5 broker heartbeat PID` après deux minutes atteste que le broker est toujours résident ; un message `ready` isolé ne suffit pas.

## Retour après fermeture d'un jeu

Par défaut, un lancement **explicitement initié depuis NiakPS5** arme un retour unique après fermeture du jeu, sous réserve que PLDmgr observe le jeu en exécution puis un accueil Sony stable pendant dix secondes, avec le même utilisateur. Le bouton PS et la sortie d'un jeu ne sont pas interceptés. Un jeu nécessitant un disque ou une licence valide demeure soumis aux vérifications Sony : aucune tentative de contournement. En cas d'échec de lancement sans processus de jeu observé, le retour n'est pas déclenché. Pour désactiver cette fonction, créer le marqueur `/data/niakps5-return-after-game.disable` ; pour la réactiver, supprimer ce marqueur. Le marqueur historique `.enabled` est conservé pour compatibilité mais n'est plus nécessaire.


## Organisation permanente des fichiers

Les données durables sont regroupées dans `/data/NiakPS5/` (`assets/`, `cache/`, `inventory/`, `logs/`, `state/`). Le broker crée ces dossiers au démarrage si nécessaire ; le ZIP FTP les prépare aussi. Les anciens fichiers ne sont pas supprimés automatiquement.

`/data/homebrew/PPSA99386/` est le **titre exécutable** monté en `/app0`. Il doit rester présent tant qu'un autre mécanisme d'installation enregistré et testé ne lui succède pas ; le supprimer empêcherait le titre de démarrer. La copie du payload dans `/data/pldmgr/payloads/niakps5/` demeure une contrainte de Payload Manager.

Les caches écrits directement par l'interface peuvent encore devoir utiliser son bac à sable `/download0` si le firmware lui interdit l'accès direct à `/data/NiakPS5`. Ce dossier n'est alors pas visible sous `/data/` par FTP.
