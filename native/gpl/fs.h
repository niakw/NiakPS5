/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once

#include <stddef.h>
#include <stdint.h>

uint8_t *fs_readfile(const char *path, size_t *size);
