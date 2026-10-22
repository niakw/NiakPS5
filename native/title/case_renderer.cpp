// SPDX-License-Identifier: GPL-3.0-or-later
// NiakPS5 closed retail case: three independent covers, correct hidden surfaces.
// Projected exterior geometry only: no opening, tray, loader, or duplicated shell.
#include "niak/case_renderer.hpp"
#include "demo/catalog.hpp"
#include "ui/fonts.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace {
using hui::gfx::Color;
using hui::gfx::DrawList;
using hui::gfx::Rect;
struct Pt { float x,y; };
struct Vec { float x,y,z; };
constexpr float PI=3.14159265358979323846f;
float smooth(float t) {
    t=std::clamp(t,0.f,1.f);
    return t*t*(3.f-2.f*t);
}
float yaw_at(float seconds) {
    // A closed case rotating along its vertical axis: front -> spine -> back.
    constexpr float front_hold=2.7f,turn=1.35f,back_hold=3.0f;
    constexpr float period=front_hold+turn+back_hold+turn;
    const float t=std::fmod(std::max(0.f,seconds),period);
    if(t<front_hold)return 0.13f;
    if(t<front_hold+turn)
        return 0.13f+(PI-0.26f)*smooth((t-front_hold)/turn);
    if(t<front_hold+turn+back_hold)return PI-0.13f;
    return PI-0.13f+(PI+0.26f)*smooth(
        (t-front_hold-turn-back_hold)/turn);
}
struct Camera {
    Rect rect;
    float cs,sn,distance;
    Pt operator()(Vec p) const {
        const float nx=p.x*cs+p.z*sn;
        const float nz=p.z*cs-p.x*sn;
        const float k=distance/(distance-nz);
        return {rect.cx()+nx*k,rect.cy()+(p.y-0.060f*p.z)*k};
    }
};
void polygon4(DrawList &list,Pt a,Pt b,Pt c,Pt d,Color color) {
    const float xy[]={a.x,a.y,b.x,b.y,c.x,c.y,d.x,d.y};
    list.polygon(xy,4,color);
}
template<class Project>
void printed(DrawList &list,std::uint32_t texture,Project project,
             int columns,int rows) {
    if(!texture)return;
    // DrawList only supports rectangular texture instances. Tessellate BOTH
    // directions to approximate a projected plane, never stretch a full image
    // over unrelated side geometry. UV orientation stays stable on both covers.
    for(int r=0;r<rows;++r)for(int col=0;col<columns;++col) {
        const float u0=float(col)/columns,u1=float(col+1)/columns;
        const float v0=float(r)/rows,v1=float(r+1)/rows;
        const Pt p0=project(u0,v0),p1=project(u1,v0);
        const Pt p2=project(u1,v1),p3=project(u0,v1);
        const float x0=std::min({p0.x,p1.x,p2.x,p3.x});
        const float x1=std::max({p0.x,p1.x,p2.x,p3.x});
        const float y0=std::min({p0.y,p1.y,p2.y,p3.y});
        const float y1=std::max({p0.y,p1.y,p2.y,p3.y});
        if(x1-x0<0.10f||y1-y0<0.10f)continue;
        const bool reverse=(p1.x+p2.x)<(p0.x+p3.x);
        // UVs are 0..1 from real portrait covers and real narrow spine scans.
        // Very small overlap covers subpixel seams without widening the sleeve.
        list.image(texture,{x0-0.12f,y0-0.10f,x1-x0+0.24f,y1-y0+0.20f},
                   {reverse?u1:u0,v0,reverse?u0-u1:u1-u0,v1-v0},
                   Color::rgb(0xffffff));
    }
}
template<class Project>
void molded_panel(DrawList &list,Project project,
                  float left,float right,float top,float bottom,
                  float rounding,Color color) {
    const float centers[4][2] = {
        {right-rounding,top+rounding},
        {right-rounding,bottom-rounding},
        {left+rounding,bottom-rounding},
        {left+rounding,top+rounding}};
    const float starts[4]={-PI*0.5f,0.f,PI*0.5f,PI};
    float xy[2*28];int n=0;
    for(int c=0;c<4;++c)for(int i=0;i<=6;++i) {
        const float angle=starts[c]+PI*i/12.f;
        const auto v=project(centers[c][0]+rounding*std::cos(angle),
                             centers[c][1]+rounding*std::sin(angle));
        xy[2*n]=v.x;xy[2*n+1]=v.y;++n;
    }
    list.polygon(xy,n,color);
}
void outer_face(DrawList &list,const Camera &camera,
                const hui::demo::Item &item,const hui::ui::Fonts &fonts,
                float L,float R,float T,float B,float z,float width,bool back) {
    const float b=width*0.020f;
    auto at=[&](float x,float y){return camera({x,y,z});};
    // A single molded case: thin translucent rim enclosing the printed sleeve.
    molded_panel(list,at,L,R,T,B,width*0.036f,Color::rgb(0x165dba,0.82f));
    const float pLeft=L;                  // Print reaches the LEFT spine fold.
    const float pRight=R-width*0.018f;   // Only the RIGHT closing edge is exposed.
    const float pTop=T+b,pBottom=B-b;
    auto paper=[&](float u,float v) {
        return at(back?pRight+(pLeft-pRight)*u:pLeft+(pRight-pLeft)*u,
                  pTop+(pBottom-pTop)*v);
    };
    const auto texture=back?item.case_back:item.case_front;
    if(texture) {
        printed(list,texture,paper,32,9);
    } else {
        const Pt a=paper(0,0),b0=paper(1,0),c=paper(1,1),d=paper(0,1);
        polygon4(list,a,b0,c,d,Color::rgb(0x1a3558));
        const float start=std::min(a.x,b0.x),span=std::fabs(a.x-b0.x);
        if(span>74.f) {
            hui::ui::text(list,fonts.semibold,item.title_id[0]=='C'?"PS4":"PS5",
                          start+span*0.5f,a.y+29.f,19.f,
                          Color::rgb(0xffffff),hui::gfx::Align::center);
            hui::ui::paragraph(list,fonts.semibold,
                               back?(item.blurb&&item.blurb[0]?item.blurb:item.title):item.title,
                               start+9.f,a.y+71.f,14.f,span-18.f,18.f,
                               Color::rgb(0xf1f7ff),4);
        }
    }
    const auto topL=at(L,T),topR=at(R,T),botL=at(L,B),botR=at(R,B);
    list.line(topL.x,topL.y,topR.x,topR.y,1.5f,Color::rgb(0x8bcfff,0.76f));
    list.line(botL.x,botL.y,botR.x,botR.y,1.5f,Color::rgb(0x217bde,0.82f));
    // The seal stays on the right, but never becomes a wide blue bar.
    list.line(topR.x,topR.y,botR.x,botR.y,1.3f,Color::rgb(0x0d45ab,0.79f));
}
void left_spine(DrawList &list,const Camera &camera,const hui::demo::Item &item,
                const hui::ui::Fonts &fonts,
                float L,float T,float B,float K,float F,float width) {
    const auto at=[&](float z,float y){return camera({L,y,z});};
    polygon4(list,at(K,T),at(F,T),at(F,B),at(K,B),
             Color::rgb(0x1c6cd0,0.88f));
    const float b=width*0.020f;
    const auto paper=[&](float u,float v){
        return at(K+(F-K)*u,T+b+(B-T-2*b)*v);
    };
    if(item.case_spine)printed(list,item.case_spine,paper,10,9);
    else {
        // Standard PS4/PS5 blue plastic spine when LaunchBox has no scan.
        // It is a physical case side, not a fabricated game illustration.
        const auto centre=paper(0.5f,0.06f);
        const auto left=paper(0.f,0.06f),right=paper(1.f,0.06f);
        if(std::fabs(right.x-left.x)>10.f) {
            const char *generation=item.title_id[0]=='C'?"PS4":"PS5";
            for(int i=0;i<3;++i) {
                const auto pos=paper(0.5f,0.08f+0.067f*i);
                const char glyph[2]={generation[i],0};
                hui::ui::text(list,fonts.semibold,glyph,pos.x,pos.y,14.f,
                   Color::rgb(0xf5faff),hui::gfx::Align::center);
            }
        }
    }
    // Small molded seam detail (NOT a thick series of projecting blocks).
    for(float rel:{0.08f,0.86f}) {
        const float y=T+(B-T)*rel;
        const auto a=at(K,y),b0=at(F,y);
        list.line(a.x,a.y,b0.x,b0.y,1.1f,Color::rgb(0xc0ebff,0.55f));
    }
}
void right_seal(DrawList &list,const Camera &camera,
                float R,float T,float B,float K,float F,float width) {
    auto at=[&](float z,float y){return camera({R,y,z});};
    polygon4(list,at(K,T),at(F,T),at(F,B),at(K,B),
             Color::rgb(0x1366c5,0.86f));
    const auto upper=at(K+0.30f*(F-K),T+width*0.060f);
    const auto lower=at(K+0.30f*(F-K),B-width*0.060f);
    list.line(upper.x,upper.y,lower.x,lower.y,1.0f,
              Color::rgb(0x0c397a,0.69f));
}
} // namespace

