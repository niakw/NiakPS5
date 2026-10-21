// SPDX-License-Identifier: GPL-3.0-or-later
// Lightweight physical PS4/PS5 case projection using the common OpenGL drawlist.
// Case faces, barcode/text, and original regional front/back scans are distinct.
#include "niak/case_renderer.hpp"
#include "demo/catalog.hpp"
#include "ui/fonts.hpp"
#include <algorithm>
#include <cmath>

void niak_draw_rotating_case(hui::gfx::DrawList &list,const hui::demo::Item &game,
                            const hui::gfx::Rect &bounds,float seconds,
                            const hui::ui::Fonts &fonts) {
    using namespace hui;
    using gfx::Color;
    using gfx::Rect;
    const float tau=6.28318530718f,pi=3.14159265359f;
    const float front_hold=3.0f,turn=0.78f,back_hold=3.6f,total=front_hold+2*turn+back_hold;
    const float phase=std::fmod(std::max(0.0f,seconds),total);
    float yaw=0;
    if(phase<front_hold) yaw=0.20f;
    else if(phase<front_hold+turn) {
        const float u=(phase-front_hold)/turn;
        yaw=0.20f+(pi-0.40f)*u*u*(3-2*u);
    }else if(phase<front_hold+turn+back_hold)yaw=pi-0.20f;
    else {
        const float u=(phase-front_hold-turn-back_hold)/turn;
        yaw=(pi-0.20f)+(pi+0.40f)*u*u*(3-2*u);
    }
    yaw=std::fmod(yaw,tau);
    const bool front=std::cos(yaw)>=0.0f;
    const bool is_ps4=game.title_id[0]=='C';
    // Selected game receives a physical retail case. Applications keep their
    // natural square icon rather than a fictional PS5/PS4 commercial package.
    if(game.homebrew || !game.title_id[0]) {
        list.image(game.cover,bounds,
                   game.cover_is_image?gfx::kFullUv:gfx::kCanvasUv,
                   Color::rgb(0xffffff),30);
        return;
    }
    const float actual_w=bounds.w*0.77f;
    const float x0=bounds.cx()-actual_w*0.5f;
    const float y0=bounds.y;
    const float face_w=std::max(7.0f,actual_w*std::fabs(std::cos(yaw)));
    const float face_x=bounds.cx()-face_w*0.5f;
    const float side_w=5.5f+17.5f*std::fabs(std::sin(yaw));
    const bool right=std::sin(yaw)>=0.0f;
    const Rect caseface{face_x,y0,face_w,bounds.h};
    const Rect spine{right?caseface.x+caseface.w-1:caseface.x-side_w+1,
                     y0+3,side_w,bounds.h-6};
    const Color plastic=is_ps4?Color::rgb(0x104db1):Color::rgb(0xcbdde9);
    const Color edge=is_ps4?Color::rgb(0x083273):Color::rgb(0xa4b9ca);
    list.shadow({x0+16,y0+25,actual_w,bounds.h},25,38,Color::rgb(0x000000,0.62f));
    list.rounded_rect({caseface.x-4,y0-3,caseface.w+8,bounds.h+6},16,plastic);
    list.rounded_rect(spine,5,edge);
    if(face_w>18) {
        const Rect paper{caseface.x+6,caseface.y+28,
                         std::max(2.0f,caseface.w-12),caseface.h-40};
        const auto face=front?game.case_front:game.case_back;
        const bool real=face!=0;
        if(real) {
            list.image(face,paper,gfx::kFullUv,Color::rgb(0xffffff),2);
        }else {
            // Never counterfeit printed rear artwork. A verified title and
            // its real publisher metadata can be shown on a neutral insert.
            list.rounded_rect(paper,4,Color::rgb(0x1b3037));
            if(face_w>180) {
                if(front && game.cover) {
                    const float sz=std::min(260.0f,paper.w-26);
                    list.image(game.cover,{paper.cx()-sz*0.5f,paper.y+25,sz,sz},
                               game.cover_is_image?gfx::kFullUv:gfx::kCanvasUv,
                               Color::rgb(0xffffff),5);
                }else if(!front) {
                    ui::text(list,fonts.semibold,"FICHE DU JEU",paper.x+17,paper.y+45,
                             21,Color::rgb(0x9af2de));
                    ui::paragraph(list,fonts.regular,game.blurb,paper.x+17,paper.y+94,
                                  18,paper.w-34,25,Color::rgb(0xe2ebed),6);
                }
            }
        }
        const Rect band{caseface.x+5,caseface.y+4,caseface.w-10,25};
        list.rounded_rect(band,4,is_ps4?Color::rgb(0x174eab):Color::rgb(0xe9f0f7));
        if(face_w>85) {
            ui::text(list,fonts.semibold,is_ps4?"PS4":"PS5",band.x+band.w*0.5f,
                     band.y+19,18,is_ps4?Color::rgb(0xffffff):Color::rgb(0x1f3857),
                     gfx::Align::center);
        }
    }
    // Plastic edges: one shell, not a duplicated outer case.
    list.bordered_rect({caseface.x-4,y0-3,caseface.w+8,bounds.h+6},
                       16,Color::rgb(0x000000,0),2,
                       Color::rgb(0xd9eff5,0.55f));
    list.line(spine.x+spine.w-2,spine.y+8,spine.x+spine.w-2,
              spine.y+spine.h-8,1,Color::rgb(0xffffff,0.23f));
}
