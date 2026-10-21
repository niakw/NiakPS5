/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef NIAK_SHADOWMOUNT_API_H
#define NIAK_SHADOWMOUNT_API_H
#include "catalog.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Read-only loopback API; -1 means unavailable, 0 means no games. */
int niak_scan_shadowmount(NiakGame *games, size_t capacity);
/* Parse bounded JSON from documented POST /api/v1/games. */
int niak_parse_shadowmount_games(const char *json, NiakGame *games, size_t capacity);
#ifdef __cplusplus
}
#endif
#endif
