/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "ui_renderer.h"
#include <stdio.h>
SDL_Renderer *niak_renderer_create(SDL_Window *window,char *description,size_t capacity){
 const Uint32 flags[]={
  SDL_RENDERER_ACCELERATED|SDL_RENDERER_PRESENTVSYNC|SDL_RENDERER_TARGETTEXTURE,
  SDL_RENDERER_ACCELERATED|SDL_RENDERER_PRESENTVSYNC,
  SDL_RENDERER_ACCELERATED,
  SDL_RENDERER_SOFTWARE|SDL_RENDERER_TARGETTEXTURE,
  SDL_RENDERER_SOFTWARE
 };
 SDL_Renderer *renderer=NULL;
 SDL_RendererInfo info;
 for(unsigned i=0;i<sizeof(flags)/sizeof(flags[0]);i++){
  renderer=SDL_CreateRenderer(window,-1,flags[i]);
  if(renderer)break;
 }
 if(description && capacity){
  if(renderer && SDL_GetRendererInfo(renderer,&info)==0)
   snprintf(description,capacity,"%s [%s]",info.name?info.name:"unknown",(info.flags&SDL_RENDERER_ACCELERATED)?"GPU":"software");
  else snprintf(description,capacity,"renderer unavailable");
 }
 return renderer;
}
