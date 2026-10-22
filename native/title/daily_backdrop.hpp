// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
namespace hui::gfx { class Renderer; }
void niak_load_daily_backdrops(hui::gfx::Renderer &renderer,
                               const char *directory="/app0/assets/niak-daily");
std::uint32_t niak_daily_backdrop();
// R1 previews the next locally packaged wallpaper without changing today's date.
void niak_next_daily_backdrop();
