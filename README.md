# NiakPS5

**Your library. Your controller. Your PS5.**

A **native, full-screen home interface** for homebrew-enabled PS5 consoles, with DualSense navigation, games and apps, local launching, and animated PS4/PS5 3D cases.

[Français](README.fr.md) · [Technical notes](native/title/README.en.md) · [Builds and previews](https://github.com/niakw/NiakPS5/actions/workflows/native-title.yml)

![Actual NiakPS5 OpenGL home interface under Mesa with sample data](docs/images/niakps5-home.png)

*Real OpenGL renderer preview under Mesa with sample data. Not a design mockup or a screenshot captured directly from a PS5.*

## Built for the controller

Use your DualSense to browse **Games**, **Applications**, and **Settings**. Explore installed titles, available game information, daily wallpapers, and animated 3D cases without a web browser.

### Artwork refreshes automatically

NiakPS5 prioritizes genuine LaunchBox front, back, and spine scans. When artwork is missing, the title **tries to fetch known public-index images itself** on a background thread, convert JPEG/PNG to its private cache, and use them on the **next app launch**. A separate Mac script is not needed for this automatic attempt.

HTTPS access depends on the console sandbox, firmware, and LaunchBox availability. If media cannot be fetched, NiakPS5 keeps a consistent reconstructed case with the correct PS4/PS5 elements. Third-party commercial scans are not distributed in the GitHub package.

Game descriptions use **up to three short sentences** from available sources, rather than fabricated or full-length essays. LaunchBox summaries are often in English; if no French version is available, the original text remains. NiakPS5 does not automatically translate the entire catalog.

## Project status

On the PS5 13.60 test console, the local service discovered **48 titles**, the library appeared, and **Play** successfully launched a game. Recent fixes for app classification, native artwork downloads, system-settings access, and return-after-game still require hardware verification. CI checks compilation and genuine Mesa/OpenGL previews separately.

## Install or update

1. Download **`NiakPS5-PPSA99386`** from a [successful `main` workflow run](https://github.com/niakw/NiakPS5/actions/workflows/native-title.yml).
2. Extract it once and **merge** the top-level **`data/`** folder into the PS5 FTP root **`/`**. **Do not delete** existing folders.
3. Open the registered title **`PPSA99386`**. The companion PLDmgr payload is already included in the same tree.

The package does **not** edit `autoload.txt`, PLDmgr settings, or Sony system files. Keep an existing working autoload configuration; a basic FTP folder copy cannot activate a missing one.

Artwork refresh is built into the title. Separate FTP scripts are documented **only as troubleshooting tools** in the [technical notes](native/title/README.md), not as a normal setup requirement.

## Privacy and limitations

NiakPS5 does not intercept the PS button, replace `SceShellUI`, or bypass disc or license checks. The launch broker is bound to `127.0.0.1`. Automatic cover requests send only public CDN filenames, not personal PS5 profiles or console title IDs. Third-party artwork remains the property of its respective owners.

**GPL-3.0-or-later**, with third-party licenses preserved. Independent homebrew project; not affiliated with Sony or LaunchBox.
