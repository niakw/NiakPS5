// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Read-only-on-the-UI-thread statistics for *successfully created GPU textures*.
// A zero count does not distinguish absence from sandbox permission failures.
namespace niak {
struct CaseMediaStats {
    unsigned titles=0;
    unsigned fronts=0;
    unsigned backs=0;
    unsigned spines=0;
    unsigned scenes=0;
    unsigned icons=0;
    unsigned templates=0;
};
inline CaseMediaStats case_media_stats{};
}
