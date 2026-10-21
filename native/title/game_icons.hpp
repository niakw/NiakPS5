// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
namespace hui::gfx { class Renderer; }
std::uint32_t niak_load_game_icon(hui::gfx::Renderer &renderer,const char *title_id);

std::uint32_t niak_load_local_png(hui::gfx::Renderer &renderer,const char *path);
