// SPDX-License-Identifier: GPL-3.0-or-later
// NiakPS5 closed retail case: three independent covers, correct hidden surfaces.
// Projected exterior geometry only: no opening, tray, loader, or duplicated shell.
#include "niak/case_renderer.hpp"
#include "demo/catalog.hpp"
#include "niak/case_fallback_layout.hpp"
#include "niak/case_back_media.hpp"
#include "ui/fonts.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <utility>

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
             int columns,int rows,bool flip_v=false,
             float uv_min=0.0f,float uv_max=1.0f,
             NiakCaseUvRegion crop={},float opacity=1.0f) {
    if(!texture)return;
    // DrawList only supports rectangular texture instances. Tessellate BOTH
    // directions to approximate a projected plane, never stretch a full image
    // over unrelated side geometry. UV orientation stays stable on both covers.
    for(int r=0;r<rows;++r)for(int col=0;col<columns;++col) {
        const float u0=float(col)/columns,u1=float(col+1)/columns;
        const float v0=float(r)/rows,v1=float(r+1)/rows;
        const float sample0=crop.top+(crop.bottom-crop.top)*
            (uv_min+(uv_max-uv_min)*v0);
        const float sample1=crop.top+(crop.bottom-crop.top)*
            (uv_min+(uv_max-uv_min)*v1);
        const float cu0=crop.left+(crop.right-crop.left)*u0;
        const float cu1=crop.left+(crop.right-crop.left)*u1;
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
                   {reverse?cu1:cu0,flip_v?1.0f-sample0:sample0,
                    reverse?cu0-cu1:cu1-cu0,
                    flip_v?sample0-sample1:sample1-sample0},
                   Color::rgb(0xffffff,std::clamp(opacity,0.f,1.f)));
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
    // Near the stationary front/back holds the perspective is almost
    // rectangular. Reduce per-frame texture quads by ~75%, but retain full
    // tessellation as soon as the case rotates toward the edge.
    const bool near_frontal=std::fabs(camera.cs)>0.985f;
    const int face_columns=near_frontal?12:32;
    const int face_rows=near_frontal?6:9;
    const auto texture=back?item.case_back:item.case_front;
    if(texture) {
        printed(list,texture,paper,face_columns,face_rows);
    } else {
        // Recompose ONLY this missing face. Official scans use the early
        // texture branch and bypass EVERY fixed platform overlay below.
        const bool ps4=item.title_id[0]=='C';
        const auto layout=niak_case_fallback_layout(ps4);
        auto block=[&](float x0,float y0,float x1,float y1,Color color) {
            polygon4(list,paper(x0,y0),paper(x1,y0),
                     paper(x1,y1),paper(x0,y1),color);
        };
        // Real normalized sleeve width:height is ~0.76:1.
        constexpr float case_aspect=0.76f;
        const auto panel=[&](std::uint32_t image,float aspect,
                             float x0,float y0,float x1,float y1,
                             float opacity=1.f) {
            if(!image)return;
            const auto region=niak_case_cover_crop(
                aspect,case_aspect*(x1-x0)/(y1-y0));
            const auto coords=[&](float u,float v) {
                return paper(x0+(x1-x0)*u,y0+(y1-y0)*v);
            };
            printed(list,image,coords,near_frontal?12:24,
                    near_frontal?8:15,false,0.f,1.f,region,opacity);
        };
        // ONE uninterrupted opaque printable sheet lives between plastic
        // and ALL front/back elements. The design never gives screenshots,
        // captions or blank areas their own separate background cards.
        block(0.f,0.f,1.f,1.f,back?
              Color::rgb(ps4?0x161a19:0xffffff):
              Color::rgb(0x0c1727));
        if(!back) {
            // Artwork covers the entire PRINT below the PS4/PS5 masthead.
            // Background-size: cover uses cropped UVs, not width stretching.
            const auto art=item.case_poster?item.case_poster:
                item.case_scene?item.case_scene:
                item.case_hero?item.case_hero:
                (item.cover_is_image?item.cover:0);
            const float art_aspect=item.case_poster?item.poster_aspect:
                item.case_scene?item.case_scene_aspect:
                item.case_hero?item.case_hero_aspect:1.0f;
            const bool icon_fallback=art && art==item.cover &&
                !item.case_poster && !item.case_scene && !item.case_hero;
            if(icon_fallback) {
                // One fallback illustration, not the same app/game icon
                // twice. Cover-crop the source into the whole printable
                // front below the console masthead without stretching width.
                panel(art,art_aspect,0.f,layout.front_header,1.f,1.f);
            } else {
                // Poster/fanart also uses cover UVs, respecting source aspect.
                panel(art,art_aspect,0.f,layout.front_header,1.f,1.f);
            }
            if(item.case_template_front) {
                // The masthead is invariant and occupies only the top ~10.8%.
                const auto banner=[&](float u,float v){
                    return paper(u,layout.front_header*v);
                };
                printed(list,item.case_template_front,banner,
                        near_frontal?12:24,near_frontal?3:5);
            } else {
                block(0.f,0.f,1.f,layout.front_header,
                      Color::rgb(ps4?0x04499c:0xeef6ff));
                block(0.f,layout.front_header-0.004f,1.f,
                      layout.front_header,Color::rgb(0x2884e7));
            }
            // Never stamp an additional clear logo onto existing artwork.
            // Posters and game icons may already contain the game's wordmark.
        } else {
            // Fanart - Background is the soft full-page illustration IN THE
            // paper, not a separate card behind screenshots or text.
            // The uninterrupted PS4/PS5 base colour remains visible below
            // this semi-transparent cover image. Actual gameplay and title
            // screenshots are then placed over it as distinct assets.
            if(item.case_hero)
                panel(item.case_hero,item.case_hero_aspect,
                      0.f,0.f,1.f,1.f,ps4?0.16f:0.11f);
            const float gutter=0.018f;
            // Only two genuinely different gameplay screenshots can form
            // two columns. With zero/one screenshot, select ONE existing
            // scene/fanart/icon in priority order and print it full width.
            // In particular, never tile pic1 and hero side by side: they
            // might be visually identical despite having different handles.
            auto chosen=niak_select_back_media({
                {item.case_shot1,item.case_shot1_aspect},
                {item.case_shot2,item.case_shot2_aspect}
            });
            // Only dedicated LaunchBox back media belongs on a recreated
            // reverse cover. The installed icon/pic1 can match the main
            // library art: NEVER repeat it on the back as fake gameplay.
            if(!chosen.first.texture && item.case_hero)
                chosen.first={item.case_hero,item.case_hero_aspect};
            if(chosen.first.texture) {
                if(chosen.second.texture) {
                    panel(chosen.first.texture,chosen.first.aspect,
                          gutter,layout.back_art_top,
                          0.5f-gutter*0.5f,layout.back_art_bottom);
                    panel(chosen.second.texture,chosen.second.aspect,
                          0.5f+gutter*0.5f,layout.back_art_top,
                          1.f-gutter,layout.back_art_bottom);
                } else {
                    // With ONE source, use one full-width print: NO duplicate.
                    // With ZERO sources the opaque background stays visible.
                    panel(chosen.first.texture,chosen.first.aspect,
                          gutter,layout.back_art_top,
                          1.f-gutter,layout.back_art_bottom);
                }
            }
            // The naturally exposed gap shows the SAME underlying paper;
            // no extra rectangle over the print and no seams between pieces.
            if(item.case_template_back) {
                const auto footer=[&](float u,float v) {
                    return paper(u,layout.back_footer+
                                    (1.0f-layout.back_footer)*v);
                };
                printed(list,item.case_template_back,footer,
                        near_frontal?12:24,near_frontal?6:9);
            }
            // Without a footer image, leave the SAME opaque paper visible;
            // do not attach a separately coloured rectangle to the bottom.
        }
        // Text in a perspective plane is legible only when the face is nearly
        // straight. Hide these planar labels edge-on; never overlay the spine.
        if(std::fabs(camera.cs)>0.90f) {
            const auto text_bounds=[&](float left,float right,float line){
                const auto aa=paper(left,line),bb=paper(right,line);
                return std::pair<float,float>{std::min(aa.x,bb.x),
                                              std::fabs(bb.x-aa.x)};
            };
            if(!back) {
                // No duplicate game title on front; the icon is sufficient.
                if(!item.case_template_front) {
                    const auto top=text_bounds(0.08f,0.92f,0.047f);
                    const auto pos=paper(0.5f,0.047f);
                    hui::ui::text(list,fonts.semibold,ps4?"PS4":"PS5",
                                  top.first+top.second*0.5f,pos.y,
                                  std::clamp(top.second*0.095f,12.f,25.f),
                                  Color::rgb(ps4?0xffffff:0x164b84),
                                  hui::gfx::Align::center);
                }
            } else {
                // Editorial copy sits entirely ABOVE the two-shot gallery.
                // An original back never reaches this branch.
                const float ty=layout.back_text_top+0.014f;
                const auto area=text_bounds(0.042f,0.958f,ty);
                const auto pos=paper(0.042f,ty);
                if(area.second>65.f) {
                    const char *description=item.blurb&&item.blurb[0]?
                        item.blurb:item.title;
                    hui::ui::paragraph(list,fonts.regular,description,
                        area.first,pos.y,
                        std::clamp(area.second*0.046f,9.f,14.f),
                        area.second,ps4?14.f:16.f,
                        Color::rgb(ps4?0xf3f7ff:0x161a19),ps4?6:8);
                }
                // If the owner lacks the invariant footer, show a neutral
                // disclaimer instead of another game's classification/SKU.
                if(!item.case_template_back) {
                    const auto foot=text_bounds(0.055f,0.945f,0.95f);
                    const auto pos=paper(0.055f,0.95f);
                    hui::ui::paragraph(list,fonts.regular,
                        "APERÇU RECONSTITUÉ — NON OFFICIEL",
                        foot.first,pos.y,10.f,foot.second,15.f,
                        Color::rgb(ps4?0xf3f7ff:0x18394f),2);
                }
            }
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
    else if(item.case_template_spine) {
        // Preserve the real vertical PS4/PS5 masthead. Its lower 12% contains
        // an ID belonging to the example box, so mask that area; never show a
        // different game's SKU on the current case.
        auto upper=[&](float u,float v) {
            return paper(u,v*0.88f);
        };
        printed(list,item.case_template_spine,upper,8,15,false,0.f,0.88f);
        polygon4(list,paper(0,0.88f),paper(1,0.88f),
                 paper(1,1.f),paper(0,1.f),
                 Color::rgb(item.title_id[0]=='C'?0x081019:0xe8eef6));
    } else {
        // Standard PS4/PS5 blue plastic spine when LaunchBox has no scan.
        // It is a physical case side, not a fabricated game illustration.
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
    if(!item.title_id[0] || item.application) {
        list.rounded_rect(bounds,26,Color::rgb(0x0f2231));
        if(item.cover)list.image(item.cover,bounds,
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
