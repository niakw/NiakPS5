// SPDX-License-Identifier: GPL-3.0-or-later
// Small, offline DXT5 (BC3) decoder for PS5 profile avatar DDS files.
#include "avatar_dds.hpp"
#include <cstddef>
#include <cstdint>
#include <vector>
namespace {
uint32_t le32(const uint8_t *p) {
  return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);
}
uint16_t le16(const uint8_t *p) {return uint16_t(p[0])|(uint16_t(p[1])<<8);}
void rgb565(uint16_t v,uint8_t *out) {
  const int r=(v>>11)&31,g=(v>>5)&63,b=v&31;
  out[0]=uint8_t((r*255+15)/31);
  out[1]=uint8_t((g*255+31)/63);
  out[2]=uint8_t((b*255+15)/31);
}
}
bool niak_decode_avatar_dds(const uint8_t *data,std::size_t size,
                            int &w,int &h,std::vector<uint8_t> &pixels) {
 w=h=0;pixels.clear();
 // DDS magic, standard 124-byte header, standard 32-byte pixel-format,
 // FOURCC "DXT5" (BC3); reject unrecognized layouts.
 if(!data||size<144||le32(data)!=0x20534444u||le32(data+4)!=124||
    le32(data+76)!=32||le32(data+84)!=0x35545844u)return false;
 uint32_t width=le32(data+16),height=le32(data+12);
 if(width<16||height<16||width>512||height>512)return false;
 std::size_t cols=(width+3)/4,rows=(height+3)/4;
 if(cols*rows>(size-128)/16)return false;
 pixels.resize(std::size_t(width)*height*4);
 const uint8_t *ptr=data+128;
 for(std::size_t row=0;row<rows;++row)for(std::size_t col=0;col<cols;++col){
   uint8_t alphas[8]={ptr[0],ptr[1]};
   if(alphas[0]>alphas[1])for(int i=1;i<=6;++i)
     alphas[i+1]=uint8_t(((7-i)*int(alphas[0])+i*int(alphas[1]))/7);
   else{
     for(int i=1;i<=4;++i)
       alphas[i+1]=uint8_t(((5-i)*int(alphas[0])+i*int(alphas[1]))/5);
     alphas[6]=0;alphas[7]=255;
   }
   uint64_t alpha_bits=0;
   for(int j=0;j<6;++j)alpha_bits|=uint64_t(ptr[2+j])<<(j*8);
   uint8_t colors[4][3]{};
   rgb565(le16(ptr+8),colors[0]);rgb565(le16(ptr+10),colors[1]);
   for(int j=0;j<3;++j){
     colors[2][j]=uint8_t((2*int(colors[0][j])+int(colors[1][j]))/3);
     colors[3][j]=uint8_t((int(colors[0][j])+2*int(colors[1][j]))/3);
   }
   const uint32_t rgb_bits=le32(ptr+12);
   for(int i=0;i<16;++i){
     const unsigned x=unsigned(col*4+i%4),y=unsigned(row*4+i/4);
     if(x>=width||y>=height)continue;
     const auto off=(std::size_t(y)*width+x)*4;
     const unsigned a=unsigned((alpha_bits>>(3*i))&7u);
     const unsigned color=(rgb_bits>>(2*i))&3u;
     for(int ch=0;ch<3;++ch)pixels[off+ch]=colors[color][ch];
     pixels[off+3]=alphas[a];
   }
   ptr+=16;
 }
 w=int(width);h=int(height);
 return true;
}
