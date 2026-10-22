#include "../case_texture_scale.hpp"
#include <cassert>
#include <vector>
int main() {
    unsigned w=1024,h=1536;
    std::vector<unsigned char> image(std::size_t(w)*h*4u,0);
    for(std::size_t i=0;i<image.size();i+=4) {
        image[i]=130;image[i+1]=90;image[i+2]=25;image[i+3]=255;
    }
    assert(niak_scale_case_rgba(image,w,h,512,768));
    assert(w==512&&h==768&&image.size()==std::size_t(w)*h*4u);
    for(std::size_t i=0;i<image.size();i+=4) {
        assert(image[i]==130&&image[i+1]==90&&image[i+2]==25&&image[i+3]==255);
    }
    const auto original=image;
    assert(niak_scale_case_rgba(image,w,h,512,768));
    assert(image==original); // no repeated compression of an existing texture
    unsigned spine_w=200,spine_h=1400;
    std::vector<unsigned char> spine(std::size_t(spine_w)*spine_h*4u,180);
    assert(niak_scale_case_rgba(spine,spine_w,spine_h,96,768));
    assert(spine_w<=96&&spine_h<=768);
    assert(spine_w==96&&spine_h==672); // original 1:7 aspect preserved
    unsigned bad_w=0,bad_h=768;
    std::vector<unsigned char> bad;
    assert(!niak_scale_case_rgba(bad,bad_w,bad_h,512,768));
    return 0;
}
