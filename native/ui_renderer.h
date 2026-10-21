/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef NIAKPS5_UI_RENDERER_H
#define NIAKPS5_UI_RENDERER_H
#include <SDL.h>
/* Tries platform-supported hardware renderer, then reliable software fallback. */
SDL_Renderer *niak_renderer_create(SDL_Window *window, char *description, size_t capacity);
#endif
