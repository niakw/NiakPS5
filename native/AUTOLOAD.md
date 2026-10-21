# WebKit Autoloader v0.5.2 : mode accueil

NiakPS5 vise un **accueil de substitution après jailbreak**, pas un remplacement du processus système protégé. Le WebKit Autoloader v0.5.2 démarre depuis une **tuile du vrai menu PS5** ; il n'est pas chargé par le firmware avant l'interface Sony.

Pour les firmwares 13.x, la documentation de l'autoloader prévoit \`/data/ps5_autoloader/autoload.txt\`, un fichier par payload dans ce dossier et des pauses \`!<millisecondes>\`. Voir [itsPLK/ps5-webkit-autoloader](https://github.com/itsPLK/ps5-webkit-autoloader).

### Mise en place

1. **D'abord tester manuellement** le bootstrap et vérifier que rond ferme l'interface vers Sony.
2. Sauvegarder l'intégralité de votre répertoire \`/data/ps5_autoloader\`. Attention à l'ordre des payloads etaHEN/kstuff/ShadowMount déjà validé.
3. Copier le même \`niakps5_bootstrap.elf\` **également dans** \`/data/ps5_autoloader/\` ; l'autoloader recherche les ELF dans son propre répertoire.
4. Préparer ou modifier \`autoload.txt\` en gardant toutes les lignes existantes et en ajoutant **à la fin, après les dépendances** :

\`\`\`text
# BEGIN NIAKPS5 - generated; use this tool to disable
!5000
niakps5_bootstrap.elf
# END NIAKPS5
\`\`\`

Le délai de 5 secondes est une **hypothèse de démarrage**, pas une valeur garantie sur PS5 13.60. Si des services ou montages ne sont pas encore disponibles, n'automatisez pas tant que l'ordre n'est pas validé.

### Script non destructif de configuration

En utilisant une copie montée ou staged du dossier \`ps5_autoloader\` (depuis Mac/Linux) :

\`\`\`sh
# Afficher le résultat sans modifier le fichier
python3 native/tools/autoload.py /chemin/ps5_autoloader/autoload.txt --enable --confirmed-manual-launch

# Une fois les tests manuels effectivement faits :
python3 native/tools/autoload.py /chemin/ps5_autoloader/autoload.txt --enable --confirmed-manual-launch --apply

# Retirer notre entrée, en laissant le reste strictement inchangé :
python3 native/tools/autoload.py /chemin/ps5_autoloader/autoload.txt --disable --apply
\`\`\`

**Sécurité :** le script refuse d'écrire ailleurs que dans \`ps5_autoloader/autoload.txt\`, crée une sauvegarde datée avant chaque modification, refuse les liens symboliques, ne supprime pas les payloads existants et détecte les marqueurs incomplets ou dupliqués. Il ne contacte jamais la PS5 et ne modifie aucun fichier système. Si le support USB contient aussi une configuration, il peut avoir priorité sur le dossier interne.

### Ce que cela permet et ce que cela ne permet pas

- **Possible si validé :** démarrer l'exploit depuis l'accueil Sony, charger la chaîne de payloads, puis afficher NiakPS5 en plein écran comme **interface principale de la session jailbreakée**.
- **Pas encore possible avec ce code :** remplacer la tuile Sony au démarrage à froid, réintercepter le bouton PS, faire survivre l'application à un reboot sans exploit, supprimer \`SceShellUI\` ou remplacer ses services.
- **Sortie :** rond ferme NiakPS5 et redonne accès au menu Sony intact.

Ne tentez pas de déplacer, désinstaller ou écraser les fichiers de Sony : cela n'est pas nécessaire à ce mode.
