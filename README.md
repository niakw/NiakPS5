# NiakPS5

**Votre console. Votre espace.** Une proposition d'accueil PS5 inspirée de [NiakTV](https://github.com/niakw/NiakTV) : même direction artistique, adaptée aux grandes jaquettes de jeux, à la navigation DualSense et à un fond de jeu du moment.

> **État : interface web de démonstration.** Ce dépôt ne remplace **pas** le shell de la PS5, ne contourne aucune protection et ne sait pas encore lancer des jeux ou lire les données système de la console. Un hôte natif compatible, à développer et valider séparément, est nécessaire. Les jeux visibles par défaut sont des **exemples**, pas des titres détectés sur votre console.

## Direction artistique

- Fond sombre en couches, accent menthe \`#91f5df\`, contrepoint violet \`#b5a4ff\`.
- Manrope (navigation) et Instrument Serif (titre cinéma), comme NiakTV ; polices embarquées et notices OFL.
- Icônes SVG au trait de la même famille, focus 2 px menthe + halo, survol et sélection manette cohérents.
- Barre haute à la PS5 (Jeux / Multimédia, recherche, notifications, réglages, profil), vedette immersive, rail des jaquettes, raccourcis console.
- Fond de **jeu récent sorti** plutôt que fond de film TMDB : sélection éditoriale 2025–2026, rotation quotidienne locale, adaptation au jeu survolé/sélectionné, transition douce.
- Palettes Menthe / Violet / Bleu / Graphite, fond Jeu / Dégradé / Uni, mode performance, navigation dans la bibliothèque complète et animations réduites selon le système.
- Aucun framework, aucune télémétrie, aucune publicité. Les fonctions de base sont consultables hors ligne ; les visuels de jeux nécessitent une connexion tant qu'ils ne sont pas mis en cache par un hôte natif.

## Tester l'interface

Le site est statique et fonctionne sans compilation. Un serveur local suffit :

\`\`\`sh
python3 -m http.server 8080
# Ouvrir http://localhost:8080/
\`\`\`

Clavier : flèches (déplacement), Entrée (valider), Échap/Retour arrière (retour), **T** (réglages).
DualSense via Gamepad API si le navigateur la rend disponible : croix confirmer, rond retour, triangle réglages, carré bibliothèque, croix directionnelle / sticks déplacement. Le bouton PS reste géré par le système, pas par l'app.

\`\`\`sh
npm test
\`\`\`

## Données et intégration PS5

L'API de présentation ne suppose aucune lecture libre du système. Lorsque l'hôte PS5 fournira une liste de jeux autorisée :

\`\`\`js
window.NiakPS5.setLibrary([
  {
    id: "CUSA00000", title: "Exemple installé", installed: true,
    year: 2026, genre: "Action", description: "Description",
    // Image locale servie par le même hôte :
    cover: "/art/cover.webp", hero: "/art/hero.webp"
  }
]);
window.NiakPS5Bridge = {
  launchGame: async id => { /* appel natif autorisé */ },
  captures: async () => { /* optionnel */ },
  downloads: async () => { /* optionnel */ },
  friends: async () => { /* optionnel */ },
  notifications: async () => { /* optionnel */ },
  profile: async () => { /* optionnel */ }
};
\`\`\`

Le frontend refuse les URLs d'images arbitraires : uniquement les ressources Steam explicites et les chemins locaux \`/art/\`. L'identifiant de jeu est traité comme opaque. **Aucun lancement, installation, nettoyage ou modification système n'est simulé comme réussi.** Les appels sans hôte affichent un message explicite.

## Fonds de jeux récents

Les jeux d'exemple sont stockés dans \`src/catalog.js\`. Une date de sortie est utilisée pour ne pas présenter un jeu futur comme sorti. Un jeu est sélectionné de manière déterministe chaque jour, ou le plus récent si la rotation est désactivée.

Visuels d'illustration : CDN Steam via les identifiants des fiches de jeux, dont PRAGMATA (2026), Resident Evil Requiem (2026) et Clair Obscur: Expedition 33 (2025). Les visuels peuvent être indisponibles, auquel cas les dégradés et pictogrammes locaux restent visibles. Steam sert seulement d'illustration pour la démo, **pas** de source d'information sur les installations PS5. Les métadonnées devront être mises à jour (ou fournies par un futur service de catalogue) pour refléter automatiquement les prochaines sorties.

## Lanceur PS5 natif (développement)

Un premier socle natif SDL2, lecteur de jeux installés et bootstrap ELF réversible est désormais dans [`native/`](native/README.md). Il vise à devenir l’accueil quotidien de la console avec la même DA que NiakTV. **Il ne remplace pas le processus protégé `SceShellUI` et n’a pas encore été validé sur une PS5 physique.** La compilation SDL2 sur Linux et les tests de base de données sont exécutés en CI séparément ; ils ne prouvent pas que le binaire PS5 fonctionne sur le firmware cible.

## Étapes natives restant à faire

1. Compiler les ELF à partir du SDK PS5/PacBrew et valider le bootstrap bigapp sur le firmware cible, sans modifier le shell système.
2. Fournir une bibliothèque et des miniatures depuis une API native locale contrôlée ; l'interface ne scanne pas elle-même les partitions.
3. Implémenter et valider les appels d'ouverture de jeu et les fonctions système une par une.
4. Tester DualSense, mémoire, cache des images, mode hors ligne et performances **sur la console réelle**.
5. Traiter séparément la question d'un accueil système par défaut ; cette possibilité n'est pas démontrée par ce prototype.

## Licence et crédits

Projet sous **GPL-3.0-or-later**. Direction artistique adaptée du projet NiakTV du même auteur. Manrope et Instrument Serif : licences SIL Open Font License, notices conservées sous \`fonts/\`. Les artworks et marques des jeux demeurent la propriété de leurs ayants droit. NiakPS5 n'est ni affilié ni approuvé par Sony ou Valve.
