// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Reduce permanent GPU footprint of per-game PS4/PS5 case print textures.
// Never upscale scans or deform their aspect ratios; bilinear sampling keeps
// small publisher typography readable in the projected 3D sleeve.
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

inline bool niak_scale_case_rgba(std::vector<unsigned char>& pixels,
                                 unsigned &w,unsigned &h,
                                 unsigned max_w,unsigned max_h) {
    if(!w||!h||!max_w||!max_h||
       pixels.size()!=std::size_t(w)*h*4u)return false;
    if(w<=max_w&&h<=max_h)return true;
    const float scale=std::min(float(max_w)/float(w),
                               float(max_h)/float(h));
    const unsigned nw=std::max(1u,std::min(max_w,
        static_cast<unsigned>(std::floor(w*scale+0.5f))));
    const unsigned nh=std::max(1u,std::min(max_h,
        static_cast<unsigned>(std::floor(h*scale+0.5f))));
    std::vector<unsigned char> reduced(std::size_t(nw)*nh*4u);
    for(unsigned y=0;y<nh;++y) {
        const float sy=std::max(0.0f,(float(y)+0.5f)*float(h)/float(nh)-0.5f);
        const unsigned y0=std::min(h-1u,static_cast<unsigned>(sy));
        const unsigned y1=std::min(h-1u,y0+1u);
        const float fy=std::min(1.0f,sy-float(y0));
        for(unsigned x=0;x<nw;++x) {
            const float sx=std::max(0.0f,(float(x)+0.5f)*float(w)/float(nw)-0.5f);
            const unsigned x0=std::min(w-1u,static_cast<unsigned>(sx));
            const unsigned x1=std::min(w-1u,x0+1u);
            const float fx=std::min(1.0f,sx-float(x0));
            for(unsigned c=0;c<4;++c) {
                const float a=pixels[(std::size_t(y0)*w+x0)*4u+c];
                const float b=pixels[(std::size_t(y0)*w+x1)*4u+c];
                const float d=pixels[(std::size_t(y1)*w+x0)*4u+c];
                const float e=pixels[(std::size_t(y1)*w+x1)*4u+c];
                const float value=(a+(b-a)*fx)*(1.f-fy)+(d+(e-d)*fx)*fy;
                reduced[(std::size_t(y)*nw+x)*4u+c]=static_cast<unsigned char>(
                    std::max(0.f,std::min(255.f,value+0.5f)));
            }
        }
    }
    pixels.swap(reduced);
    w=nw;h=nh;
    return true;
}
