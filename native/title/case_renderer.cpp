// SPDX-License-Identifier: GPL-3.0-or-later
// A continuous PS4/PS5 retail sleeve around a translucent hinged Blu-ray shell.
// Native OpenGL drawlist: projected physical surfaces, no second loading screen.
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
constexpr float kBackEnd=460.0f/964.0f;
constexpr float kSpineEnd=504.0f/964.0f;
float ease(float t) {
    t=std::clamp(t,0.0f,1.0f);
    return t*t*(3.0f-2.0f*t);
}
struct Motion {float yaw,opening;};
Motion animation(float seconds) {
    // The free RIGHT edge unlatches; the LEFT molded spine remains the hinge.
    // Front, opening, interior, closing, back, front. No separate loader.
    constexpr float front=2.45f,open=1.18f,inside=2.05f,close=1.18f;
    constexpr float turn=1.05f,back=2.65f,again=1.05f;
    constexpr float cycle=front+open+inside+close+turn+back+again;
    const float t=std::fmod(std::max(0.0f,seconds),cycle);
    const float maximum=2.68f; // 153 degrees, like a book opening on its left edge
    if(t<front)return {0.17f,0};
    if(t<front+open)return {0.17f,maximum*ease((t-front)/open)};
    if(t<front+open+inside)return {0.17f,maximum};
    if(t<front+open+inside+close)
        return {0.17f,maximum*(1.0f-ease((t-front-open-inside)/close))};
    if(t<front+open+inside+close+turn)
        return {0.17f+(pi-0.34f)*ease((t-front-open-inside-close)/turn),0};
    if(t<front+open+inside+close+turn+back)
        return {pi-0.17f,0};
    return {pi-0.17f+(pi+0.34f)*ease(
        (t-front-open-inside-close-turn-back)/again),0};
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
        // A single texture atlas is sampled right across both folds, with
        // precisely matching UV endpoints at back/spine/front boundaries.
        d.image(texture,{x0-0.13f,y0,x1-x0+0.26f,y1-y0},
                {mirrored?au1:au0,0.0f,mirrored?au0-au1:au1-au0,1.0f},tint);
    }
}
Surface flap(float x,float y,float offset,float hinge,float front,float angle) {
    const float delta=x-hinge;
    return {hinge+delta*std::cos(angle)-offset*std::sin(angle),y,
            front+delta*std::sin(angle)+offset*std::cos(angle)};
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
void disk_tray(DrawList &d,const Camera &cam,float L,float R,float T,float B,
               float K,float w,float h) {
    // Empty PS5/PS4 case: transparent right-hand tray, molded disc seat,
    // centre hub and cover-retaining clips. No fictitious game disc.
    const float z=K+w*0.018f;
    const auto plane=[&](float x,float y) {return cam.project({x,y,z});};
    panel(d,plane,L+w*0.016f,R-w*0.018f,T+w*0.020f,B-w*0.020f,
          w*0.034f,Color::rgb(0x55b8f2,0.73f));
    // Deep blue rails around the actual plastic perimeter.
    for(float x:{L+w*0.035f,R-w*0.035f}) {
        const auto a=plane(x,T+w*0.064f),b=plane(x,B-w*0.064f);
        d.line(a.x,a.y,b.x,b.y,w*0.007f,Color::rgb(0x126bca,0.56f));
    }
    const float cx=(L+R)*0.5f,cy=(T+B)*0.5f;
    for(const auto &ring : {0.273f,0.243f,0.110f,0.075f,0.034f}) {
        const float outer=w*ring,inner=outer-w*(ring>0.20f?0.011f:0.008f);
        for(int i=0;i<48;++i) {
            const float a=2*pi*i/48.0f,b=2*pi*(i+1)/48.0f;
            quad(d,plane(cx+outer*std::cos(a),cy+outer*std::sin(a)),
                 plane(cx+outer*std::cos(b),cy+outer*std::sin(b)),
                 plane(cx+inner*std::cos(b),cy+inner*std::sin(b)),
                 plane(cx+inner*std::cos(a),cy+inner*std::sin(a)),
                 Color::rgb(ring>0.20f?0x1676d8:0x1c83dd,0.58f));
        }
    }
    for(int i=0;i<4;++i) {
        const float a=pi*0.5f*i;
        const float x=cx+w*0.095f*std::cos(a);
        const float y=cy+w*0.095f*std::sin(a);
        const auto p0=plane(x-w*0.016f,y-w*0.015f);
        const auto p1=plane(x+w*0.016f,y-w*0.015f);
        const auto p2=plane(x+w*0.016f,y+w*0.015f);
        const auto p3=plane(x-w*0.016f,y+w*0.015f);
        quad(d,p0,p1,p2,p3,Color::rgb(0x187ace,0.69f));
    }
    // Front opening catches on the RIGHT edge; not on the spine.
    for(float relY:{0.21f,0.50f,0.79f}) {
        const float y=T+h*relY;
        const auto a=plane(R-w*0.022f,y-w*0.022f);
        const auto b=plane(R-w*0.006f,y-w*0.022f);
        const auto c=plane(R-w*0.006f,y+w*0.022f);
        const auto e=plane(R-w*0.022f,y+w*0.022f);
        quad(d,a,b,c,e,Color::rgb(0x0c58c6,0.66f));
    }
}
void inside_door(DrawList &d,const Camera &cam,float L,float R,float T,float B,
                 float F,float w,float angle) {
    const auto inner=[&](float x,float y) {
        return cam.project(flap(x,y,-w*0.018f,L,F,angle));};
    panel(d,inner,L,R,T,B,w*0.038f,Color::rgb(0x5bb7ee,0.84f));
    // Thin clear insertion sleeve: top/bottom arcs and retaining tabs.
    for(float y:{T+w*0.18f,B-w*0.18f}) {
        Point last={};
        for(int s=0;s<=16;++s) {
            const float t=float(s)/16.0f;
            const float x=L+w*(0.25f+0.48f*t);
            const float rise=(1-(2*t-1)*(2*t-1))*w*0.075f;
            const auto q=inner(x,y+(y<(T+B)*0.5f?rise:-rise));
            if(s) d.line(last.x,last.y,q.x,q.y,1.45f,
                         Color::rgb(0x0d63bd,0.54f));
            last=q;
        }
    }
    const auto a=inner(R-w*0.032f,T+w*0.080f);
    const auto b=inner(R-w*0.032f,B-w*0.080f);
    d.line(a.x,a.y,b.x,b.y,1.5f,Color::rgb(0xe2fbff,0.64f));
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
    const std::uint32_t image=game.case_wrap?game.case_wrap:
                              back?game.case_back:game.case_front;
    const float u0=game.case_wrap?(back?0.0f:kSpineEnd):0.0f;
    const float u1=game.case_wrap?(back?kBackEnd:1.0f):1.0f;
    if(image) strip_art(d,paper,image,u0,u1,60,Color::rgb(0xffffff));
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
    // Translucent PET film and molded blue rim lie OVER the continuous insert.
    // The LEFT paper reaches the hinge; no extra opaque border cuts its fold.
    const Point ltop=p(L,T),rtop=p(R,T),rbot=p(R,B),lbot=p(L,B);
    d.line(ltop.x,ltop.y,rtop.x,rtop.y,1.65f,Color::rgb(0x9ae5ff,0.86f));
    d.line(lbot.x,lbot.y,rbot.x,rbot.y,1.80f,Color::rgb(0x0c6ad8,0.80f));
    d.line(rtop.x,rtop.y,rbot.x,rbot.y,2.0f,Color::rgb(0x0c5ed1,0.86f));
}
void front_door(DrawList &d,const Camera &cam,
                const hui::demo::Item &game,const hui::ui::Fonts &fonts,
                float L,float R,float T,float B,float F,float w,float angle) {
    const auto outer=[&](float x,float y){return cam.project(flap(x,y,0,L,F,angle));};
    const auto inner=[&](float x,float y){return cam.project(flap(x,y,-w*0.025f,L,F,angle));};
    const bool exterior=std::cos(angle)>=0;
    // The cover has its own thickness. Its free RIGHT edge separates from the
    // stationary rear tray; only the LEFT edge shares the hinge.
    quad(d,outer(R,T),inner(R,T),inner(R,B),outer(R,B),
         Color::rgb(0x1476da,0.86f));
    quad(d,outer(L,T),outer(R,T),inner(R,T),inner(L,T),
         Color::rgb(0x5bc4f8,0.81f));
    quad(d,inner(L,B),inner(R,B),outer(R,B),outer(L,B),
         Color::rgb(0x1256be,0.75f));
    if(!exterior) {
        inside_door(d,cam,L,R,T,B,F,w,angle);
    }else{
        panel(d,outer,L,R,T,B,w*0.039f,Color::rgb(0x1775d4,0.74f));
        const float border=w*0.021f;
        const float paperRight=R-w*0.016f;
        auto paper=[&](float t,float v){
            return outer(L+(paperRight-L)*t,T+border+(B-T-2*border)*v);
        };
        const auto image=game.case_wrap?game.case_wrap:game.case_front;
        if(image)
            strip_art(d,paper,image,game.case_wrap?kSpineEnd:0.0f,
                      1.0f,60,Color::rgb(0xffffff));
        else {
            const auto a=paper(0,0),b=paper(1,0),c=paper(1,1),e=paper(0,1);
            quad(d,a,b,c,e,Color::rgb(0x18416f));
            if(std::fabs(a.x-b.x)>74)
                hui::ui::paragraph(d,fonts.semibold,game.title,
                                   std::min(a.x,b.x)+8,a.y+74,16,
                                   std::fabs(b.x-a.x)-16,19,
                                   Color::rgb(0xf4faff),3);
        }
        // Blue-translucent film follows the cover, not a second fake cover.
        const auto ta=outer(L,T),tb=outer(R,T),ba=outer(L,B),bb=outer(R,B);
        d.line(ta.x,ta.y,tb.x,tb.y,1.75f,Color::rgb(0x9de9ff,0.81f));
        d.line(ba.x,ba.y,bb.x,bb.y,1.75f,Color::rgb(0x1572dc,0.79f));
        d.line(tb.x,tb.y,bb.x,bb.y,2.0f,Color::rgb(0x0c54c8,0.93f));
    }
}
void spine_print(DrawList &d,const Camera &cam,const hui::demo::Item &game,
                 float L,float T,float B,float F,float K,float w) {
    const float border=w*0.021f;
    const auto sleeve=[&](float t,float v){
        return cam.project({L,T+border+(B-T-2*border)*v,K+(F-K)*t});
    };
    const auto img=game.case_wrap?game.case_wrap:game.case_spine;
    const float a=game.case_wrap?kBackEnd:0.0f;
    const float b=game.case_wrap?kSpineEnd:1.0f;
    if(img)strip_art(d,sleeve,img,a,b,18,Color::rgb(0xffffff));
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
    const Motion motion=animation(seconds);
    const float opened=ease(std::clamp(motion.opening/2.68f,0.0f,1.0f));
    const float base=std::min(bounds.w*0.83f,bounds.h*0.78f);
    // An open book occupies nearly twice the width of a closed case.
    // Scale smoothly to keep the animation inside the focused tile.
    const float w=base*(1.0f-0.40f*opened);
    const float h=std::min(bounds.h*0.93f,w/0.755f);
    const float depth=w*(game.title_id[0]=='C'?0.102f:0.106f);
    const float L=-w*0.5f,R=w*0.5f,T=-h*0.5f,B=h*0.5f;
    const float F=depth*0.5f,K=-depth*0.5f;
    const Camera cam{bounds,std::cos(motion.yaw),std::sin(motion.y),
                     w*4.1f,w*0.26f*opened};
    d.shadow({bounds.cx()-w*0.50f,bounds.cy()-h*0.45f,w,h},
             w*0.060f,20,Color::rgb(0x07101a,0.42f));
    // Blue-transparent molded caps remain continuous at both folds.
    quad(d,cam.project({L,T,K}),cam.project({R,T,K}),
         cam.project({R,T,F}),cam.project({L,T,F}),
         Color::rgb(0x238cea,0.73f));
    quad(d,cam.project({L,B,K}),cam.project({R,B,K}),
         cam.project({R,B,F}),cam.project({L,B,F}),
         Color::rgb(0x1057c7,0.77f));

    if(std::cos(motion.yaw)<0) {
        // Back exterior faces the viewer: uninterrupted back/spine wrap.
        printed_face(d,cam,game,fonts,L,R,T,B,K,w,true);
    }else {
        // When the right edge opens, the stationary disc tray is exposed.
        disk_tray(d,cam,L,R,T,B,K,w,h);
        front_door(d,cam,game,fonts,L,R,T,B,F,w,motion.opening);
    }
    // The plastic tube lies OUTSIDE the paper fold. Never put a blue strip
    // BETWEEN the printed back, spine, and front portions of the jacket.
    spine_print(d,cam,game,L,T,B,F,K,w);
    hinge(d,cam,L,T,B,K,F,w);
}
