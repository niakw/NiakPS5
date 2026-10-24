// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
#include <vector>
// Strict HTTPS only, official PlayStation image host; never includes console
// profile, installed games, FTP IPs or account identifiers.
bool niak_fetch_latest_ps5_wallpaper(const char *today_yyyy_mm_dd,
                                    std::uint32_t selection_seed,
                                    std::vector<std::uint8_t> &png);

// Download a strictly whitelisted public LaunchBox CDN image. No API key,
// game title, profile or console identifier is sent. PS5-only.
bool niak_fetch_launchbox_asset(const char *filename,
                               std::vector<std::uint8_t> &bytes);
bool niak_fetch_launchbox_asset_ex(const char *filename,
                               std::vector<std::uint8_t> &bytes,int *failure,
                               int *failure_stage=nullptr);
