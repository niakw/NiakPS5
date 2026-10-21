/* SPDX-License-Identifier: GPL-3.0-or-later */
/* NiakPS5 — native full-screen HOME UI. No ShellUI patches, no system writes. */
#include "catalog.h"
#include "ui_renderer.h"
#include "ui_text_cache.h"
#include "ui_motion.h"
#include "build/embedded_assets.h"
#include <math.h>
#include <SDL.h>
#include <SDL_image.h>
#include <SDL_ttf.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define W 1920
#define H 1080
#define COVER_MAX 9
#define COVER_CACHE_MAX 24
#define DATABASE_PATH "/system_data/priv/mms/app.db"
#define NIAK_LOG_PATH "/data/niakps5.log"
#ifdef __PS5__
extern int sceSystemServiceLaunchApp(const char *title_id,const char **argv,void *ctx);
extern int sceSystemServiceHideSplashScreen(void);
#endif
#ifdef __PS5__
typedef struct {char reserved[45];char message[3075];} NiakStartNotice;
extern int sceKernelSendNotificationRequest(int,void*,size_t,int);
static void niak_notify(const char *message){
 NiakStartNotice request={0};
 snprintf(request.message,sizeof(request.message),"%s",message);
 sceKernelSendNotificationRequest(0,&request,sizeof(request),0);
}
static void niak_log(const char *message){
 FILE *f=fopen(NIAK_LOG_PATH,"a");
 if(f){fprintf(f,"%s\n",message);fclose(f);}
 fprintf(stderr,"%s\n",message);
}
#else
static void niak_notify(const char *message){fprintf(stderr,"NOTICE: %s\n",message);}
static void niak_log(const char *message){fprintf(stderr,"%s\n",message);}
#endif
typedef struct {
 SDL_Window *window;
 SDL_Renderer *renderer;
 SDL_GameController *pad;
 TTF_Font *body,*small,*title,*heading;
 SDL_Texture *covers[COVER_CACHE_MAX];
 int cover_index[COVER_CACHE_MAX];
 unsigned cover_used[COVER_CACHE_MAX];
 unsigned cover_clock;
 NiakTextCache text_cache;
 NiakNavRepeat nav;
 float focus_x;
 Uint64 last_frame_count;
 Uint32 backdrop_due;
 int backdrop_pending;
 char renderer_desc[64];
 SDL_Texture *backdrop;
 SDL_Texture *shade_mask;
 NiakGame games[NIAKPS5_MAX_GAMES];
 int game_count,selected,palette,settings,dirty,running;
 time_t clock_second;
 char message[180];
} App;
typedef struct {SDL_Color accent,accent2,background,text,soft,glass;} Theme;
static const Theme THEMES[]={
 {{145,245,223,255},{181,164,255,255},{8,23,25,255},{243,242,237,255},{175,195,197,255},{19,33,41,255}},
 {{199,175,255,255},{145,245,223,255},{22,16,34,255},{243,242,237,255},{186,175,208,255},{36,28,54,255}},
 {{143,207,255,255},{181,164,255,255},{10,20,36,255},{243,242,237,255},{180,193,218,255},{22,37,61,255}},
 {{227,231,238,255},{145,245,223,255},{16,18,22,255},{243,242,237,255},{171,177,188,255},{35,40,49,255}}
};
static void fill(SDL_Renderer *r,int x,int y,int w,int h,SDL_Color c) {
 SDL_Rect rect={x,y,w,h};SDL_SetRenderDrawBlendMode(r,SDL_BLENDMODE_BLEND);
 SDL_SetRenderDrawColor(r,c.r,c.g,c.b,c.a);SDL_RenderFillRect(r,&rect);
}
static void line(SDL_Renderer *r,int x1,int y1,int x2,int y2,SDL_Color c) {
 SDL_SetRenderDrawColor(r,c.r,c.g,c.b,c.a);SDL_RenderDrawLine(r,x1,y1,x2,y2);
}
static void outline(SDL_Renderer *r,int x,int y,int w,int h,SDL_Color c) {
 SDL_Rect rect={x,y,w,h};SDL_SetRenderDrawColor(r,c.r,c.g,c.b,c.a);SDL_RenderDrawRect(r,&rect);
}
static void text(App *app,TTF_Font *font,const char *str,int x,int y,SDL_Color col,int maxw){
 niak_text_draw(&app->text_cache,app->renderer,font,str,x,y,col,maxw);
}
static void set_status(App *app,const char *value){
 snprintf(app->message,sizeof(app->message),"%s",value);app->dirty=1;
}
static SDL_Texture *image(App *app,const char *path) {
 if(!path||!*path)return NULL;
 return IMG_LoadTexture(app->renderer,path);
}
static void clear_cover_cache(App *app){
 for(int i=0;i<COVER_CACHE_MAX;i++){if(app->covers[i])SDL_DestroyTexture(app->covers[i]);app->covers[i]=NULL;app->cover_index[i]=-1;app->cover_used[i]=0;}app->cover_clock=0;
}
/* Bounded LRU keyed by game index; keyboard/controller focus no longer reloads all covers. */
static SDL_Texture *cover_for(App *app,int index){
 int victim=0;
 for(int i=0;i<COVER_CACHE_MAX;i++){
   if(app->cover_index[i]==index){app->cover_used[i]=++app->cover_clock;return app->covers[i];}
   if(app->cover_index[i]<0){victim=i;break;}
   if(app->cover_used[i]<app->cover_used[victim])victim=i;
 }
 if(app->covers[victim])SDL_DestroyTexture(app->covers[victim]);
 app->covers[victim]=image(app,app->games[index].icon);
 app->cover_index[victim]=index;
 app->cover_used[victim]=++app->cover_clock;
 return app->covers[victim];
}
static void reload_background(App *app){
 app->backdrop_pending=0;
 if(app->backdrop){SDL_DestroyTexture(app->backdrop);app->backdrop=NULL;}
 if(app->game_count>0)app->backdrop=image(app,app->games[app->selected].background);
 app->dirty=1;
}
static void scan_games(App *app){
 clear_cover_cache(app);
 /* Desktop verification can override fixture paths; PS5 paths are fixed. */
 const char *db=DATABASE_PATH,*root="/";
#ifndef __PS5__
 const char *test_db=getenv("NIAKPS5_DB"),*test_root=getenv("NIAKPS5_ROOT");
 if(test_db && *test_db)db=test_db;
 if(test_root && *test_root)root=test_root;
#endif
 int result=niak_scan_games(db,root,app->games,NIAKPS5_MAX_GAMES);
 app->game_count=result<0?0:result;app->selected=0;
 if(result<0)set_status(app,"Lecture de la base PS5 impossible. Rond : accueil Sony.");
 else if(result==0)set_status(app,"Aucun jeu installe detecte. Carre : actualiser.");
 else set_status(app,"Jeux installes sur cette console (lecture seule).");
 reload_background(app);
}
static TTF_Font *niak_embedded_font(const unsigned char *data,size_t count,int size){
 SDL_RWops *rw=SDL_RWFromConstMem(data,(int)count);
 if(!rw)return NULL;
 return TTF_OpenFontRW(rw,1,size);
}
static int load_fonts(App *app){
 /* True single-ELF build: SDL_RWops reads fonts from immutable embedded arrays. */
 app->body=niak_embedded_font(niak_manrope_font,sizeof(niak_manrope_font),23);
 app->small=niak_embedded_font(niak_manrope_font,sizeof(niak_manrope_font),17);
 app->heading=niak_embedded_font(niak_manrope_font,sizeof(niak_manrope_font),33);
 app->title=niak_embedded_font(niak_serif_font,sizeof(niak_serif_font),92);
 return (app->body&&app->small&&app->heading&&app->title)?0:-1;
}
/* Create a low-resolution smooth mask once; scale linearly rather than drawing 200 alpha strips per frame. */
static SDL_Texture *make_shade(SDL_Renderer *renderer) {
 const int w=512,h=288;
 SDL_Surface *surface=SDL_CreateRGBSurfaceWithFormat(0,w,h,32,SDL_PIXELFORMAT_RGBA8888);
 if(!surface)return NULL;
 SDL_LockSurface(surface);
 for(int y=0;y<h;y++)for(int x=0;x<w;x++){
   float fx=(float)x/(float)(w-1),fy=(float)y/(float)(h-1);
   float a=fx<0.22f?1.0f:(fx>0.86f?0.07f:1.0f-0.93f*((fx-0.22f)/0.64f));
   float b=fy<0.63f?0.0f:(fy>0.96f?0.98f:0.98f*((fy-0.63f)/0.33f));
   float total=1.0f-(1.0f-a)*(1.0f-b);
   Uint8 alpha=(Uint8)(total*255.0f);
   ((Uint32*)((Uint8*)surface->pixels+y*surface->pitch))[x]=SDL_MapRGBA(surface->format,6,14,23,alpha);
 }
 SDL_UnlockSurface(surface);
 SDL_Texture *tex=SDL_CreateTextureFromSurface(renderer,surface);SDL_FreeSurface(surface);
 if(tex)SDL_SetTextureBlendMode(tex,SDL_BLENDMODE_BLEND);
 return tex;
}
static void cover_fit(SDL_Renderer *renderer,SDL_Texture *tex,SDL_Rect dest) {
 int iw=0,ih=0;
 if(!tex || SDL_QueryTexture(tex,NULL,NULL,&iw,&ih)!=0 || iw<1 || ih<1)return;
 SDL_Rect src={0,0,iw,ih};
 if((long long)iw*dest.h > (long long)ih*dest.w) {
   src.w=(int)((long long)ih*dest.w/dest.h);src.x=(iw-src.w)/2;
 } else {
   src.h=(int)((long long)iw*dest.h/dest.w);src.y=(ih-src.h)/2;
 }
 SDL_RenderCopy(renderer,tex,&src,&dest);
}
static void background(App *app,const Theme *theme) {
 SDL_Renderer *r=app->renderer;
 SDL_SetRenderDrawColor(r,theme->background.r,theme->background.g,theme->background.b,255);
 SDL_RenderClear(r);
 if(app->backdrop){
   SDL_SetTextureAlphaMod(app->backdrop,150);
   SDL_Rect rect={550,0,1370,850};
   cover_fit(r,app->backdrop,rect);
 }
 if(app->shade_mask){
   SDL_Rect full={0,0,W,H};
   SDL_RenderCopy(r,app->shade_mask,NULL,&full);
 }else{
   fill(r,0,0,650,H,(SDL_Color){6,14,23,208});
   fill(r,0,840,W,240,(SDL_Color){6,14,23,205});
 }
}
static void background_label(App *app,const Theme *theme){
 SDL_Renderer *r=app->renderer;
 SDL_Color muted=theme->soft;
 fill(r,70,75,30,34,theme->accent);
 text(app,app->heading,"N",74,72,theme->background,0);
 text(app,app->heading,"NIAK",114,70,theme->text,0);
 text(app,app->heading,"PS5",210,70,theme->accent,0);
 text(app,app->body,"Jeux",395,76,theme->text,0);
 text(app,app->body,"Multimedia",510,76,muted,0);
 line(r,75,139,1835,139,(SDL_Color){140,175,180,44});
 char timebuf[64];time_t now=time(NULL);struct tm *tm=localtime(&now);
 if(tm){strftime(timebuf,sizeof(timebuf),"%H:%M",tm);text(app,app->body,timebuf,1700,76,theme->text,0);}
 text(app,app->small,"NIAK / PLAY",1600,175,theme->accent,0);
}
static void draw_cards(App *app,const Theme *theme) {
 SDL_Renderer *r=app->renderer;
 text(app,app->heading,"Ma bibliotheque",75,708,theme->text,0);
 int label_width=0,label_height=0;
 if(app->heading)TTF_SizeUTF8(app->heading,"Ma bibliotheque",&label_width,&label_height);
 int dot=75+label_width+18;
 fill(r,dot,729,7,7,theme->accent);
 char count[80];snprintf(count,sizeof(count),"%d jeux installes",app->game_count);
 text(app,app->small,count,dot+34,721,theme->soft,0);
 if(app->game_count<=0)return;
 int start=app->selected>=COVER_MAX?app->selected-(COVER_MAX-1):0;
 for(int k=0;k<COVER_MAX&&start+k<app->game_count;k++){
   int index=start+k,x=75+k*194,y=773;
   SDL_Color card={22,38,44,255};
   fill(r,x,y,175,225,card);
   SDL_Texture *cover=cover_for(app,index);
   if(cover){
     SDL_Rect dst={x,y,175,160};SDL_RenderCopy(r,cover,NULL,&dst);
   }else{
     text(app,app->heading,"PS5",x+50,y+53,theme->accent,0);
   }
   fill(r,x,y+158,175,67,(SDL_Color){10,21,29,240});
   text(app,app->small,app->games[index].title,x+11,y+167,theme->text,154);
   text(app,app->small,app->games[index].id,x+11,y+192,theme->soft,0);
 }
 int fx=(int)(app->focus_x+0.5f);
 outline(r,fx-3,770,181,231,theme->accent);
 outline(r,fx-6,767,187,237,(SDL_Color){theme->accent.r,theme->accent.g,theme->accent.b,130});
}
static void draw(App *app) {
 const Theme *theme=&THEMES[app->palette];SDL_Renderer *r=app->renderer;
 background(app,theme);background_label(app,theme);
 fill(r,75,276,7,7,theme->accent);
 text(app,app->small,"VOTRE CONSOLE  /  VOTRE ESPACE",98,268,theme->accent,0);
 const NiakGame *game=app->game_count?&app->games[app->selected]:NULL;
 text(app,app->title,game?game->title:"Bienvenue sur NiakPS5",77,327,theme->text,900);
 text(app,app->body,game?"Jeu installe sur votre PS5":"Votre bibliotheque sera disponible des que votre console la fournira.",82,461,theme->soft,850);
 if(game) {
   fill(r,80,530,224,62,theme->accent);
   text(app,app->body,"X  Lancer le jeu",105,546,theme->background,0);
   fill(r,323,530,240,62,theme->glass);
   text(app,app->body,"[]  Actualiser",343,546,theme->text,0);
 }else{
   fill(r,80,530,257,62,theme->glass);
   text(app,app->body,"[]  Actualiser",104,546,theme->text,0);
 }
 draw_cards(app,theme);
 fill(r,0,1016,W,64,(SDL_Color){6,13,20,231});
 text(app,app->small,app->message,68,1038,theme->soft,920);
 text(app,app->small,app->renderer_desc,750,1038,theme->soft,0);
 text(app,app->small,"X  Jouer    O  Sony    []  Actualiser    /\\  Options",1210,1038,theme->text,0);
 if(app->settings){
   fill(r,0,0,W,H,(SDL_Color){3,8,16,183});
   fill(r,1220,0,700,H,(SDL_Color){16,25,36,255});
   fill(r,1220,0,2,H,theme->accent);
   text(app,app->title,"NiakPS5",1280,110,theme->text,0);
   text(app,app->heading,"Preferences",1280,245,theme->accent,0);
   text(app,app->body,"Gauche / Droite : changer de palette",1280,338,theme->text,0);
   text(app,app->body,"Carre : actualiser les jeux",1280,391,theme->text,0);
   text(app,app->body,"Rond : fermer le panneau",1280,444,theme->text,0);
   text(app,app->small,"Accueil Sony conserve, aucune modification systeme.",1280,585,theme->soft,570);
 }
 #ifndef __PS5__
 static int captured=0;
 const char *screenshot=getenv("NIAKPS5_SCREENSHOT");
 if(!captured && screenshot && *screenshot){
  captured=1;
  SDL_Surface *pixels=SDL_CreateRGBSurfaceWithFormat(0,W,H,32,SDL_PIXELFORMAT_ARGB8888);
  if(pixels){
   if(SDL_RenderReadPixels(r,NULL,SDL_PIXELFORMAT_ARGB8888,pixels->pixels,pixels->pitch)==0)
    SDL_SaveBMP(pixels,screenshot);
   SDL_FreeSurface(pixels);
  }
 }
#endif
 SDL_RenderPresent(r);app->dirty=0;
}
static void select_game(App *app,int next) {
 if(next<0 || next>=app->game_count || next==app->selected)return;
 app->selected=next;app->backdrop_pending=1;app->backdrop_due=SDL_GetTicks()+135;app->dirty=1;
}
static void launch_selected(App *app) {
 if(app->game_count==0)return;
#ifdef __PS5__
 const char *id=app->games[app->selected].id;
 int result=sceSystemServiceLaunchApp(id,NULL,NULL);
 if(result==0){app->running=0;return;}
 char message[160];snprintf(message,sizeof(message),"Echec lancement %s (0x%08x). Accueil Sony : Rond.",id,(unsigned)result);
 set_status(app,message);
#else
 set_status(app,"Apercu PC : le lancement des jeux PS5 est desactive.");
#endif
}
static void input(App *app,int action){
 /* 1 left, 2 right, 3 confirm, 4 back, 5 rescan, 6 settings */
 if(action==4){if(app->settings)app->settings=0;else app->running=0;}
 else if(action==6){app->settings=!app->settings;}
 else if(action==7){app->palette=(app->palette+1)%4;}
 else if(action==5){scan_games(app);}
 else if(app->settings && (action==1||action==2))app->palette=(app->palette+(action==1?3:1))%4;
 else if(!app->settings && action==1)select_game(app,app->selected-1);
 else if(!app->settings && action==2)select_game(app,app->selected+1);
 else if(!app->settings && action==3)launch_selected(app);
 app->dirty=1;
}
int main(int argc,char **argv){
 (void)argc;(void)argv;
#ifdef __PS5__
 niak_log("NiakPS5 single ELF startup (no hbldr; no system_ex writes)");
 niak_notify("NiakPS5: initialisation de l'interface...");
#endif
 App *app=(App*)calloc(1,sizeof(App));if(!app)return 1;
 for(int i=0;i<COVER_CACHE_MAX;i++)app->cover_index[i]=-1;
 app->focus_x=75.0f;
 app->running=1;app->dirty=1;
 SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY,"linear");
 if(SDL_Init(SDL_INIT_VIDEO|SDL_INIT_GAMECONTROLLER)!=0){char error[340];snprintf(error,sizeof(error),"NiakPS5: SDL_Init: %.260s",SDL_GetError());niak_log(error);niak_notify(error);free(app);return 1;}
 IMG_Init(IMG_INIT_PNG|IMG_INIT_JPG);
 if(TTF_Init()!=0){char error[340];snprintf(error,sizeof(error),"NiakPS5: TTF_Init: %.260s",TTF_GetError());niak_log(error);niak_notify(error);SDL_Quit();free(app);return 1;}
