// SPDX-License-Identifier: GPL-3.0-or-later
// Optional pre-cached LaunchBox retail PS4/PS5 case print.
#include "niak/case_art.hpp"
#include "niak/lodepng.h"
#include "niak/case_texture_scale.hpp"
#include "niak/case_auto_art.hpp"
#include "niak/asset_stats.hpp"
extern "C" {
#include "niak/catalog.h"
}
#include "gfx/renderer.hpp"
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <vector>
#include <string>
std::uint32_t niak_load_case_art(hui::gfx::Renderer &renderer,
                                 const char *id,const char *side,float *aspect) {
 if(!niak_valid_title_id(id)||!side ||
    (std::strcmp(side,"front") && std::strcmp(side,"back") &&
     std::strcmp(side,"logo") && std::strcmp(side,"spine") &&
     std::strcmp(side,"poster") && std::strcmp(side,"hero") &&
     std::strcmp(side,"shot1") && std::strcmp(side,"shot2")))return 0;
 // Do not let a stale/corrupt private PNG shadow another valid source.
 std::vector<std::string> paths;
 char file[384];
#if defined(__linux__)
 if(const char *preview=std::getenv("NIAK_CASE_PREVIEW_ASSETS")) {
     if(preview[0]) {
         std::snprintf(file,sizeof(file),"%s/%s-%s.png",preview,id,side);
         paths.emplace_back(file);
     }
 }
#endif
 std::snprintf(file,sizeof(file),
     "/data/homebrew/PPSA99386/assets/niak-cases/%s-%s.png",id,side);
 paths.emplace_back(file);
 std::snprintf(file,sizeof(file),"/download0/niak-case-%s-%s.png",id,side);
 paths.emplace_back(file);
 std::snprintf(file,sizeof(file),"/app0/assets/niak-cases/%s-%s.png",id,side);
 paths.emplace_back(file);
 if(std::strcmp(side,"front")==0) {
     std::snprintf(file,sizeof(file),
         "/data/homebrew/%s/assets/box-front.png",id);
     paths.emplace_back(file);
 }
 const bool logo=std::strcmp(side,"logo")==0;
 const bool spine=std::strcmp(side,"spine")==0;
 const bool landscape=std::strcmp(side,"hero")==0 ||
                      std::strcmp(side,"shot1")==0 ||
                      std::strcmp(side,"shot2")==0;
 for(const std::string& filename:paths) {
     FILE *fp=std::fopen(filename.c_str(),"rb");
     if(!fp)continue;
     if(std::fseek(fp,0,SEEK_END)!=0){std::fclose(fp);continue;}
     const long size=std::ftell(fp);
     if(size<33||size>3*1024*1024||
        std::fseek(fp,0,SEEK_SET)!=0){std::fclose(fp);continue;}
     std::vector<unsigned char> png(static_cast<std::size_t>(size));
     const bool okay=std::fread(png.data(),1,png.size(),fp)==png.size();
     std::fclose(fp);if(!okay)continue;
     if(png.size()<24||
        std::memcmp(png.data(),"\x89PNG\r\n\x1a\n",8)!=0)continue;
     const unsigned width=(unsigned(png[16])<<24)|(unsigned(png[17])<<16)|
                          (unsigned(png[18])<<8)|png[19];
     const unsigned height=(unsigned(png[20])<<24)|(unsigned(png[21])<<16)|
                           (unsigned(png[22])<<8)|png[23];
     if(width<(logo?32u:spine?16u:64u)||
        height<(logo?20u:100u)||
        width>(logo?1400u:landscape?2048u:1024u)||
        height>1536u)continue;
     if(!logo) {
         const float ratio=float(width)/float(height);
         if(spine?ratio>0.25f:
            landscape?(ratio<1.15f||ratio>3.1f):
                      (ratio<0.55f||ratio>0.90f))continue;
     }
     std::vector<unsigned char> pixels;unsigned w=0,h=0;
     if(lodepng::decode(pixels,w,h,png)!=0||w!=width||h!=height||
        pixels.size()!=std::size_t(w)*h*4u)continue;
     if(!niak_scale_case_rgba(pixels,w,h,
         logo?768u:spine?96u:landscape?768u:512u,
         landscape?512u:768u))continue;
     const auto handle=renderer.create_texture(int(w),int(h),pixels.data());
     if(!handle)continue;
     if(aspect)*aspect=float(w)/float(h);
     niak::case_media_stats.case_texture_bytes+=std::uint64_t(w)*h*4u;
     if(filename.rfind("/download0/niak-case-",0)==0)
         niak_queue_auto_case_art(id,side);
     return handle;
 }
 // Missing or invalid artwork: enqueue a private download, not an icon copy.
 niak_queue_auto_case_art(id,side);
 return 0;
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
#if defined(__linux__)
 const auto fail=[&](const char *reason)->std::uint32_t{
     std::fprintf(stderr,"[NiakPS5 preview] fixed template %s-%s: %s [%s]\\n",
                  platform,part,reason,file);
     return 0;
 };
#else
 const auto fail=[&](const char *)->std::uint32_t{return 0;};
#endif
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
 if(!fp)return fail("not found"); // Optional on offline PS5, required in CI.
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
 // The standard GitHub OpenGL preview carries two *downscaled* copies
 // of the owner's real footer blocks (PS4 232x130, PS5 280x115).
 // They have the same artwork/aspect as the genuine larger originals.
 // Only the HOST preview may accept this lower resolution. Actual PS5
 // installations retain strict full-size footer validation.
#if defined(__linux__)
 const bool host_small_footer=side==1 && width>=180 && height>=90 &&
                              width<=1600 && height<=900 &&
                              float(width)/float(height)>=1.5f &&
                              float(width)/float(height)<=2.8f;
#else
 const bool host_small_footer=false;
#endif
 const bool valid=side==2?(width>=40 && width<=200 && height>=350 && height<=1600):
                  side==0?(width>=450 && width<=2000 && height>=60 && height<=400):
                          ((width>=450 && width<=1600 &&
                            height>=220 && height<=900) || host_small_footer);
 if(!valid || std::size_t(width)*height>2500000u) {
#if defined(__linux__)
     std::fprintf(stderr,
       "[NiakPS5 preview] %s-%s invalid template geometry %ux%u\\n",
       platform,part,width,height);
#endif
     return fail("invalid dimensions");
 }
 std::vector<unsigned char> pixels;
 unsigned w=0,h=0;
 const unsigned decode_error=lodepng::decode(pixels,w,h,bytes);
 if(decode_error || w!=width || h!=height ||
    pixels.size()!=std::size_t(w)*h*4) {
#if defined(__linux__)
    std::fprintf(stderr,
        "[NiakPS5 preview] decode %s-%s error=%u expected=%ux%u decoded=%ux%u\\n",
        platform,part,decode_error,width,height,w,h);
#endif
    return fail("PNG decoding failed");
 }
 // An invariant footer must be a TRANSPARENT overlay above the single
 // continuous paper. The bundled opaque example-game footers carry another
 // game's details and must never look like a separate pasted rectangle.
 if(side==1) {
     std::size_t clear=0;
     for(std::size_t i=3;i<pixels.size();i+=4)
         clear+=pixels[i]<=16;
     if(clear*20 < std::size_t(w)*h)
         return fail("opaque sample footer rejected; background remains seamless");
 }
 // Shared mastheads/footers also avoid needless original-size GPU textures.
 if(!niak_scale_case_rgba(pixels,w,h,side==2?96u:1024u,
                          side==2?768u:512u))return fail("resampling failed");
 template_textures[index]=renderer.create_texture(int(w),int(h),pixels.data());
 if(template_textures[index])
     niak::case_media_stats.case_texture_bytes+=std::uint64_t(w)*h*4u;
 else
     return fail("GPU texture allocation failed");
 return template_textures[index];
}
