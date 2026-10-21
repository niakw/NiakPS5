/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "ui_text_cache.h"
#include <stdio.h>
#include <string.h>
static int same_color(SDL_Color a,SDL_Color b){return a.r==b.r&&a.g==b.g&&a.b==b.b&&a.a==b.a;}
void niak_text_clear(NiakTextCache *cache){
 if(!cache)return;
 for(int i=0;i<NIAK_TEXT_CACHE_SIZE;i++){if(cache->entries[i].texture)SDL_DestroyTexture(cache->entries[i].texture);cache->entries[i]=(NiakTextEntry){0};}
 cache->counter=0;
}
void niak_text_draw(NiakTextCache *cache,SDL_Renderer *renderer,TTF_Font *font,const char *value,int x,int y,SDL_Color color,int max_width){
 if(!renderer || !font || !value || !*value)return;
 size_t length=strlen(value);
 if(length>=NIAK_TEXT_MAX)length=NIAK_TEXT_MAX-1;
 NiakTextEntry *entry=NULL;
 if(cache){
  NiakTextEntry *victim=&cache->entries[0];
  for(int i=0;i<NIAK_TEXT_CACHE_SIZE;i++){
   NiakTextEntry *candidate=&cache->entries[i];
   if(candidate->texture&&candidate->font==font&&same_color(candidate->color,color)&&strlen(candidate->value)==length&&memcmp(candidate->value,value,length)==0){
    entry=candidate;break;
   }
   if(!candidate->texture||candidate->use<victim->use)victim=candidate;
  }
  if(!entry){
   SDL_Surface *surface=TTF_RenderUTF8_Blended(font,value,color);if(!surface)return;
   SDL_Texture *texture=SDL_CreateTextureFromSurface(renderer,surface);
   int w=surface->w,h=surface->h;SDL_FreeSurface(surface);
   if(!texture)return;
   if(victim->texture)SDL_DestroyTexture(victim->texture);
   victim->texture=texture;victim->font=font;victim->color=color;victim->width=w;victim->height=h;
   snprintf(victim->value,sizeof(victim->value),"%.*s",(int)length,value);
   entry=victim;
  }
  entry->use=++cache->counter;
 }else{
  return;
 }
 int width=entry->width,height=entry->height;
 if(max_width>0&&width>max_width){height=(height*max_width)/width;width=max_width;}
 SDL_Rect dst={x,y,width,height};SDL_RenderCopy(renderer,entry->texture,NULL,&dst);
}
