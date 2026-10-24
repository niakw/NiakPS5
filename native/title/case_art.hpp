// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
namespace hui::gfx{class Renderer;}
std::uint32_t niak_load_case_art(hui::gfx::Renderer &renderer,const char *id,const char *side, float *aspect=nullptr);

// Private user-supplied PS4/PS5 overlays (front header, back lower strip, spine).
// Loaded once per renderer session, not packaged in public GitHub sources.
std::uint32_t niak_load_case_template(hui::gfx::Renderer &renderer,const char *platform,const char *part);
void niak_release_case_templates(hui::gfx::Renderer &renderer);
// Renderer-thread only: free the case texture and update resident VRAM estimate.
void niak_destroy_case_texture(hui::gfx::Renderer &renderer,std::uint32_t &texture);
// Track GPU bytes for local game backgrounds used as reconstructed sleeve art.
void niak_track_case_texture(std::uint32_t texture,unsigned width,unsigned height);
