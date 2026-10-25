#include "../avatar_dds.hpp"
#include <cassert>
#include <cstdint>
#include <vector>

static std::vector<uint8_t> avatar(const char fourcc,const int stride) {
 std::vector<uint8_t> data(128+stride*16,0);
 data[0]='D';data[1]='D';data[2]='S';data[3]=' ';
 data[4]=124;data[12]=16;data[16]=16;data[76]=32;
 data[84]='D';data[85]='X';data[86]='T';data[87]=uint8_t(fourcc);
 for(int i=0;i<16;++i) {
   auto *block=data.data()+128+i*stride;
   if(stride==16) {block[0]=255;block[1]=0;}
   block[stride==16?8:0]=0;
   block[stride==16?9:1]=0xf8; // color0 = red RGB565
 }
 return data;
}
int main() {
 int w=0,h=0;std::vector<uint8_t> rgba;
 auto bc3=avatar('5',16);
 assert(niak_decode_avatar_dds(bc3.data(),bc3.size(),w,h,rgba));
 assert(w==16&&h==16&&rgba.size()==1024);
 assert(rgba[0]==255&&rgba[1]==0&&rgba[2]==0&&rgba[3]==255);
 auto bc1=avatar('1',8);
 assert(niak_decode_avatar_dds(bc1.data(),bc1.size(),w,h,rgba));
 assert(w==16&&h==16&&rgba.size()==1024);
 assert(rgba[0]==255&&rgba[1]==0&&rgba[2]==0&&rgba[3]==255);
 // In BC1 3-colour mode, index 3 is transparent (unlike opaque BC3).
 for(int i=0;i<16;++i) {
   auto *block=bc1.data()+128+i*8;
   block[0]=0;block[1]=0;block[2]=0xff;block[3]=0xff;
   block[4]=0xff;block[5]=0xff;block[6]=0xff;block[7]=0xff;
 }
 assert(niak_decode_avatar_dds(bc1.data(),bc1.size(),w,h,rgba));
 assert(rgba[3]==0);
 assert(!niak_decode_avatar_dds(bc1.data(),bc1.size()-1,w,h,rgba));
 bc1[87]='9';
 assert(!niak_decode_avatar_dds(bc1.data(),bc1.size(),w,h,rgba));
}
