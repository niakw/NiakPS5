// SPDX-License-Identifier: GPL-3.0-or-later
// Small offline BC1/DXT1 and BC3/DXT5 decoders for PS5 profile DDS icons.
#include "avatar_dds.hpp"
#include <cstddef>
#include <cstdint>
#include <vector>
namespace {
uint32_t le32(const uint8_t *p) {
 return uint32_t(p[0])|(uint32_t(p[1])<<8)|
        (uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);
}
uint16_t le16(const uint8_t *p) {
 return uint16_t(p[0])|(uint16_t(p[1])<<8);
}
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
 // Only standard DDS with FOURCC DXT1 (BC1) or DXT5 (BC3).
 // Refuse DX10 headers, cubemaps or unknown pixel formats.
 if(!data||size<128||le32(data)!=0x20534444u||
    le32(data+4)!=124u||le32(data+76)!=32u)return false;
 const uint32_t format=le32(data+84);
 const bool bc1=format==0x31545844u,bc3=format==0x35545844u;
 if(!bc1&&!bc3)return false;
 const uint32_t width=le32(data+16),height=le32(data+12);
 if(width<16||height<16||width>512||height>512)return false;
 const std::size_t cols=(width+3u)/4u,rows=(height+3u)/4u;
 const std::size_t stride=bc1?8u:16u;
 if(cols*rows>(size-128u)/stride)return false;
 pixels.resize(std::size_t(width)*height*4u);
 const uint8_t *ptr=data+128;
 for(std::size_t row=0;row<rows;++row)for(std::size_t col=0;col<cols;++col) {
  uint8_t alphas[8]{};
  uint64_t alpha_bits=0;
  if(bc3) {
   alphas[0]=ptr[0];alphas[1]=ptr[1];
   if(alphas[0]>alphas[1]) {
    for(int i=1;i<=6;++i)
      alphas[i+1]=uint8_t(((7-i)*int(alphas[0])+i*int(alphas[1]))/7);
   } else {
    for(int i=1;i<=4;++i)
      alphas[i+1]=uint8_t(((5-i)*int(alphas[0])+i*int(alphas[1]))/5);
    alphas[6]=0;alphas[7]=255;
   }
   for(int j=0;j<6;++j)alpha_bits|=uint64_t(ptr[2+j])<<(j*8);
  }
  const uint8_t *color_block=ptr+(bc3?8u:0u);
  const uint16_t color0=le16(color_block),color1=le16(color_block+2);
  uint8_t colors[4][3]{};
  rgb565(color0,colors[0]);rgb565(color1,colors[1]);
  if(bc1 && color0<=color1) {
   for(int j=0;j<3;++j)
    colors[2][j]=uint8_t((int(colors[0][j])+int(colors[1][j]))/2);
   // BC1 index 3 is transparent when color0 <= color1.
  } else {
   for(int j=0;j<3;++j) {
    colors[2][j]=uint8_t((2*int(colors[0][j])+int(colors[1][j]))/3);
    colors[3][j]=uint8_t((int(colors[0][j])+2*int(colors[1][j]))/3);
   }
  }
  const uint32_t rgb_bits=le32(color_block+4);
  for(int i=0;i<16;++i) {
   const unsigned x=unsigned(col*4+i%4),y=unsigned(row*4+i/4);
   if(x>=width||y>=height)continue;
   const auto off=(std::size_t(y)*width+x)*4u;
   const unsigned color=(rgb_bits>>(2*i))&3u;
   for(int ch=0;ch<3;++ch)pixels[off+ch]=colors[color][ch];
   pixels[off+3]=bc3?
       alphas[(alpha_bits>>(3*i))&7u] :
       uint8_t(bc1&&color0<=color1&&color==3u ? 0u:255u);
  }
  ptr+=stride;
 }
 w=int(width);h=int(height);
 return true;
}
