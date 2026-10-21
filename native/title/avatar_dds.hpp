// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>
bool niak_decode_avatar_dds(const uint8_t *data,std::size_t size,
                            int &width,int &height,std::vector<uint8_t> &rgba);
