// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Return 0 only after PLDmgr's privileged local service accepted the launch.
// -2: no local service, -3: rejected title/protocol, negative OS code otherwise.
int niak_launch_registered_title(const char *title_id);
