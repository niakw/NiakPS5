// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
namespace niak {
// -1 means no local elfldr/elevation, -2 means validation/install failed;
//  0 already current, 1 own PLDmgr payload updated.
int bootstrap_own_payload() noexcept;
}
