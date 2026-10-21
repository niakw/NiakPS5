/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef NIAKPS5_CATALOG_H
#define NIAKPS5_CATALOG_H
#include <stddef.h>
#define NIAKPS5_MAX_GAMES 256
typedef struct {
  char id[16];
  char title[192];
  char icon[512];
  char background[512];
} NiakGame;
/* Read-only catalogue; checks installed app directories and excludes shell titles. */
int niak_scan_games(const char *database_path, const char *filesystem_root,
                    NiakGame *games, size_t capacity);
int niak_valid_title_id(const char *id);
#endif
