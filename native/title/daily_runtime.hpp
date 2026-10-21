// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
#include <vector>
// Strict HTTPS only, official PlayStation image host; never includes console
// profile, installed games, FTP IPs or account identifiers.
bool niak_fetch_latest_ps5_wallpaper(const char *today_yyyy_mm_dd,
                                    std::uint32_t selection_seed,
                                    std::vector<std::uint8_t> &png);