#ifdef __PS5__
 const Uint32 flags=SDL_WINDOW_FULLSCREEN;
#else
 const Uint32 flags=SDL_WINDOW_SHOWN;
#endif
 app->window=SDL_CreateWindow("NiakPS5",SDL_WINDOWPOS_CENTERED,SDL_WINDOWPOS_CENTERED,W,H,flags);
 if(!app->window){niak_log(SDL_GetError());niak_notify("NiakPS5: SDL video/window indisponible dans ce contexte ELF.");goto fail;}
 app->renderer=niak_renderer_create(app->window,app->renderer_desc,sizeof(app->renderer_desc));
 if(!app->renderer){niak_log(SDL_GetError());niak_notify("NiakPS5: rendu SDL indisponible dans Payload Manager.");goto fail;}
 SDL_RenderSetLogicalSize(app->renderer,W,H);
 app->shade_mask=make_shade(app->renderer);
 SDL_SetRenderDrawBlendMode(app->renderer,SDL_BLENDMODE_BLEND);
 if(load_fonts(app)!=0){niak_log(TTF_GetError());niak_notify("NiakPS5: chargement des polices integrees impossible.");goto fail;}
#ifdef __PS5__
 sceSystemServiceHideSplashScreen();
#endif
 for(int i=0;i<SDL_NumJoysticks();i++)if(SDL_IsGameController(i)){app->pad=SDL_GameControllerOpen(i);break;}
 scan_games(app);
 niak_log("NiakPS5: main UI event loop initialized");
 while(app->running) {
   SDL_Event event;
   if(SDL_WaitEventTimeout(&event,16)){
     do {
       if(event.type==SDL_QUIT)app->running=0;
       if(event.type==SDL_KEYDOWN&&!event.key.repeat){
         switch(event.key.keysym.sym){
           case SDLK_LEFT: input(app,1);break;case SDLK_RIGHT:input(app,2);break;
           case SDLK_RETURN:input(app,3);break;case SDLK_ESCAPE:input(app,4);break;
           case SDLK_r:input(app,5);break;case SDLK_t:input(app,6);break;
         }
       }
       if(event.type==SDL_CONTROLLERBUTTONDOWN){
         switch(event.cbutton.button){
           /* D-pad and analog stick are sampled by niak_nav_tick below, with repeat. */
           case SDL_CONTROLLER_BUTTON_A:input(app,3);break;
           case SDL_CONTROLLER_BUTTON_B:input(app,4);break;
           case SDL_CONTROLLER_BUTTON_X:input(app,5);break;
           case SDL_CONTROLLER_BUTTON_Y:input(app,6);break;
           case SDL_CONTROLLER_BUTTON_LEFTSHOULDER:select_game(app,app->selected-COVER_MAX);break;
           case SDL_CONTROLLER_BUTTON_RIGHTSHOULDER:select_game(app,app->selected+COVER_MAX);break;
         }
       }
     }while(SDL_PollEvent(&event));
   }
   if(app->pad && SDL_GameControllerGetAttached(app->pad)){
     int dir=0;
     Sint16 axis=SDL_GameControllerGetAxis(app->pad,SDL_CONTROLLER_AXIS_LEFTX);
     if(SDL_GameControllerGetButton(app->pad,SDL_CONTROLLER_BUTTON_DPAD_LEFT))dir=-1;
     else if(SDL_GameControllerGetButton(app->pad,SDL_CONTROLLER_BUTTON_DPAD_RIGHT))dir=1;
     else if(axis < -19000)dir=-1;
     else if(axis > 19000)dir=1;
     int step=niak_nav_tick(&app->nav,dir,SDL_GetTicks());
     if(step<0)input(app,1);else if(step>0)input(app,2);
   }else niak_nav_tick(&app->nav,0,SDL_GetTicks());
   Uint32 tick=SDL_GetTicks();
   if(app->backdrop_pending && (Sint32)(tick-app->backdrop_due)>=0)reload_background(app);
   Uint64 perf=SDL_GetPerformanceCounter();
   Uint64 freq=SDL_GetPerformanceFrequency();
   float dt=app->last_frame_count && freq ? (float)((double)(perf-app->last_frame_count)/(double)freq):1.0f/60.0f;
   app->last_frame_count=perf;
   int start=app->selected>=COVER_MAX?app->selected-(COVER_MAX-1):0;
   float target=(float)(75+(app->selected-start)*194);
   float before=app->focus_x;
   app->focus_x=niak_ease(before,target,dt,14.0f);
   if(fabsf(target-app->focus_x)<0.25f)app->focus_x=target;
   if(app->focus_x!=before)app->dirty=1;
   time_t now=time(NULL);if(now!=app->clock_second){app->clock_second=now;app->dirty=1;}
   if(app->dirty)draw(app);
 }
fail:
 if(app->pad)SDL_GameControllerClose(app->pad);
 clear_cover_cache(app);
 if(app->backdrop)SDL_DestroyTexture(app->backdrop);
 if(app->shade_mask)SDL_DestroyTexture(app->shade_mask);
 niak_text_clear(&app->text_cache);
 if(app->body)TTF_CloseFont(app->body);if(app->small)TTF_CloseFont(app->small);
 if(app->title)TTF_CloseFont(app->title);if(app->heading)TTF_CloseFont(app->heading);
 if(app->renderer)SDL_DestroyRenderer(app->renderer);if(app->window)SDL_DestroyWindow(app->window);
 TTF_Quit();IMG_Quit();SDL_Quit();free(app);
 return 0;
}
