// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
#include <initializer_list>
// Back-media selection has no rendering side effects. An absent second
// image remains ABSENT; callers must use a single full-width image or opaque
// paper, never repeat the hero/artwork to fill a second slot.
struct NiakBackArt {
    std::uint32_t texture=0;
    float aspect=1.f;
};
struct NiakBackSelection {
    NiakBackArt first{};
    NiakBackArt second{};
};
inline NiakBackSelection niak_select_back_media(
    std::initializer_list<NiakBackArt> candidates) {
    NiakBackSelection result{};
    for(const auto candidate:candidates) {
        if(!candidate.texture || !(candidate.aspect>0.f))continue;
        if(!result.first.texture) {
            result.first=candidate;
        } else if(candidate.texture!=result.first.texture) {
            result.second=candidate;
            break;
        }
    }
    return result;
}
