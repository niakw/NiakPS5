// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
const char *niak_ps5_user_label();

#include <cstdint>
namespace hui::gfx {class Renderer;}
void niak_profile_load_avatar(hui::gfx::Renderer &renderer);
std::uint32_t niak_profile_avatar();
