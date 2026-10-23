// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Source-agnostic physical case layout for missing faces ONLY.
// A genuine scanned front/back/spine bypasses all of these overlays.
// Ratios use the face's normalized coordinate system (height == 1).
#include <algorithm>
#include <cmath>

struct NiakCaseFallbackLayout {
    float front_header;   // PS4/PS5 platform masthead, locked to top.
    float back_footer;    // legal footer starts here, locked to bottom.
    float back_text_top;  // editorial copy wholly above the fixed footer.
    float back_art_top;   // 2-up screen/art region, no overlap with text.
    float back_art_bottom;
};
constexpr NiakCaseFallbackLayout niak_case_fallback_layout(bool ps4) {
    // Original owner-supplied banners are ~7:1, so on a 0.76 width/height
    // box the header occupies ~10.8% of its height, NOT a thick 20% stripe.
    // Footer: PS4 647x362, PS5 1000x411 with front face aspect ~0.76.
    return {0.108f, ps4?0.576f:0.688f, 0.025f,
            ps4?0.265f:0.315f, ps4?0.555f:0.666f};
}
struct NiakCaseUvRegion {
    float left=0.0f,right=1.0f,top=0.0f,bottom=1.0f;
};
inline NiakCaseUvRegion niak_case_cover_crop(float source_aspect,
                                              float target_aspect) {
    NiakCaseUvRegion out{};
    if(!(std::isfinite(source_aspect)&&std::isfinite(target_aspect)) ||
       source_aspect<=0.f || target_aspect<=0.f)return out;
    // Never deform a square icon or landscape pic1 to fit portrait plastic.
    if(source_aspect>target_aspect) {
        const float span=std::clamp(target_aspect/source_aspect,0.01f,1.0f);
        out.left=(1.f-span)*0.5f;
        out.right=out.left+span;
    } else {
        const float span=std::clamp(source_aspect/target_aspect,0.01f,1.0f);
        out.top=(1.f-span)*0.5f;
        out.bottom=out.top+span;
    }
    return out;
}
