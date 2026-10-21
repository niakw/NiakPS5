/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef NIAKPS5_UI_TEXT_CACHE_H
#define NIAKPS5_UI_TEXT_CACHE_H
#include <SDL.h>
#include <SDL_ttf.h>
#include <stdint.h>
#define NIAK_TEXT_CACHE_SIZE 128
#define NIAK_TEXT_MAX 192
typedef struct {TTF_Font *font; SDL_Color color; char value[NIAK_TEXT_MAX]; SDL_Texture *texture;int width,height;uint64_t use;} NiakTextEntry;
typedef struct {NiakTextEntry entries[NIAK_TEXT_CACHE_SIZE];uint64_t counter;} NiakTextCache;
void niak_text_draw(NiakTextCache *cache,SDL_Renderer *renderer,TTF_Font *font,const char *value,int x,int y,SDL_Color color,int max_width);
void niak_text_clear(NiakTextCache *cache);
#endif