void niak_draw_rotating_case(hui::gfx::DrawList &list,const hui::demo::Item &item,
                             const hui::gfx::Rect &bounds,float seconds,
                             const hui::ui::Fonts &fonts) {
    // Homebrew games can have genuine privately supplied front/back scans.
    // If none exists, use the installed app icon rather than invent box art.
    if(!item.title_id[0] || !item.case_front) {
        list.image(item.cover,bounds,
                   item.cover_is_image?hui::gfx::kFullUv:hui::gfx::kCanvasUv,
                   Color::rgb(0xffffff),26);
        return;
    }
    const float yaw=yaw_at(seconds);
    const float width=std::min(bounds.w*0.78f,bounds.h*0.76f);
    const float height=std::min(bounds.h*0.88f,width/0.76f);
    const float thickness=width*(item.title_id[0]=='C'?0.080f:0.084f);
    const float L=-width*0.5f,R=width*0.5f,T=-height*0.5f,B=height*0.5f;
    const float F=thickness*0.5f,K=-thickness*0.5f;
    const Camera camera{bounds,std::cos(yaw),std::sin(yaw),width*4.8f};

    // Alpha blending is painter-ordered: never draw occluded side pieces on top.
    // In the coordinate model depth=z*cos(yaw)-x*sin(yaw). Positive sin means
    // LEFT spine is visible; negative sin means the RIGHT closing seal is visible.
    const bool back=std::cos(yaw)<0.f;
    const bool show_spine=std::sin(yaw)>0.055f;
    const bool show_seal=std::sin(yaw)<-0.055f;
    const bool show_face=std::fabs(std::cos(yaw))>0.075f;
    list.shadow({bounds.cx()-width*0.48f,bounds.cy()-height*0.47f,
                 width*0.96f,height*0.94f},
                width*0.035f,16.f,Color::rgb(0x000917,0.36f));

    // Top and bottom are a THIN cap of the same closed body, not second covers.
    polygon4(list,camera({L,T,K}),camera({R,T,K}),
             camera({R,T,F}),camera({L,T,F}),
             Color::rgb(0x3296ea,0.69f));
    polygon4(list,camera({L,B,K}),camera({R,B,K}),
             camera({R,B,F}),camera({L,B,F}),
             Color::rgb(0x125abb,0.70f));

    // Back view: the near side edges overlay the far edge of the printed back.
    // Front view: the near-facing print covers the far side edges.
    if(back&&show_face)
        outer_face(list,camera,item,fonts,L,R,T,B,K,width,true);
    if(show_spine)
        left_spine(list,camera,item,fonts,L,T,B,K,F,width);
    if(show_seal)
        right_seal(list,camera,R,T,B,K,F,width);
    if(!back&&show_face)
        outer_face(list,camera,item,fonts,L,R,T,B,F,width,false);
}
