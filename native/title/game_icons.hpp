// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
#include <vector>
namespace hui::gfx { class Renderer; }
std::uint32_t niak_load_game_icon(hui::gfx::Renderer &renderer,const char *title_id);
// Requeue a missing icon after an outage without touching disk, HTTP or GPU.
// Safe to invoke periodically while navigation is idle.
void niak_request_missing_game_icon(const char *title_id);
// Renderer-thread poll: completes one queued icon, without network waits.
// Returns texture and writes its title ID; caller owns and must release GPU handle.
std::uint32_t niak_take_downloaded_game_icon(hui::gfx::Renderer &renderer,
                                             char (&title_id)[16],
                                             bool (*accept)(const char *,void *)=nullptr,
                                             void *opaque=nullptr);

// Optional locally installed wide pic1.png for the outer 3D case.
// Never crop/replace the application's existing 2D library icon.
std::uint32_t niak_load_game_background(hui::gfx::Renderer &renderer,const char *title_id,float *aspect=nullptr);
// Poll a locally decoded pic1 / scene result on the graphics thread.
std::uint32_t niak_take_downloaded_game_background(
    hui::gfx::Renderer &renderer,char (&title_id)[16],float *aspect=nullptr,
    const char *expected_id=nullptr);

std::uint32_t niak_load_local_png(hui::gfx::Renderer &renderer,const char *path);

// Best-effort current PS5 user cache read; no network or account upload.
std::uint32_t niak_load_profile_cache_png(hui::gfx::Renderer &renderer,unsigned user);

// CPU-only avatar PNG preparation. Call from profile worker, never the GL thread.
bool niak_prepare_profile_png_file(const char *path,
                                   std::vector<std::uint8_t> &pixels);
