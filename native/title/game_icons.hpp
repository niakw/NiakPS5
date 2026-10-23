// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
namespace hui::gfx { class Renderer; }
std::uint32_t niak_load_game_icon(hui::gfx::Renderer &renderer,const char *title_id);

// Optional locally installed wide pic1.png for the outer 3D case.
// Never crop/replace the application's existing 2D library icon.
std::uint32_t niak_load_game_background(hui::gfx::Renderer &renderer,const char *title_id,float *aspect=nullptr);

std::uint32_t niak_load_local_png(hui::gfx::Renderer &renderer,const char *path);

// Best-effort current PS5 user cache read; no network or account upload.
std::uint32_t niak_load_profile_cache_png(hui::gfx::Renderer &renderer,unsigned user);
