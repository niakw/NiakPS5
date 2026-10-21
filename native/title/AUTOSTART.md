# NiakPS5 : accueil automatique après jailbreak (optionnel, réversible)

## Principe et limite

L'accueil natif reste l'application \`PPSA99386\` sous \`/data/homebrew\`. Un mini-payload de lancement, exécuté **une seule fois à la fin de la chaîne de jailbreak déjà configurée**, demande au service PS5 d'ouvrir le titre. **Aucun tap sur l'icône NiakPS5 ne devrait alors être nécessaire.**

Cela n'est PAS un remplacement de \`SceShellUI\` : l'écran Sony initial, les fonctions de sécurité, le bouton PS et le menu système continuent d'exister. Sur PS5 éteinte, rien ne peut changer avant que la chaîne jailbreak se lance. Si le titre ferme, le Sony Home reste accessible.

Le mini-payload :
- n'exécute pas de SDL, ni de composant graphique ;
- ne remonte pas \`/system_ex\`, n'attache pas \`SceSysCore\`, n'effectue aucun \`ptrace\` ou modification système ;
- attend que le titre soit enregistré puis appelle \`sceSystemServiceLaunchApp("PPSA99386")\` dans la session de l'utilisateur ;
- refuse d'interrompre un autre titre déjà au premier plan ;
- réessaie au maximum 12 fois (3 s entre essais), puis abandonne ;
- ne fait rien tant que le fichier \`/data/niakps5-autostart.enabled\` est absent ;
- ne fait rien si \`/data/niakps5-autostart.disable\` existe.

## Installation

1. Installer le dossier \`/data/homebrew/PPSA99386\` complet.
2. Charger Kstuff et ShadowMountPlus dans l'ordre habituel et vérifier que la tuile NiakPS5 existe. **Tester une fois le lancement manuel du titre natif et son retour au Sony Home.**
3. Créer un fichier vide \`/data/niakps5-autostart.enabled\` par FTP. Cela constitue une activation explicite.
4. Installer \`niakps5_autostart.elf\` comme **dernier payload de la liste d'autochargement** de ton WebKit Autoloader / Payload Manager, APRES Kstuff et ShadowMountPlus. Adapter sa configuration à la version installée ; ne pas remplacer l'autoloader, ni écraser les autres payloads.
5. Relancer le jailbreak : NiakPS5 devrait s'ouvrir une fois le titre enregistré. Voir \`/data/niakps5-autostart.log\` pour les résultats. Les codes et les services dépendent du firmware ; cette procédure n'a **pas encore été vérifiée sur ta PS5 13.60**.

**Désactivation immédiate :** enlever \`niakps5_autostart.elf\` de la chaîne ou supprimer \`/data/niakps5-autostart.enabled\`. Option sans modification de la chaîne : créer \`/data/niakps5-autostart.disable\`.

**Sécurité :** ne pas programmer ce payload à répétition pendant le jeu et ne pas le déclencher à chaque retour au Sony Home : cela provoquerait une boucle de lancement. C'est un *one-shot* à la fin du jailbreak.

## Limite du remplacement du shell

Un vrai remplacement du design de \`SceShellUI\` avec ta propre disposition de menus nécessite des modifications du processus système non démontrées comme compatibles et sûres sur 13.60. Les solutions de thèmes par surcouche mémoire peuvent changer les ressources visuelles sans réécrire la partition système, mais elles ne remplacent pas le moteur de navigation et les vues React Native du shell. Il faut donc distinguer :
- **NiakPS5 UI complète au premier plan, lancée automatiquement** : cible de ce mini-payload.
- **Thème des ressources visuelles du Sony Home** : un second mode de travail, réversible, mais avec disposition Sony.
- **Remplacement du processus SceShellUI** : non pris en charge et non justifié par la validation actuelle.
