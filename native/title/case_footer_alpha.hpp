// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Preserve the owner's lower-back fixed graphic, but remove its embedded
// background so all text/icons are ink over one continuous PS4/PS5 paper.
#include <algorithm>
#include <cstddef>
#include <cstdlib>
#include <vector>
inline bool niak_footer_paper_to_alpha(std::vector<unsigned char>& rgba,
                                        unsigned width,unsigned height,
                                        bool ps4) {
    if(!width || !height || width>2048 || height>1536 ||
       std::size_t(width)*height>2500000u ||
       rgba.size()!=std::size_t(width)*height*4u)return false;
    const std::size_t pixels=std::size_t(width)*height;
    std::size_t existing_clear=0;
    for(std::size_t i=3;i<rgba.size();i+=4)
        existing_clear+=rgba[i]<240;
    // Already properly extracted: do not damage existing alpha and edges.
    if(existing_clear*100>=pixels*2)return true;
    const int paper_r=ps4?24:255,paper_g=ps4?27:255,paper_b=ps4?24:255;
    const int transparent_until=ps4?10:12,opaque_from=ps4?48:58;
    std::size_t transparent=0;
    for(std::size_t i=0;i<rgba.size();i+=4) {
        const int delta=std::max({std::abs(int(rgba[i])-paper_r),
                                  std::abs(int(rgba[i+1])-paper_g),
                                  std::abs(int(rgba[i+2])-paper_b)});
        const int a=delta<=transparent_until?0:
                    delta>=opaque_from?255:
                    (delta-transparent_until)*255/
                         (opaque_from-transparent_until);
        rgba[i+3]=static_cast<unsigned char>(
            std::min<int>(rgba[i+3],a));
        transparent+=rgba[i+3]<32;
    }
    // An unrelated fully opaque photo must not replace the base sheet.
    return transparent*100>=pixels*4;
}
