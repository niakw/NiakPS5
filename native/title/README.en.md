# NiakPS5 — technical notes

[Main README (English)](../../README.md) · [Documentation française](README.md) · [Release checks](../../docs/QA_CHECKLIST.md)

## Architecture

The PS5 title (`PPSA99386`) uses the native GPU renderer and a loopback-only launch broker supplied as a companion PLDmgr ELF. Game inventory merges multiple verified sources, including installed-title metadata, without assuming that every homebrew title is a game. Apps are displayed as icons; genuine PS4/PS5 game cases rotate in 3D.

Missing cover media is queried against the packaged LaunchBox **metadata index**. The native background worker attempts to download strictly allowlisted CDN filenames, validate/resize JPEG or PNG images, and store them under the title's private cache. The index distinguishes box fronts, backs, spines, background fanart, gameplay and game-title screenshots. Downloads still depend on PS5 sandbox HTTPS permissions; an unavailable resource must not make the library unusable.

Official scanned fronts and backs bypass reconstruction. Missing faces use one opaque printed sheet beneath the artwork, text, platform strip and genuine alpha overlays. Reconstructed backs may use background fanart and two distinct screenshots. Apps do not get retail-game boxes.

Game descriptions display no more than three sourced sentences (360 characters). The original English stays when a verified French translation is unavailable; no bulk translation is invented.

## Quality gates

The GitHub workflows validate host source tests, the native PS5 build, six real Mesa/OpenGL 3D-case views, the native home screenshot and a single drag-and-drop `data/` FTP package. Their success does **not** prove native HTTPS downloads, PS5 settings deep links or game-return behavior on physical hardware. Check [release readiness](../../docs/QA_CHECKLIST.md) before requesting another console test.

## Safe installation

Merge the **single** extracted `data/` directory into the PS5 FTP root; never erase existing folders. Preserve the owner's working PLDmgr configuration and autoload entries. No external artwork application, full-system override, account information or API key is required by the title.

`ftp_install.py` and other host scripts remain available for **diagnosis and repair only**, not as a normal requirement to obtain covers. The package ships public image filenames and metadata, not commercial retail artwork.

## Security and privacy

Never commit logs containing console identities, FTP credentials, private screenshots, profile images, system keys, private addresses or installation databases. The privacy scanner is run in CI. For responsible disclosure, consult [SECURITY.md](../../SECURITY.md). Third-party dependencies retain their copyright and license notices.

### Selection-only artwork (Eden Encore parity)

Unlike earlier NiakPS5 builds, scrolling through the full game list **does not start CDN downloads**. Focusing a single game queues only its own LaunchBox image IDs, giving genuine front/back scans priority. Switching selection cancels any still-pending work for the previous game. Existing offline files may still appear for other titles; those do not trigger network requests. A successfully downloaded, atomically cached PNG is uploaded to the selected game's 3D case by the renderer within the same session. The worker accepts bounded original JPEG/PNG bodies up to 16 MiB (the same cap used by Eden Encore), then validates dimensions and reduces resolution for the smaller native cache. Runtime PS5 HTTPS permission remains a separate, on-console condition.
