// SPDX-License-Identifier: GPL-3.0-or-later
// Closed PS4/PS5 retail box: front, spine, back, molded outside only.
// It never opens or shows the disc tray; the selected tile remains the animation.
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
struct Point {float x,y;};
struct Surface {float x,y,z;};
constexpr float pi=3.14159265358979323846f;
float ease(float t) {
    t=std::clamp(t,0.0f,1.0f);
    return t*t*(3.0f-2.0f*t);
}
float animation(float seconds) {
    // Sealed case rotates: FRONT -> printed SPINE -> BACK -> FRONT.
    constexpr float front_hold=2.70f,turn=1.18f,back_hold=3.0f;
    constexpr float cycle=front_hold+turn+back_hold+turn;
    const float t=std::fmod(std::max(0.0f,seconds),cycle);
    if(t<front_hold)return 0.17f;
    if(t<front_hold+turn)return 0.17f+(pi-0.34f)*ease((t-front_hold)/turn);
    if(t<front_hold+turn+back_hold)return pi-0.17f;
    return pi-0.17f+(pi+0.34f)*ease((t-front_hold-turn-back_hold)/turn);
}
struct Camera {
    Rect box;
    float cosine,sine,distance,offset;
    Point project(Surface p) const {
        const float x=p.x*cosine+p.z*sine;
        const float z=p.z*cosine-p.x*sine;
        const float scale=distance/(distance-z);
        return {box.cx()+offset+x*scale,
                box.cy()+(p.y-0.108f*z)*scale};
    }
};
void quad(DrawList &d,Point a,Point b,Point c,Point e,Color color) {
    const float xy[]={a.x,a.y,b.x,b.y,c.x,c.y,e.x,e.y};
    d.polygon(xy,4,color);
}
template<class Project>
void panel(DrawList &d,Project project,float L,float R,float T,float B,
           float radius,Color fill) {
    const float centers[4][2]={
        {R-radius,T+radius},{R-radius,B-radius},
        {L+radius,B-radius},{L+radius,T+radius}};
    const float angle[4]={-pi*0.5f,0.0f,pi*0.5f,pi};
    float vertices[56];int n=0;
    for(int c=0;c<4;++c)for(int s=0;s<=6;++s) {
        const float a=angle[c]+pi*float(s)/12.0f;
        const auto p=project(centers[c][0]+radius*std::cos(a),
                             centers[c][1]+radius*std::sin(a));
        vertices[2*n]=p.x;vertices[2*n+1]=p.y;++n;
    }
    d.polygon(vertices,n,fill);
}
template<class Project>
void strip_art(DrawList &d,Project project,std::uint32_t texture,
               float u0,float u1,int slices,Color tint) {
    if(!texture)return;
    for(int i=0;i<slices;++i) {
        const float t0=float(i)/slices,t1=float(i+1)/slices;
        const Point top0=project(t0,0),top1=project(t1,0);
        const Point bot0=project(t0,1),bot1=project(t1,1);
        const float x0=std::min(top0.x,top1.x),x1=std::max(top0.x,top1.x);
        const float y0=std::min(std::min(top0.y,top1.y),std::min(bot0.y,bot1.y));
        const float y1=std::max(std::max(top0.y,top1.y),std::max(bot0.y,bot1.y));
        if(x1-x0<0.018f || y1-y0<0.05f)continue;
        const float au0=u0+(u1-u0)*t0,au1=u0+(u1-u0)*t1;
        const bool mirrored=top1.x<top0.x;
        // Independent prints meet at the identical fold vertices.
        d.image(texture,{x0-0.13f,y0,x1-x0+0.26f,y1-y0},
                {mirrored?au1:au0,0.0f,mirrored?au0-au1:au1-au0,1.0f},tint);
    }
}
void hinge(DrawList &d,const Camera &cam,float L,float T,float B,
           float K,float F,float w) {
    const Color blue=Color::rgb(0x1253c1,0.87f);
    // A continuous left hinge and three thicker injection-molded knuckles.
    quad(d,cam.project({L,T,K}),cam.project({L,T,F}),
         cam.project({L,B,F}),cam.project({L,B,K}),blue);
    const float h=B-T;
    for(int k=0;k<3;++k) {
        const float y0=T+h*(0.08f+0.36f*k),y1=y0+h*0.15f;
        quad(d,cam.project({L-w*0.010f,y0,K-w*0.006f}),
             cam.project({L-w*0.010f,y0,F+w*0.006f}),
             cam.project({L-w*0.010f,y1,F+w*0.006f}),
             cam.project({L-w*0.010f,y1,K-w*0.006f}),
             Color::rgb(0x1680e9,0.93f));
        const auto a=cam.project({L-w*0.010f,y0,F+w*0.008f});
        const auto b=cam.project({L-w*0.010f,y1,F+w*0.008f});
        d.line(a.x,a.y,b.x,b.y,1.05f,Color::rgb(0xc8faff,0.70f));
    }
}
void printed_face(DrawList &d,const Camera &cam,
                  const hui::demo::Item &game,const hui::ui::Fonts &fonts,
                  float L,float R,float T,float B,float z,float w,bool back) {
    const Color shell=Color::rgb(0x1873d1,0.77f);
    const float border=w*0.021f;
    const auto p=[&](float x,float y){return cam.project({x,y,z});};
    panel(d,p,L,R,T,B,w*0.039f,shell);
    const float paperTop=T+border,paperBottom=B-border;
    const float paperRight=R-w*0.016f;
    auto paper=[&](float t,float v){
        const float x=back?paperRight+(L-paperRight)*t
                          :L+(paperRight-L)*t;
        return p(x,paperTop+(paperBottom-paperTop)*v);
    };
    // Separate original scans meet at the SAME physical printed fold.
    // Back right edge -> spine rear edge; spine front edge -> front left edge.
    // No atlas, gap-filler, resampling, or plastic band inserted between them.
    const std::uint32_t image=back?game.case_back:game.case_front;
    if(image) strip_art(d,paper,image,0.0f,1.0f,60,Color::rgb(0xffffff));
    else {
        const auto a=paper(0,0),b=paper(1,0),c=paper(1,1),e=paper(0,1);
        quad(d,a,b,c,e,Color::rgb(0x183e67));
        const float left=std::min(a.x,b.x),span=std::fabs(b.x-a.x);
        if(span>74) {
            hui::ui::text(d,fonts.semibold,game.title_id[0]=='C'?"PS4":"PS5",
                          left+span*0.5f,a.y+30,20,Color::rgb(0xf5fcff),
                          hui::gfx::Align::center);
            hui::ui::paragraph(d,fonts.semibold,back?
                (game.blurb&&game.blurb[0]?game.blurb:game.title):game.title,
                left+12,a.y+76,15,span-24,19,Color::rgb(0xf7ffff),4);
        }
    }
    // The translucent outside plastic frames the print without hiding folds.
    const Point ltop=p(L,T),rtop=p(R,T),rbot=p(R,B),lbot=p(L,B);
    d.line(ltop.x,ltop.y,rtop.x,rtop.y,1.65f,Color::rgb(0x9ae5ff,0.86f));
    d.line(lbot.x,lbot.y,rbot.x,rbot.y,1.80f,Color::rgb(0x0c6ad8,0.80f));
    d.line(rtop.x,rtop.y,rbot.x,rbot.y,2.0f,Color::rgb(0x0c5ed1,0.86f));
}
void spine_print(DrawList &d,const Camera &cam,const hui::demo::Item &game,
                 float L,float T,float B,float F,float K,float w) {
    const float border=w*0.021f;
    const auto sleeve=[&](float t,float v){
        return cam.project({L,T+border+(B-T-2*border)*v,K+(F-K)*t});
    };
    // The spine scan reaches z=K and z=F exactly, adjoining both art faces.
    if(game.case_spine)
        strip_art(d,sleeve,game.case_spine,0.0f,1.0f,18,Color::rgb(0xffffff));
}
} // namespace

