// SPDX-License-Identifier: GPL-3.0-or-later
// Optional pre-cached LaunchBox retail PS4/PS5 case print.
#include "niak/case_art.hpp"
#include "niak/lodepng.h"
#include "niak/case_texture_scale.hpp"
#include "niak/asset_stats.hpp"
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
     std::snprintf(file,sizeof(file),
         "/data/homebrew/PPSA99386/assets/niak-cases/%s-%s.png",id,side);
 FILE *fp=std::fopen(file,"rb");
 // Prefer recent private scans; only fall back to the original app package
 // if the owner has not refreshed this title via FTP.
 if(!fp) {
    std::snprintf(file,sizeof(file),"/app0/assets/niak-cases/%s-%s.png",id,side);
    fp=std::fopen(file,"rb");
 }
 if(!fp && std::strcmp(side,"front")==0) {
    // Homebrew game authors sometimes package their own portrait cover.
    // Use it only if it later passes the strict PNG geometry checks below.
    std::snprintf(file,sizeof(file),
        "/data/homebrew/%s/assets/box-front.png",id);
    fp=std::fopen(file,"rb");
 }
 if(!fp)return 0;
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
 if(!logo) {
    const float aspect=float(width)/float(height);
    if(spine ? aspect>0.25f : (aspect<0.55f || aspect>0.90f))
        return 0;  // Never stretch square app icons or landscape backdrops.
 }
 std::vector<unsigned char> pixels;unsigned w=0,h=0;
 if(lodepng::decode(pixels,w,h,png)!=0||w!=width||h!=height||
    pixels.size()!=std::size_t(w)*h*4)return 0;
 // A 1024x1536 source was consuming 6 MiB of permanent VRAM per cover.
 // Projected sleeves never use that resolution: keep 512x768 at most.
 const unsigned max_w=logo?768u:spine?96u:512u;
 const unsigned max_h=logo?768u:768u;
 if(!niak_scale_case_rgba(pixels,w,h,max_w,max_h))return 0;
 const auto handle=renderer.create_texture(int(w),int(h),pixels.data());
 if(handle)niak::case_media_stats.case_texture_bytes+=std::uint64_t(w)*h*4u;
 return handle;
}

namespace {
bool template_attempted[6]={};
std::uint32_t template_textures[6]={};
}
void niak_release_case_templates(hui::gfx::Renderer &renderer) {
 for(int i=0;i<6;++i) {
  if(template_textures[i])renderer.destroy_texture(template_textures[i]);
  template_textures[i]=0;
  template_attempted[i]=false;
 }
}
std::uint32_t niak_load_case_template(hui::gfx::Renderer &renderer,
                                      const char *platform,const char *part) {
 // Exactly six static, user-supplied files. Never form untrusted paths.
 const char *platforms[]={"ps4","ps5"};
 const char *parts[]={"front","back","spine"};
 int generation=-1,side=-1;
 for(int i=0;i<2;++i)
     if(platform && std::strcmp(platform,platforms[i])==0)generation=i;
 for(int i=0;i<3;++i)
     if(part && std::strcmp(part,parts[i])==0)side=i;
 if(generation<0||side<0)return 0;
 const int index=generation*3+side;
 if(template_attempted[index])return template_textures[index];
 template_attempted[index]=true;
 char file[512]{};
 FILE *fp=nullptr;
#if defined(__linux__)
 const char *fixture=std::getenv("NIAK_CASE_TEMPLATE_ASSETS");
 if(fixture && fixture[0]) {
     std::snprintf(file,sizeof(file),"%s/%s-%s.png",fixture,platform,part);
     fp=std::fopen(file,"rb");
 }
#endif
 if(!fp) {
     std::snprintf(file,sizeof(file),
        "/data/homebrew/PPSA99386/assets/niak-templates/%s-%s.png",platform,part);
     fp=std::fopen(file,"rb");
 }
 if(!fp) {
     std::snprintf(file,sizeof(file),
        "/app0/assets/niak-templates/%s-%s.png",platform,part);
     fp=std::fopen(file,"rb");
 }
 if(!fp)return 0; // Offline installations still use the procedural fallback.
 if(std::fseek(fp,0,SEEK_END)!=0){std::fclose(fp);return 0;}
 const long size=std::ftell(fp);
 if(size<33 || size>3*1024*1024 || std::fseek(fp,0,SEEK_SET)!=0)
     {std::fclose(fp);return 0;}
 std::vector<unsigned char> bytes(static_cast<std::size_t>(size));
 const bool complete=std::fread(bytes.data(),1,bytes.size(),fp)==bytes.size();
 std::fclose(fp);if(!complete)return 0;
 if(bytes.size()<24||std::memcmp(bytes.data(),"\x89PNG\r\n\x1a\n",8)!=0)return 0;
 const unsigned width=(unsigned(bytes[16])<<24)|(unsigned(bytes[17])<<16)|
                      (unsigned(bytes[18])<<8)|bytes[19];
 const unsigned height=(unsigned(bytes[20])<<24)|(unsigned(bytes[21])<<16)|
                       (unsigned(bytes[22])<<8)|bytes[23];
 // Wide brand header/back legal strip or narrow tall spine; do not decode
 // accidentally swapped art, malicious PNG dimensions or an icon.
 const bool valid=side==2?(width>=40 && width<=200 && height>=350 && height<=1600):
                  side==0?(width>=450 && width<=2000 && height>=60 && height<=400):
                          (width>=450 && width<=1600 && height>=220 && height<=900);
 if(!valid || std::size_t(width)*height>2500000u)return 0;
 std::vector<unsigned char> pixels;
 unsigned w=0,h=0;
 if(lodepng::decode(pixels,w,h,bytes)!=0||w!=width||h!=height||
    pixels.size()!=std::size_t(w)*h*4)return 0;
 // Shared mastheads/footers also avoid needless original-size GPU textures.
 if(!niak_scale_case_rgba(pixels,w,h,side==2?96u:1024u,
                          side==2?768u:512u))return 0;
 template_textures[index]=renderer.create_texture(int(w),int(h),pixels.data());
 if(template_textures[index])
     niak::case_media_stats.case_texture_bytes+=std::uint64_t(w)*h*4u;
 return template_textures[index];
}
