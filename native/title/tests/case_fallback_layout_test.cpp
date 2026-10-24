// SPDX-License-Identifier: GPL-3.0-or-later
#include "../case_fallback_layout.hpp"
#include <cassert>
#include <cmath>
static bool near(float x,float y) {return std::fabs(x-y)<0.003f;}
int main() {
    const auto ps4=niak_case_fallback_layout(true);
    const auto ps5=niak_case_fallback_layout(false);
    assert(near(ps4.front_header,0.108f));
    assert(near(ps5.front_header,0.108f));
    assert(ps4.back_footer<ps5.back_footer);
    for(auto shape:{ps4,ps5}) {
        assert(shape.front_header>0.f && shape.front_header<0.2f);
        assert(shape.back_text_top<shape.back_art_top);
        assert(shape.back_art_top<shape.back_art_bottom);
        assert(shape.back_art_bottom<shape.back_footer);
        assert(shape.back_footer<1.f);
    }
    // Cover crop: landscape pic1 fills portrait print without squeezing.
    const auto panoramic=niak_case_cover_crop(16.f/9.f,0.76f/(1.f-ps5.front_header));
    assert(panoramic.left>0.2f && panoramic.right<0.8f);
    assert(near(panoramic.top,0.f)&&near(panoramic.bottom,1.f));
    const auto square=niak_case_cover_crop(1.f,0.76f/(1.f-ps4.front_header));
    assert(square.left>0.f&&square.right<1.f);
    // 1:1 source on a portrait paper: horizontal centre crop, no squeeze.
    const float print_aspect=0.76f/(1.f-ps4.front_header);
    assert(near((square.right-square.left)*1.f,print_aspect));
    assert(near(square.left,1.f-square.right));
    assert(near(square.top,0.f)&&near(square.bottom,1.f));
    const auto portrait=niak_case_cover_crop(0.76f,print_aspect);
    assert(portrait.left>=0.f && portrait.right<=1.f);
    assert(portrait.top>=0.f && portrait.bottom<=1.f);
    const auto letterbox=niak_case_cover_crop(0.5f,1.f);
    assert(letterbox.top>0.f && letterbox.bottom<1.f);
    const auto invalid=niak_case_cover_crop(0.f,1.f);
    assert(near(invalid.left,0.f)&&near(invalid.right,1.f));
    return 0;
}
