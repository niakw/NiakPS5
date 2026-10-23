// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
namespace niak {
// Status of the one-shot install attempt in this running GUI process.
// -99: not attempted (host preview), -1: no helper/elevation, -2: failed,
//  0: already current, 1: updated (broker reload requires next jailbreak).
inline int payload_install_status = -99;
// -1 means no local elfldr/elevation, -2 means validation/install failed;
//  0 already current, 1 own PLDmgr payload updated.
int bootstrap_own_payload() noexcept;
}
