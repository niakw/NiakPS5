// SPDX-License-Identifier: GPL-3.0-or-later
// Optional pre-cached LaunchBox retail PS4/PS5 case print.
#include "niak/case_art.hpp"
#include "niak/lodepng.h"
extern "C" {
#include "niak/catalog.h"
}
#include "gfx/renderer.hpp"
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <vector>
std::uint32_t niak_load_case_art(hui::gfx::Renderer &renderer,const char *id,const char *side){
 if(!niak_valid_title_id(id)||!side ||
    (std::strcmp(side,"front") && std::strcmp(side,"back") &&
     std::strcmp(side,"logo") && std::strcmp(side,"spine")))return 0;
 char file[384];
 // Linux CI loads explicit non-commercial QA art. Never shipped in PS5 ZIP.
 // The native PS5 title always loads the locally installed private scans.
#if defined(__linux__)
 const char *preview=std::getenv("NIAK_CASE_PREVIEW_ASSETS");
 if(preview && preview[0])
     std::snprintf(file,sizeof(file),"%s/%s-%s.png",preview,id,side);
 else
#endif
     std::snprintf(file,sizeof(file),"/app0/assets/niak-cases/%s-%s.png",id,side);
 FILE *fp=std::fopen(file,"rb");if(!fp)return 0;
 if(std::fseek(fp,0,SEEK_END)!=0){std::fclose(fp);return 0;}
 const long bytes=std::ftell(fp);
 if(bytes<33||bytes>3*1024*1024||std::fseek(fp,0,SEEK_SET)!=0)
 {std::fclose(fp);return 0;}
 std::vector<unsigned char> png(static_cast<std::size_t>(bytes));
 const bool okay=std::fread(png.data(),1,png.size(),fp)==png.size();
 std::fclose(fp);if(!okay)return 0;
 if(png.size()<24||png[0]!=137||png[1]!=80||png[2]!=78||png[3]!=71)return 0;
 const unsigned width=(unsigned(png[16])<<24)|(unsigned(png[17])<<16)|
                      (unsigned(png[18])<<8)|png[19];
 const unsigned height=(unsigned(png[20])<<24)|(unsigned(png[21])<<16)|
                       (unsigned(png[22])<<8)|png[23];
 const bool logo=std::strcmp(side,"logo")==0;
 const bool spine=std::strcmp(side,"spine")==0;
 if(width<(logo?32u:spine?16u:64u)||height<(logo?20u:100u)||
    width>(logo?1400u:1024u)||height>1536u)return 0;
 std::vector<unsigned char> pixels;unsigned w=0,h=0;
 if(lodepng::decode(pixels,w,h,png)!=0||w!=width||h!=height||
    pixels.size()!=std::size_t(w)*h*4)return 0;
 return renderer.create_texture(int(w),int(h),pixels.data());
}
