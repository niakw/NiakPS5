# NiakPS5 : démarrage via PLDmgr (configuré par défaut, réversible)

## Principe et limite

L'accueil natif reste l'application \`PPSA99386\` sous \`/data/homebrew\`. Un mini-payload de lancement, exécuté **une seule fois à la fin de la chaîne de jailbreak déjà configurée**, demande au service PS5 d'ouvrir le titre. **Aucun tap sur l'icône NiakPS5 ne devrait alors être nécessaire.**

Cela n'est PAS un remplacement de \`SceShellUI\` : l'écran Sony initial, les fonctions de sécurité, le bouton PS et le menu système continuent d'exister. Sur PS5 éteinte, rien ne peut changer avant que la chaîne jailbreak se lance. Si le titre ferme, le Sony Home reste accessible.

Le mini-payload :
- n'exécute pas de SDL, ni de composant graphique ;
- ne remonte pas \`/system_ex\`, n'attache pas \`SceSysCore\`, n'effectue aucun \`ptrace\` ou modification système ;
- demande le lancement du titre avec un contexte utilisateur initialisé (taille ABI 32 octets, utilisateur actif) ; si SystemService refuse avec \`0x80940005\`, essaie \`sceLncUtilLaunchApp\` pour le même titre ;
- refuse d'interrompre un autre titre déjà au premier plan ;
- tente le lancement toutes les 3 s pendant les 12 premières tentatives, puis toutes les 30 s dans une fenêtre totale de 10 minutes pour laisser ShadowMountPlus enregistrer le titre ; ne ferme jamais un autre jeu, et garde le courtier actif après cette fenêtre ;
- fonctionne depuis l'entrée explicite dans \`/data/pldmgr/autoload.txt\` ; le marqueur historique \`/data/niakps5-autostart.enabled\` n'est plus requis ;
- ne fait rien si \`/data/niakps5-autostart.disable\` existe.

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

## Installation actuelle (une seule commande)

L'archive contient l'application native `PPSA99386/eboot.bin`, l'installeur
`PPSA99386/tools/ftp_install.py` et son payload compagnon
`PPSA99386/tools/niakps5/niakps5.elf`.

Depuis l'ordinateur connecté à la PS5, après extraction du ZIP :

```sh
python3 PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5
```

Cette commande installe le titre et **configure PLDmgr par défaut** pour charger
le payload compagnon en dernier, après les autres payloads conservés. Elle active
son marqueur privé et peut copier les jaquettes ainsi que les gabarits présents.
Pour une installation complète qui **remplace aussi niakps5.elf**
sans réécrire `autoload.txt`, la configuration PLDmgr ni les marqueurs
existants (mode conseillé si PLDmgr est déjà configuré) :

```sh
python3 PPSA99386/tools/ftp_install.py --host IP_DE_LA_PS5 --preserve-autoload
```

Pour transférer uniquement le titre sans le payload, utiliser
`--no-autoload`. Pour une inspection strictement en lecture seule, utiliser
`--status`.

Copier seulement le dossier par FTP n'ajoute pas automatiquement un payload à
une liste PLDmgr existante : le script doit être exécuté pour cette étape.
Le service local « Jouer » ne devient disponible qu'après exécution effective
du payload par la chaîne de jailbreak ; un binaire copié ne suffit pas.
La compatibilité PS5 13.60 doit encore être testée sur matériel.

Après jailbreak, Réglages NiakPS5 affiche si le service local PLDmgr répond
réellement. En cas de problème, consulter le diagnostic `--status` et le journal
`/data/niakps5-autostart.log`. Une ancienne trace de succès n'est pas une preuve
de fonctionnement du démarrage actuel.

**Désactivation immédiate :** enlever \`niakps5.elf\` de la chaîne ou supprimer \`/data/niakps5-autostart.enabled\`. Option sans modification de la chaîne : créer \`/data/niakps5-autostart.disable\`.

**Sécurité :** ne pas programmer ce payload à répétition pendant le jeu et ne pas le déclencher à chaque retour au Sony Home : cela provoquerait une boucle de lancement. C'est un *one-shot* à la fin du jailbreak.

## Limite du remplacement du shell

Un vrai remplacement du design de \`SceShellUI\` avec ta propre disposition de menus nécessite des modifications du processus système non démontrées comme compatibles et sûres sur 13.60. Les solutions de thèmes par surcouche mémoire peuvent changer les ressources visuelles sans réécrire la partition système, mais elles ne remplacent pas le moteur de navigation et les vues React Native du shell. Il faut donc distinguer :
- **NiakPS5 UI complète au premier plan, lancée automatiquement** : cible de ce mini-payload.
- **Thème des ressources visuelles du Sony Home** : un second mode de travail, réversible, mais avec disposition Sony.
- **Remplacement du processus SceShellUI** : non pris en charge et non justifié par la validation actuelle.

## Option expérimentale : retour après la fermeture d'un jeu

L'option `--return-after-game` de l'installeur crée le marqueur `/data/niakps5-return-after-game.enabled`. Le payload reste en veille, compare l'ID de l'application au premier plan et, **seulement après avoir vu un jeu remplacer NiakPS5 puis se fermer**, tente de revenir sur l'accueil après environ dix secondes sans grand titre actif. Le moniteur est également armé quand l'utilisateur ouvre NiakPS5 manuellement, puis lance un jeu depuis son interface, même si le démarrage automatique avait échoué.

Ce mécanisme ne peut pas lire le bouton PS (intercepté par le système) et **ne peut pas remplacer le menu Sony**. Il ne se déclenche pas lorsque le jeu reste actif derrière le Control Center. Cela reste expérimental : la validation sur firmware 13.60 est indispensable avant activation. Désactivation sans désinstaller : créer `/data/niakps5-autostart.disable` ou supprimer `/data/niakps5-return-after-game.enabled`. Une réinstallation sans `--return-after-game` supprime également l'ancien marqueur de retour (sans désactiver le démarrage automatique). Le moniteur s'arrête s'il ne parvient pas à identifier l'application ou si une tentative de retour échoue. Aucun hook ni accès mémoire système.


## Comparaison avec NiakTV

Sur Android TV, `HomeRedirectService` reçoit un évènement `TYPE_WINDOW_STATE_CHANGED` d'AccessibilityService et lance `MainActivity`. Le système PS5 ne fournit pas cette API au titre NiakPS5. Le mode `--return-after-game` observe seulement les transitions entre applications PS5 en avant-plan, par périodes de deux secondes. Il ne voit ni l'appui court/long sur PS ni le contexte des fenêtres du Centre de contrôle.

Le verrou `redirect_gate.h` vérifie : un vrai autre bigapp a succédé à NiakPS5, puis une période continue d'au moins dix secondes sans grand titre actif, mesurée avec l'horloge monotone (indépendamment du nombre de requêtes réseau). Il ignore une erreur d'observation, attend au moins ~10 s avant de lancer, ne lance qu'une fois, et ne tente pas de remplacer le shell Sony. Ce mode est désactivé sans le marqueur `/data/niakps5-return-after-game.enabled`.

La redirection immédiate au bouton PS comme NiakTV nécessiterait une instrumentation spécifique de `SceShellUI`, plus invasive et non validée sur le firmware de test. Ne pas la confondre avec le mode de retour après fermeture d'un jeu.

## Authentique avatar PS5

Le payload ne lit que le profil utilisateur actuellement en avant-plan via `sceUserServiceGetForegroundUser`. Il copie, lorsqu'ils sont disponibles, `/system_data/priv/cache/profile/0x%08X/avatar.png` ou à défaut `avatar128.dds`, `avatar260.dds` ou `avatar64.dds` dans le dossier d'assets de NiakPS5. Le titre lit uniquement cette copie `/app0/assets/niak-profile.png` ou `niak-profile.dds` et décode localement le DDS DXT5. Aucun fichier de profil n'est ajouté au dépôt, expédié à Steam ou transféré sur Internet. **La compatibilité du chemin, des permissions et de l'affichage de l'avatar doit encore être validée sur console.**


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
