#include "../case_footer_alpha.hpp"
#include <cassert>
#include <vector>
int main() {
  const unsigned w=100,h=100;
  std::vector<unsigned char> ps5(std::size_t(w)*h*4u,255);
  for(unsigned i=0;i<100;++i) {
    const std::size_t p=std::size_t(i)*4u;
    ps5[p]=22;ps5[p+1]=55;ps5[p+2]=112;
  }
  assert(niak_footer_paper_to_alpha(ps5,w,h,false));
  assert(ps5[3]==255 && ps5[std::size_t(500)*4u+3]==0);
  std::vector<unsigned char> ps4(std::size_t(w)*h*4u);
  for(std::size_t i=0;i<ps4.size();i+=4)
    {ps4[i]=24;ps4[i+1]=27;ps4[i+2]=24;ps4[i+3]=255;}
  for(unsigned i=0;i<100;++i) {
    const auto p=std::size_t(i)*4u;
    ps4[p]=220;ps4[p+1]=210;ps4[p+2]=185;
  }
  assert(niak_footer_paper_to_alpha(ps4,w,h,true));
  assert(ps4[3]==255 && ps4[std::size_t(500)*4u+3]==0);
  std::vector<unsigned char> overlay=ps4;
  overlay[3]=100;
  assert(niak_footer_paper_to_alpha(overlay,w,h,true));
  assert(overlay[3]==100);
  assert(!niak_footer_paper_to_alpha(overlay,w+1,h,true));
  return 0;
}
