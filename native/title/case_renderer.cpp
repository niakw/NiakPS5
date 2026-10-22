// SPDX-License-Identifier: GPL-3.0-or-later
// PS4/PS5 retail case: a single perspective-projected shell, not a squeezed icon.
// The GPU DrawList is 2D. Its polygon mesh and clipped UV image strips let us
// project the same physical geometry and regional art at every animation angle.
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
struct Point { float x, y; };
struct Surface { float x, y, z; };

float smooth(float v) {
    v=std::clamp(v,0.0f,1.0f);
    return v*v*(3.0f-2.0f*v);
}
float case_yaw(float seconds) {
    constexpr float pi=3.14159265359f;
    // Front/back pause; physically continue rotating, never jump or reset.
    constexpr float hold_front=3.0f, turn=1.15f, hold_back=3.2f;
    constexpr float cycle=hold_front+turn+hold_back+turn;
    const float phase=std::fmod(std::max(0.0f,seconds),cycle);
    if(phase<hold_front)return 0.19f;
    if(phase<hold_front+turn)
        return 0.19f+(pi-0.38f)*smooth((phase-hold_front)/turn);
    if(phase<hold_front+turn+hold_back)return pi-0.19f;
    return pi-0.19f+(pi+0.38f)*smooth(
        (phase-hold_front-turn-hold_back)/turn);
}
struct Camera {
    Rect box;
    float cosine, sine, distance;
    Point project(Surface p) const {
        const float x=p.x*cosine+p.z*sine;
        const float z=p.z*cosine-p.x*sine;
        const float factor=distance/(distance-z);
        // The small camera elevation exposes the molded top and bottom lips.
        return {box.cx()+x*factor,
                box.cy()+(p.y-0.115f*z)*factor};
    }
};
void quad(DrawList &list,Point a,Point b,Point c,Point d,Color fill) {
    const float xy[]={a.x,a.y,b.x,b.y,c.x,c.y,d.x,d.y};
    list.polygon(xy,4,fill);
}
void textured_face(DrawList &list,const Camera &cam,std::uint32_t texture,
                   float x_left,float x_right,float top,float bottom,float z,
                   Color tint,int slices) {
    // Piecewise perspective UVs: the cover stays on the physical front/back
    // instead of being drawn as an unrelated rectangle in front of the case.
    // Thin columns also preserve perspective-correct edge height changes.
    for(int i=0;i<slices;++i) {
        const float u0=float(i)/slices,u1=float(i+1)/slices;
        const float x0=x_left+(x_right-x_left)*u0;
        const float x1=x_left+(x_right-x_left)*u1;
        const Point a=cam.project({x0,top,z});
        const Point b=cam.project({x1,top,z});
        const Point d=cam.project({(x0+x1)*0.5f,top,z});
        const float left=std::min(a.x,b.x),width=std::fabs(b.x-a.x);
        const Point low=cam.project({(x0+x1)*0.5f,bottom,z});
        const float height=std::fabs(low.y-d.y);
        if(width<0.015f || height<0.05f)continue;
        // Very small strip overlap avoids hairline gaps due to subpixel rounding.
        list.image(texture,{left-0.18f,std::min(d.y,low.y),
                   width+0.36f,height},
                   {u0,0,u1-u0,1},tint);
    }
}
void spine_texture(DrawList &list,const Camera &cam,std::uint32_t image,
                   float x,float top,float bottom,float depth,int slices) {
    // LaunchBox Box-Spine is kept distinct from Box-Front and Box-Back.
    for(int i=0;i<slices;++i) {
        const float u0=float(i)/slices,u1=float(i+1)/slices;
        const float z0=-depth*0.5f+depth*u0,z1=-depth*0.5f+depth*u1;
        const Point a=cam.project({x,top,z0});
        const Point b=cam.project({x,top,z1});
        const Point mid=cam.project({x,top,(z0+z1)*0.5f});
        const Point low=cam.project({x,bottom,(z0+z1)*0.5f});
        const float width=std::fabs(a.x-b.x);
        if(width<0.015f)continue;
        list.image(image,{std::min(a.x,b.x)-0.12f,std::min(mid.y,low.y),
                   width+0.24f,std::fabs(mid.y-low.y)},
                   {u0,0,u1-u0,1},Color::rgb(0xffffff));
    }
}
void framed_face(DrawList &list,const Camera &cam,float w,float h,float z,
                 std::uint32_t image,bool front,bool ps4,
                 const hui::demo::Item &game,const hui::ui::Fonts &fonts) {
    const float left=-w*0.5f,right=w*0.5f;
    const float top=-h*0.5f,bottom=h*0.5f;
    const float lip=w*0.025f;
    const Color shell=Color::rgb(ps4?0x2856b5:0x377acb);
    const Color rim=Color::rgb(ps4?0x7196e7:0xa7d3ed);
    quad(list,cam.project({left,top,z}),cam.project({right,top,z}),
         cam.project({right,bottom,z}),cam.project({left,bottom,z}),shell);
    const float uleft=front?left+lip:right-lip;
    const float uright=front?right-lip:left+lip;
    if(image && std::fabs(cam.cosine)>0.08f) {
        textured_face(list,cam,image,uleft,uright,top+lip,bottom-lip,z,
                      Color::rgb(0xffffff),40);
    } else {
        // Do not invent a retail rear scan: use factual local metadata only.
        const Point a=cam.project({left+lip,top+lip,z});
        const Point b=cam.project({right-lip,top+lip,z});
        const Point c=cam.project({right-lip,bottom-lip,z});
        const Point d=cam.project({left+lip,bottom-lip,z});
        quad(list,a,b,c,d,Color::rgb(0x182b37));
        const float x0=std::min(a.x,b.x),x1=std::max(a.x,b.x);
        const float span=x1-x0;
        if(span>65.0f) {
            const float texttop=(a.y+b.y)*0.5f;
            if(front) {
                hui::ui::text(list,fonts.semibold,ps4?"PS4":"PS5",
                              x0+span*0.5f,texttop+28,
                              std::min(21.0f,span*0.2f),
                              Color::rgb(0xf1f6ff),hui::gfx::Align::center);
                hui::ui::paragraph(list,fonts.semibold,game.title,
                                   x0+10,texttop+69,
                                   std::min(16.0f,span*0.13f),span-20,20,
                                   Color::rgb(0xf1f6ff),3);
            } else {
                hui::ui::paragraph(list,fonts.regular,
                    game.blurb&&game.blurb[0]?game.blurb:game.title,
                    x0+8,texttop+28,std::min(13.0f,span*0.1f),
                    span-16,17,Color::rgb(0xf1f6ff),6);
            }
        }
    }
    // Separate transparent molded rim; this is the same case, not a
    // duplicate transparent rectangle behind a fictional second case.
    quad(list,cam.project({left,top,z}),cam.project({right,top,z}),
         cam.project({right,top+lip,z}),cam.project({left,top+lip,z}),rim.with_alpha(0.90f));
    quad(list,cam.project({left,bottom-lip,z}),cam.project({right,bottom-lip,z}),
         cam.project({right,bottom,z}),cam.project({left,bottom,z}),rim.with_alpha(0.74f));
    quad(list,cam.project({left,top,z}),cam.project({left+lip,top,z}),
         cam.project({left+lip,bottom,z}),cam.project({left,bottom,z}),rim.with_alpha(0.42f));
    quad(list,cam.project({right-lip,top,z}),cam.project({right,top,z}),
         cam.project({right,bottom,z}),cam.project({right-lip,bottom,z}),rim.with_alpha(0.58f));
    const Point hi=cam.project({left+lip,top+lip,z});
    const Point lo=cam.project({left+lip,bottom-lip,z});
    list.line(hi.x,hi.y,lo.x,lo.y,0.8f,Color::rgb(0xf0fbff,0.30f));
}
} // namespace

