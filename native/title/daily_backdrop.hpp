// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
namespace hui::gfx { class Renderer; }
void niak_load_daily_backdrops(hui::gfx::Renderer &renderer,
                               const char *directory="/app0/assets/niak-daily");
std::uint32_t niak_daily_backdrop();
// Only the explicit Settings action selects another packaged wallpaper for today.
void niak_next_daily_backdrop();
