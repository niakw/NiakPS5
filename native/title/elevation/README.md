# NiakPS5 one-shot filesystem access

Adapted from niakw/Prospero.Eden-Encore `headless/elevation`, originally
blackbearreloaded/ps5-native-app-boilerplate (GPL-3.0-or-later). This copy
changes the exact authorized title ID to `PPSA99386`.

Only a compatible, already running, local elfldr at 127.0.0.1:9021 can
execute the bundled helper. The helper validates its caller's PID/title ID,
cloned credentials, version and narrowly fixed filesystem capability.
Without it the GUI continues sandboxed. It never installs a resident
privilege service or grants access to another title. Any self-installation
must be restricted to NiakPS5's own PLDmgr payload files.
Firmware 13.60 behavior requires real console qualification.
