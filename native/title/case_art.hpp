// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
namespace hui::gfx{class Renderer;}
std::uint32_t niak_load_case_art(hui::gfx::Renderer &renderer,const char *id,const char *side);

// Private user-supplied PS4/PS5 overlays (front header, back lower strip, spine).
// Loaded once per renderer session, not packaged in public GitHub sources.
std::uint32_t niak_load_case_template(hui::gfx::Renderer &renderer,const char *platform,const char *part);
