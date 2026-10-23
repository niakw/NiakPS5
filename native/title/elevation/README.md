# NiakPS5 one-shot filesystem access

Adapted from niakw/Prospero.Eden-Encore `headless/elevation`, originally
blackbearreloaded/ps5-native-app-boilerplate (GPL-3.0-or-later). This copy
changes the exact authorized title ID to `PPSA99386`.

Only a compatible, already running, local elfldr at 127.0.0.1:9021 can
execute the bundled helper. The helper validates its caller's PID/title ID,
cloned credentials, version and narrowly fixed filesystem capability.
Without it the GUI continues sandboxed. It never installs a resident
privilege service or grants access to another title. Any self-installation
must be restricted to NiakPS5's own PLDmgr payload files. As in Encore,
a rollback failure or failed elevation that changes the caller's UID/GID
causes immediate termination instead of continuing in an ambiguous state.

The FTP installer must stage the two verified payload assets into
`/data/homebrew/PPSA99386/tools/niakps5/` for the GUI's `/app0/tools/`
source path to exist. It does this only with `--autoload` or
`--preserve-autoload`; `--no-autoload` leaves this opt-in step disabled.
No installer Python script is uploaded to the console title.
The in-app one-shot helper copies ONLY the app's own PLDmgr ELF/JSON.
It checks the existing autoload entry read-only; the application NEVER
edits autoload.txt itself. A missing entry requires the explicit FTP
installer --autoload operation (or the owner's own PLDmgr setup).
Firmware 13.60 behavior requires real console qualification.