void niak_draw_rotating_case(hui::gfx::DrawList &d,const hui::demo::Item &game,
                             const hui::gfx::Rect &bounds,float seconds,
                             const hui::ui::Fonts &fonts) {
    if(game.homebrew || !game.title_id[0]) {
        d.image(game.cover,bounds,
                game.cover_is_image?hui::gfx::kFullUv:hui::gfx::kCanvasUv,
                Color::rgb(0xffffff),26);
        return;
    }
    const float yaw=animation(seconds);
    const float w=std::min(bounds.w*0.83f,bounds.h*0.78f);
    const float h=std::min(bounds.h*0.93f,w/0.755f);
    const float depth=w*(game.title_id[0]=='C'?0.102f:0.106f);
    const float L=-w*0.5f,R=w*0.5f,T=-h*0.5f,B=h*0.5f;
    const float F=depth*0.5f,K=-depth*0.5f;
    const Camera cam{bounds,std::cos(yaw),std::sin(yaw),w*4.1f,0.0f};
    d.shadow({bounds.cx()-w*0.50f,bounds.cy()-h*0.45f,w,h},
             w*0.060f,20,Color::rgb(0x07101a,0.42f));
    // Blue-transparent molded caps remain continuous at both folds.
    quad(d,cam.project({L,T,K}),cam.project({R,T,K}),
         cam.project({R,T,F}),cam.project({L,T,F}),
         Color::rgb(0x238cea,0.73f));
    quad(d,cam.project({L,B,K}),cam.project({R,B,K}),
         cam.project({R,B,F}),cam.project({L,B,F}),
         Color::rgb(0x1057c7,0.77f));

    // The right opening edge is visible as a SEALED seam, never opened.
    quad(d,cam.project({R,T,K}),cam.project({R,T,F}),
         cam.project({R,B,F}),cam.project({R,B,K}),
         Color::rgb(0x1873cf,0.82f));
    const auto seam_a=cam.project({R,T+w*0.085f,K+depth*0.19f});
    const auto seam_b=cam.project({R,B-w*0.085f,K+depth*0.19f});
    d.line(seam_a.x,seam_a.y,seam_b.x,seam_b.y,1.10f,
           Color::rgb(0x073b9e,0.64f));

    const bool back=std::cos(yaw)<0.0f;
    printed_face(d,cam,game,fonts,L,R,T,B,back?K:F,w,back);
    // Molded hinge is underneath the paper sleeve: never cover the print
    // with an opaque blue strip. All three scans share the fold vertices.
    hinge(d,cam,L,T,B,K,F,w);
    spine_print(d,cam,game,L,T,B,F,K,w);
}
