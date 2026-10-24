# Contributing / Contribuer

[Français](#français) · [English](#english)

## Français

Merci de contribuer à NiakPS5. Le projet conserve **une seule branche de référence, `main`** : proposez les modifications dans une pull request sans publier de données de votre console.

Avant de soumettre : vérifiez la compilation native lorsque le changement touche la PS5, lancez `python3 -m unittest discover -s native/title/tests -p 'test_*.py'`, documentez la cause du problème et ajoutez un test reproductible si possible. Les captures publiques doivent provenir du moteur de rendu OpenGL de démonstration, pas d'une image fictive ou d'une capture contenant un profil personnel.

Respectez les métadonnées officielles et les licences tierces : ne placez aucun scan commercial LaunchBox, copie de jeux, FPKG, clé d'API, journal FTP, identifiant de compte ou adresse IP privée dans le dépôt. Les corrections d'accès au système doivent limiter les privilèges et ne jamais modifier les fichiers Sony ou supprimer des données sans nécessité.

Pour les bugs, utilisez le modèle d'issue PS5. Pour les vulnérabilités, consultez [SECURITY.md](SECURITY.md) avant de publier des détails.

## English

Contribute through a pull request targeting the single reference branch **`main`**. Explain the problem, include a regression test where practical, run the Python tests above, and check the native PS5 build for console-facing changes.

Never commit personal console data, private screenshots, commercial box scans, game binaries, FTP credentials, API tokens, or private IP addresses. Use genuine OpenGL-renderer previews with sample data. Keep changes scoped and preserve third-party license notices. Report security issues privately as described in [SECURITY.md](SECURITY.md).
