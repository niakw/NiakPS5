/* SPDX-License-Identifier: GPL-3.0-or-later */
/* NiakPS5 — native full-screen HOME UI. No ShellUI patches, no system writes. */
#include "catalog.h"
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
#define DATABASE_PATH "/system_data/priv/mms/app.db"
#define ASSETS_PATH "/data/niakps5/assets"
#ifdef __PS5__
extern int sceSystemServiceLaunchApp(const char *title_id,const char **argv,void *ctx);
extern int sceSystemServiceHideSplashScreen(void);
#endif
typedef struct {
 SDL_Window *window;
 SDL_Renderer *renderer;
 SDL_GameController *pad;
 TTF_Font *body,*small,*title,*heading;
 SDL_Texture *covers[COVER_MAX];
 int cover_index[COVER_MAX];
 SDL_Texture *backdrop;
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
 if(!font||!str||!*str)return;
 SDL_Surface *surface=TTF_RenderUTF8_Blended(font,str,col);
 if(!surface)return;
 SDL_Texture *tex=SDL_CreateTextureFromSurface(app->renderer,surface);
 int w=surface->w,h=surface->h;SDL_FreeSurface(surface);
 if(!tex)return;
 if(maxw>0 && w>maxw){h=h*maxw/w;w=maxw;}
 SDL_Rect rect={x,y,w,h};SDL_RenderCopy(app->renderer,tex,NULL,&rect);
 SDL_DestroyTexture(tex);
}
static void set_status(App *app,const char *value){
 snprintf(app->message,sizeof(app->message),"%s",value);app->dirty=1;
}
static SDL_Texture *image(App *app,const char *path) {
 if(!path||!*path)return NULL;
 return IMG_LoadTexture(app->renderer,path);
}
static void clear_cover_cache(App *app){
 for(int i=0;i<COVER_MAX;i++){if(app->covers[i])SDL_DestroyTexture(app->covers[i]);app->covers[i]=NULL;app->cover_index[i]=-1;}
}
static void reload_background(App *app){
 if(app->backdrop){SDL_DestroyTexture(app->backdrop);app->backdrop=NULL;}
 if(app->game_count>0)app->backdrop=image(app,app->games[app->selected].background);
 app->dirty=1;
}
static void scan_games(App *app){
 clear_cover_cache(app);
 int result=niak_scan_games(DATABASE_PATH,"/",app->games,NIAKPS5_MAX_GAMES);
 app->game_count=result<0?0:result;app->selected=0;
 if(result<0)set_status(app,"Lecture de la base PS5 impossible. Rond : accueil Sony.");
 else if(result==0)set_status(app,"Aucun jeu installe detecte. Carre : actualiser.");
 else set_status(app,"Jeux installes sur cette console (lecture seule).");
 reload_background(app);
}
static int load_fonts(App *app){
 char path[512];const char *base=getenv("NIAKPS5_ASSETS");
 if(!base||!*base)base=ASSETS_PATH;
 snprintf(path,sizeof(path),"%s/manrope.ttf",base);
 app->body=TTF_OpenFont(path,23);app->small=TTF_OpenFont(path,17);app->heading=TTF_OpenFont(path,33);
 snprintf(path,sizeof(path),"%s/instrument-serif.ttf",base);
 app->title=TTF_OpenFont(path,92);
 return (app->body&&app->small&&app->heading&&app->title)?0:-1;
}
static void background(App *app,const Theme *theme) {
 SDL_Renderer *r=app->renderer;
 SDL_SetRenderDrawColor(r,theme->background.r,theme->background.g,theme->background.b,255);
 SDL_RenderClear(r);
 if(app->backdrop){
   SDL_SetTextureAlphaMod(app->backdrop,150);
   SDL_Rect rect={550,0,1370,850};
   SDL_RenderCopy(r,app->backdrop,NULL,&rect);
 }
 /* Soft layered shades approximate the NiakTV cinematic darkening without shaders. */
 for(int x=0;x<1400;x+=18){
   int a=(int)(245.0*(1.0-(float)x/1400.0));
   SDL_Color shade={theme->background.r,theme->background.g,theme->background.b,(Uint8)a};
   fill(r,x,0,19,H,shade);
 }
 for(int y=740;y<H;y+=10){
   SDL_Color shade={6,11,19,(Uint8)(25+200*(y-740)/(H-740))};
   fill(r,0,y,W,11,shade);
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
 char timebuf[64];time_t now=time(NULL);struct tm *tm=localtime(&now);
 if(tm){strftime(timebuf,sizeof(timebuf),"%H:%M",tm);text(app,app->body,timebuf,1700,76,theme->text,0);}
 text(app,app->small,"NI​AK / PLAY",1600,175,theme->accent,0);
}
static void draw_cards(App *app,const Theme *theme) {
 SDL_Renderer *r=app->renderer;
 text(app,app->heading,"Ma bibliotheque",75,708,theme->text,0);
 fill(r,307,729,7,7,theme->accent);
 char count[80];snprintf(count,sizeof(count),"%d jeux installes",app->game_count);
 text(app,app->small,count,352,721,theme->soft,0);
 if(app->game_count<=0)return;
 int start=app->selected>=COVER_MAX?app->selected-(COVER_MAX-1):0;
 for(int k=0;k<COVER_MAX&&start+k<app->game_count;k++){
   int index=start+k,x=75+k*194,y=773;
   SDL_Color card={22,38,44,255};
   fill(r,x,y,175,225,card);
   if(app->cover_index[k]!=index){
     if(app->covers[k])SDL_DestroyTexture(app->covers[k]);
     app->covers[k]=image(app,app->games[index].icon);
     app->cover_index[k]=index;
   }
   if(app->covers[k]){
     SDL_Rect dst={x,y,175,160};SDL_RenderCopy(r,app->covers[k],NULL,&dst);
   }else{
     text(app,app->heading,"PS5",x+50,y+53,theme->accent,0);
   }
   fill(r,x,y+158,175,67,(SDL_Color){10,21,29,240});
   text(app,app->small,app->games[index].title,x+11,y+167,theme->text,154);
   text(app,app->small,app->games[index].id,x+11,y+192,theme->soft,0);
   if(index==app->selected){
     outline(r,x-3,y-3,181,231,theme->accent);
     outline(r,x-6,y-6,187,237,(SDL_Color){theme->accent.r,theme->accent.g,theme->accent.b,130});
   }
 }
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
 text(app,app->small,"X  Selectionner     O  Accueil Sony     []  Actualiser     /\\  Palette",1120,1038,theme->text,0);
 if(app->settings){
   fill(r,0,0,W,H,(SDL_Color){3,8,16,183});
   fill(r,1220,0,700,H,(SDL_Color){16,25,36,255});
   fill(r,1220,0,2,H,theme->accent);
   text(app,app->title,"NiakPS5",1280,110,theme->text,0);
   text(app,app->heading,"Preferences",1280,245,theme->accent,0);
   text(app,app->body,"Triangle : changer la palette",1280,338,theme->text,0);
   text(app,app->body,"Carre : actualiser les jeux",1280,391,theme->text,0);
   text(app,app->body,"Rond : fermer le panneau",1280,444,theme->text,0);
   text(app,app->small,"Accueil Sony conserve, aucune modification systeme.",1280,585,theme->soft,570);
 }
 SDL_RenderPresent(r);app->dirty=0;
}
static void select_game(App *app,int next) {
 if(next<0 || next>=app->game_count || next==app->selected)return;
 app->selected=next;clear_cover_cache(app);reload_background(app);
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
 else if(action==6){app->palette=(app->palette+1)%4;app->settings=!app->settings;}
 else if(action==5){scan_games(app);}
 else if(!app->settings && action==1)select_game(app,app->selected-1);
 else if(!app->settings && action==2)select_game(app,app->selected+1);
 else if(!app->settings && action==3)launch_selected(app);
 app->dirty=1;
}
int main(int argc,char **argv){
 (void)argc;(void)argv;
 App *app=(App*)calloc(1,sizeof(App));if(!app)return 1;
 for(int i=0;i<COVER_MAX;i++)app->cover_index[i]=-1;
 app->running=1;app->dirty=1;
 if(SDL_Init(SDL_INIT_VIDEO|SDL_INIT_GAMECONTROLLER)!=0){fprintf(stderr,"SDL_Init: %s\n",SDL_GetError());free(app);return 1;}
 IMG_Init(IMG_INIT_PNG|IMG_INIT_JPG);
 if(TTF_Init()!=0){fprintf(stderr,"TTF_Init: %s\n",TTF_GetError());SDL_Quit();free(app);return 1;}
#ifdef __PS5__
 const Uint32 flags=SDL_WINDOW_FULLSCREEN;
#else
 const Uint32 flags=SDL_WINDOW_SHOWN;
#endif
 app->window=SDL_CreateWindow("NiakPS5",SDL_WINDOWPOS_CENTERED,SDL_WINDOWPOS_CENTERED,W,H,flags);
 if(!app->window)goto fail;
 app->renderer=SDL_CreateRenderer(app->window,-1,SDL_RENDERER_SOFTWARE);
 if(!app->renderer)goto fail;
 SDL_RenderSetLogicalSize(app->renderer,W,H);
 SDL_SetRenderDrawBlendMode(app->renderer,SDL_BLENDMODE_BLEND);
 if(load_fonts(app)!=0){fprintf(stderr,"Font asset missing under %s\n",ASSETS_PATH);goto fail;}
#ifdef __PS5__
 sceSystemServiceHideSplashScreen();
#endif
 for(int i=0;i<SDL_NumJoysticks();i++)if(SDL_IsGameController(i)){app->pad=SDL_GameControllerOpen(i);break;}
 scan_games(app);
 while(app->running) {
   SDL_Event event;
   if(SDL_WaitEventTimeout(&event,100)){
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
           case SDL_CONTROLLER_BUTTON_DPAD_LEFT:input(app,1);break;
           case SDL_CONTROLLER_BUTTON_DPAD_RIGHT:input(app,2);break;
           case SDL_CONTROLLER_BUTTON_A:input(app,3);break;
           case SDL_CONTROLLER_BUTTON_B:input(app,4);break;
           case SDL_CONTROLLER_BUTTON_X:input(app,5);break;
           case SDL_CONTROLLER_BUTTON_Y:input(app,6);break;
         }
       }
     }while(SDL_PollEvent(&event));
   }
   time_t now=time(NULL);if(now!=app->clock_second){app->clock_second=now;app->dirty=1;}
   if(app->dirty)draw(app);
 }
fail:
 if(app->pad)SDL_GameControllerClose(app->pad);
 clear_cover_cache(app);
 if(app->backdrop)SDL_DestroyTexture(app->backdrop);
 if(app->body)TTF_CloseFont(app->body);if(app->small)TTF_CloseFont(app->small);
 if(app->title)TTF_CloseFont(app->title);if(app->heading)TTF_CloseFont(app->heading);
 if(app->renderer)SDL_DestroyRenderer(app->renderer);if(app->window)SDL_DestroyWindow(app->window);
 TTF_Quit();IMG_Quit();SDL_Quit();free(app);
 return 0;
}
