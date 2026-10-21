// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
namespace hui::gfx { class Renderer; }
void niak_load_daily_backdrops(hui::gfx::Renderer &renderer);
std::uint32_t niak_daily_backdrop();
