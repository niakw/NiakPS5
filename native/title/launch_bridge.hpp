// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Return 0 only after PLDmgr's privileged local service accepted the launch.
// -2: no local service, -3: rejected title/protocol, negative OS code otherwise.
int niak_launch_registered_title(const char *title_id);

// Read-only actual broker liveness check, not just an autoload config marker.
bool niak_launch_broker_ready();
// Last bounded PING stage + errno; no proof of active service from the log.
const char *niak_launch_broker_diagnostic();
// Exact live PID from STATUS over loopback; zero means unavailable.
unsigned niak_launch_broker_pid();

// Request the PS5 system settings deep link. Sandbox/firmware may reject it.
// Returns raw SystemService status; a 0 is acceptance, not display proof.
int niak_open_system_settings();
