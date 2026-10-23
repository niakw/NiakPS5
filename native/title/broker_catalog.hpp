// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstddef>
extern "C" {
#include "niak/catalog.h"
}
// Read-only inventory through the already-resident PLDmgr launch broker.
int niak_scan_broker_games(NiakGame *games,std::size_t cap);