void niak_draw_rotating_case(hui::gfx::DrawList &list,const hui::demo::Item &game,
                             const hui::gfx::Rect &bounds,float seconds,
                             const hui::ui::Fonts &fonts) {
    using hui::gfx::Color;
    if(game.homebrew || !game.title_id[0]) {
        list.image(game.cover,bounds,
                   game.cover_is_image?hui::gfx::kFullUv:hui::gfx::kCanvasUv,
                   Color::rgb(0xffffff),26);
        return;
    }
    const bool ps4=game.title_id[0]=='C'; // CUSA / PPSA: no title-name heuristic.
    const float w=std::min(bounds.w*0.84f,bounds.h*0.80f);
    const float h=std::min(bounds.h*0.94f,w/0.79f);
    const float depth=w*(ps4?0.108f:0.102f);
    const float yaw=case_yaw(seconds);
    const Camera cam{bounds,std::cos(yaw),std::sin(yaw),w*3.9f};
    const float L=-w*0.5f,R=w*0.5f,T=-h*0.5f,B=h*0.5f;
    const float F=depth*0.5f,K=-depth*0.5f;
    const Color plastic=Color::rgb(ps4?0x234b9e:0x377bc3);
    const Color edge=Color::rgb(ps4?0x7398e2:0x9dd2ed);
    list.shadow({bounds.cx()-w*0.50f,bounds.cy()-h*0.46f,w*1.03f,h*0.98f},
                w*0.07f,23.0f,Color::rgb(0x020a15,0.56f));

    // Actual projected shell: top and bottom caps share all 8 vertices with
    // front/back/spine. They can never float away during a 180-degree turn.
    quad(list,cam.project({L,T,K}),cam.project({R,T,K}),
         cam.project({R,T,F}),cam.project({L,T,F}),edge.with_alpha(0.87f));
    quad(list,cam.project({L,B,K}),cam.project({R,B,K}),
         cam.project({R,B,F}),cam.project({L,B,F}),plastic);

    const bool left_spine=cam.sine>=0.0f;
    const float side_x=left_spine?L:R;
    quad(list,cam.project({side_x,T,K}),cam.project({side_x,T,F}),
         cam.project({side_x,B,F}),cam.project({side_x,B,K}),
         left_spine?plastic:Color::rgb(ps4?0x142c65:0x1c4a83));
    if(left_spine && game.case_spine && std::fabs(cam.sine)>0.13f)
        spine_texture(list,cam,game.case_spine,side_x,T+w*0.018f,
                      B-w*0.018f,depth,12);
    else if(!left_spine && std::fabs(cam.sine)>0.12f) {
        // Right-hand opening edge and recessed snap seal.
        const auto a=cam.project({R,T,K+depth*0.17f});
        const auto b=cam.project({R,B,K+depth*0.17f});
        list.line(a.x,a.y,b.x,b.y,1.5f,Color::rgb(0x0b244d,0.66f));
    }
    const bool front=cam.cosine>=0.0f;
    framed_face(list,cam,w,h,front?F:K,
                front?game.case_front:game.case_back,front,ps4,game,fonts);
    // Subtle edge glints follow the SAME projected corners as the cover.
    for(float y : {T+w*0.027f,B-w*0.027f}) {
        const auto a=cam.project({L,y,front?F:K});
        const auto b=cam.project({R,y,front?F:K});
        list.line(a.x,a.y,b.x,b.y,0.85f,Color::rgb(0xe5f5ff,0.28f));
    }
}
