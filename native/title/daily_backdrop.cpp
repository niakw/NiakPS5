// SPDX-License-Identifier: GPL-3.0-or-later
// Daily PlayStation 5 backgrounds from locally packaged optimized PNGs.
#include "niak/daily_backdrop.hpp"
#include "niak/lodepng.h"
#include "gfx/renderer.hpp"
#include "platform/ps5/system.hpp"
#include <array>
#include <cstdint>
#include <cstdio>
#include <ctime>
#include <vector>

namespace {
std::array<std::uint32_t,14> images{};
int count=0;
bool load_png(const char *path, int &width, int &height,
              std::vector<unsigned char> &rgba) {
    FILE *f=std::fopen(path,"rb");
    if(!f)return false;
    if(std::fseek(f,0,SEEK_END)!=0){std::fclose(f);return false;}
    long bytes=std::ftell(f);
    if(bytes<32||bytes>4*1024*1024||std::fseek(f,0,SEEK_SET)!=0)
    {std::fclose(f);return false;}
    std::vector<unsigned char> png(static_cast<std::size_t>(bytes));
    bool ok=std::fread(png.data(),1,png.size(),f)==png.size();
    std::fclose(f);
    if(!ok)return false;
    // Guard decompression bombs before asking the PNG decoder to allocate.
    if(png.size()<24||png[0]!=137||png[1]!=80||png[2]!=78||png[3]!=71)
        return false;
    unsigned w=(unsigned(png[16])<<24)|(unsigned(png[17])<<16)|
               (unsigned(png[18])<<8)|png[19];
    unsigned h=(unsigned(png[20])<<24)|(unsigned(png[21])<<16)|
               (unsigned(png[22])<<8)|png[23];
    if(w!=1280||h!=720)return false;
    unsigned decoded_w=0,decoded_h=0;
    if(lodepng::decode(rgba,decoded_w,decoded_h,png)!=0 ||
       decoded_w!=w||decoded_h!=h||
       rgba.size()!=std::size_t(w)*h*4)return false;
    width=int(w);height=int(h);return true;
}
}
void niak_load_daily_backdrops(hui::gfx::Renderer &renderer,const char *directory) {
    if(!directory) return;
    for(int i=0;i<14;++i) {
        char path[384];
        const int length=std::snprintf(path,sizeof(path),"%s/wall-%02d.png",directory,i);
        if(length<=0||length>=int(sizeof(path)))continue;
        int w=0,h=0;
        std::vector<unsigned char> rgba;
        if(!load_png(path,w,h,rgba))continue; // tolerate missing corrupt members
        auto texture=renderer.create_texture(w,h,rgba.data());
        if(!texture)continue;
        images[static_cast<std::size_t>(count++)]=texture;
    }
    hui::sys::log("[NiakPS5] PS5 wallpaper pool: %d media textures",count);
}
std::uint32_t niak_daily_backdrop() {
    if(count==0)return 0;
    const auto t=std::time(nullptr);
    const std::tm *date=std::localtime(&t);
    if(!date)return images[0];
    // One image for the user's entire local calendar day.
    const int serial=(date->tm_year+1900)*372+date->tm_mon*31+date->tm_mday;
    return images[static_cast<std::size_t>((serial%count+count)%count)];
}
