#include "../avatar_dds.hpp"
#include <cassert>
#include <cstdint>
#include <vector>
int main(){
 std::vector<uint8_t> data(128+16*16,0);
 data[0]='D';data[1]='D';data[2]='S';data[3]=' ';
 data[4]=124;data[12]=16;data[16]=16;data[76]=32;
 data[84]='D';data[85]='X';data[86]='T';data[87]='5';
 for(int i=0;i<16;++i){
   data[128+i*16]=255;
   data[128+i*16+1]=0;
   data[128+i*16+8]=0;
   data[128+i*16+9]=0xf8; // red RGB565
 }
 int w=0,h=0;std::vector<uint8_t> rgba;
 assert(niak_decode_avatar_dds(data.data(),data.size(),w,h,rgba));
 assert(w==16&&h==16&&rgba.size()==1024);
 assert(rgba[0]==255&&rgba[1]==0&&rgba[2]==0&&rgba[3]==255);
 data[84]='X';
 assert(!niak_decode_avatar_dds(data.data(),data.size(),w,h,rgba));
};
