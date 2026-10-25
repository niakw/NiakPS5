// SPDX-License-Identifier: GPL-3.0-or-later
// Optional pre-cached LaunchBox retail PS4/PS5 case print.
#include "niak/case_art.hpp"
#include "niak/lodepng.h"
#if defined(__PROSPERO__)
#include <webp/decode.h>
#endif
#include "niak/case_texture_scale.hpp"
#include "niak/case_auto_art.hpp"
#include "niak/case_footer_alpha.hpp"
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
#include <unordered_map>
#include <utility>
#if defined(__PROSPERO__)
#include <condition_variable>
#include <deque>
#include <mutex>
#include <thread>
#include <unordered_set>
#endif
namespace {
// Texture creation and release always run on the graphics thread.
std::unordered_map<std::uint32_t,std::uint64_t> tracked_case_textures;
void track_case_texture(std::uint32_t texture,unsigned w,unsigned h){
 if(!texture)return;
 const auto bytes=std::uint64_t(w)*h*4u;
 tracked_case_textures[texture]=bytes;
 niak::case_media_stats.case_texture_bytes+=bytes;
}
// Private CDN PNGs are valid only after their .source marker is committed.
// Earlier interrupted writes must never displace the fallback box art.
bool valid_download_source(const std::string &image_path) {
 const std::string marker=image_path+".source";
 FILE *f=std::fopen(marker.c_str(),"rb");
 if(!f)return false;
 char name[64]{};
 const std::size_t length=std::fread(name,1,sizeof(name),f);
 const bool ended=std::feof(f)!=0;
 std::fclose(f);
 if(!ended)return false;
 const bool r2=length>=3 && std::memcmp(name,"r2_",3)==0;
 const std::size_t offset=r2?3u:0u;
 if(length!=offset+40u && length!=offset+41u)return false;
 for(std::size_t i=offset;i<offset+36;i++){
   const char c=name[i];
   if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')||
        (c>='A'&&c<='F')||c=='-'))return false;
 }
 const std::string ext(name+offset+36,length-offset-36);
 return ext==".jpg"||ext==".jpeg"||ext==".png";
}
} // namespace
void niak_track_case_texture(std::uint32_t texture,unsigned width,unsigned height){
 track_case_texture(texture,width,height);
}
static bool niak_prepare_case_pixels(
        const char *id,const char *side,
        std::vector<unsigned char> &prepared,unsigned &out_w,unsigned &out_h) {
 if(!niak_valid_title_id(id)||!side ||
    (std::strcmp(side,"front") && std::strcmp(side,"back") &&
     std::strcmp(side,"logo") && std::strcmp(side,"spine") &&
     std::strcmp(side,"poster") && std::strcmp(side,"hero") &&
     std::strcmp(side,"shot1") && std::strcmp(side,"shot2")))return false;
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
 // Native CDN WebP cache takes precedence over old PNG, if provenance is valid.
 // The private fallback wins only while its exact .source provenance
 // marker exists. A successful /download0 update clears that old marker.
 // If /download0 is read-only, it may retain an unremovable old marker:
 // placing the newer private image first prevents that obsolete cache
 // from hiding the freshly downloaded cover.
 std::snprintf(file,sizeof(file),
     "/data/homebrew/PPSA99386/assets/niak-cdn-case-%s-%s.webp",id,side);
 paths.emplace_back(file);
 std::snprintf(file,sizeof(file),"/download0/niak-case-%s-%s.webp",id,side);
 paths.emplace_back(file);
 // A verified CDN replacement takes priority over older FTP artwork.
 // Without this ordering a downloaded PS5 back could stay invisible behind
 // the previously installed PS4/PC fallback after a successful upgrade.
 std::snprintf(file,sizeof(file),"/download0/niak-case-%s-%s.png",id,side);
 paths.emplace_back(file);
 // Prefer WebP FTP art when present; retain PNG for older installations.
 for(const char *format:{
     "/data/homebrew/PPSA99386/assets/niak-cases/%s-%s.webp",
     "/app0/assets/niak-cases/%s-%s.webp",
     "/data/homebrew/PPSA99386/assets/niak-cases/%s-%s.png",
     "/app0/assets/niak-cases/%s-%s.png"}) {
     std::snprintf(file,sizeof(file),format,id,side);
     paths.emplace_back(file);
 }
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
     // The FTP override and packaged scans have independent provenance.
     // Only worker-generated PNGs require the atomic .source sidecar.
     if((filename.rfind("/download0/niak-case-",0)==0 ||
         filename.rfind("/data/homebrew/PPSA99386/assets/niak-cdn-case-",0)==0) &&
        !valid_download_source(filename))continue;
     FILE *fp=std::fopen(filename.c_str(),"rb");
     if(!fp)continue;
     if(std::fseek(fp,0,SEEK_END)!=0){std::fclose(fp);continue;}
     const long size=std::ftell(fp);
     if(size<33||size>3*1024*1024||
        std::fseek(fp,0,SEEK_SET)!=0){std::fclose(fp);continue;}
     std::vector<unsigned char> png(static_cast<std::size_t>(size));
     const bool okay=std::fread(png.data(),1,png.size(),fp)==png.size();
     std::fclose(fp);if(!okay)continue;
     if(png.size()<24)continue;
     const bool webp=std::memcmp(png.data(),"RIFF",4)==0 &&
                     std::memcmp(png.data()+8,"WEBP",4)==0;
     unsigned width=0,height=0;
     if(webp) {
#if defined(__PROSPERO__)
         int iw=0,ih=0;
         if(!WebPGetInfo(png.data(),png.size(),&iw,&ih) ||
            iw<=0||ih<=0)continue;
         width=unsigned(iw);height=unsigned(ih);
#else
         continue; // Host preview retains PNG-only fixtures.
#endif
     } else {
         if(std::memcmp(png.data(),"\x89PNG\r\n\x1a\n",8)!=0)continue;
         width=(unsigned(png[16])<<24)|(unsigned(png[17])<<16)|
               (unsigned(png[18])<<8)|png[19];
         height=(unsigned(png[20])<<24)|(unsigned(png[21])<<16)|
                (unsigned(png[22])<<8)|png[23];
     }
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
     std::vector<unsigned char> pixels;unsigned w=width,h=height;
     if(webp) {
#if defined(__PROSPERO__)
         pixels.resize(std::size_t(w)*h*4u);
         if(!WebPDecodeRGBAInto(png.data(),png.size(),pixels.data(),
                                pixels.size(),int(w*4u)))continue;
#else
         continue;
#endif
     } else if(lodepng::decode(pixels,w,h,png)!=0||
               w!=width||h!=height||
               pixels.size()!=std::size_t(w)*h*4u)continue;
     if(!niak_scale_case_rgba(pixels,w,h,
         logo?768u:spine?96u:landscape?768u:512u,
         landscape?512u:768u))continue;
     out_w=w;out_h=h;
     prepared=std::move(pixels);
     return true;
 }
 // Pure CPU helper. Work is queued separately on PS5 and previews load
 // read-only fixtures synchronously on the host.
 return false;
}

#if defined(__PROSPERO__)
// Latest-selected-title worker. This owns no GPU handles or catalogue items;
// only one resized RGBA image is retained until the graphics thread polls it.
struct PreparedCaseArt {
    std::mutex mutex;
    std::condition_variable wake;
    std::deque<std::string> queued_sides;
    std::unordered_set<std::string> in_flight;
    std::string selected_id;
    std::uint64_t generation=0;
    bool started=false,completed=false;
    std::string completed_id,completed_side;
    std::vector<unsigned char> completed_pixels;
    unsigned completed_width=0,completed_height=0;
};
static PreparedCaseArt &prepared_case_state() {
    static auto *state=new PreparedCaseArt;
    return *state;
}
static void prepared_case_worker() {
    auto &state=prepared_case_state();
    for(;;) {
        std::string id,side;
        std::uint64_t generation=0;
        {
            std::unique_lock<std::mutex> lock(state.mutex);
            state.wake.wait(lock,[&] {
                return !state.completed && !state.queued_sides.empty();
            });
            id=state.selected_id;
            generation=state.generation;
            side=std::move(state.queued_sides.front());
            state.queued_sides.pop_front();
        }
        std::vector<unsigned char> pixels;
        unsigned width=0,height=0;
        const bool ready=niak_prepare_case_pixels(
            id.c_str(),side.c_str(),pixels,width,height);
        {
            std::lock_guard<std::mutex> lock(state.mutex);
            // A different game was selected while a large scan decoded.
            // Its decoded bytes must never be uploaded to an old GPU owner.
            if(generation!=state.generation || id!=state.selected_id)
                continue;
            if(!ready) {
                state.in_flight.erase(side);
                continue;
            }
            state.completed_id=std::move(id);
            state.completed_side=std::move(side);
            state.completed_width=width;
            state.completed_height=height;
            state.completed_pixels=std::move(pixels);
            state.completed=true;
        }
    }
}
static void queue_prepared_case_art(const char *id,const char *side) {
    auto &state=prepared_case_state();
    std::lock_guard<std::mutex> lock(state.mutex);
    if(state.selected_id!=id) {
        state.selected_id=id;
        ++state.generation;
        state.queued_sides.clear();
        state.in_flight.clear();
        state.completed=false;
        state.completed_pixels.clear();
        state.completed_id.clear();
        state.completed_side.clear();
    }
    // At most eight distinct face requests per game.
    if(state.in_flight.size()>=8 || !state.in_flight.emplace(side).second)
        return;
    state.queued_sides.emplace_back(side);
    if(!state.started) {
        state.started=true;
        std::thread([] {prepared_case_worker();}).detach();
    }
    state.wake.notify_one();
}
#endif

void niak_select_prepared_case_focus(const char *id) {
#if defined(__PROSPERO__)
    // Never keep a pending decoded face belonging to a previous focus.
    // This is CPU-only: no file I/O, GPU operation or network call.
    const char *next=niak_valid_title_id(id)?id:"";
    auto &state=prepared_case_state();
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        if(state.selected_id==next)return;
        state.selected_id=next;
        ++state.generation;
        state.queued_sides.clear();
        state.in_flight.clear();
        state.completed=false;
        state.completed_id.clear();
        state.completed_side.clear();
        state.completed_pixels.clear();
    }
    state.wake.notify_one();
#else
    (void)id;
#endif
}

void niak_invalidate_prepared_case_art(const char *id) {
#if defined(__PROSPERO__)
    if(!id)return;
    auto &state=prepared_case_state();
    std::lock_guard<std::mutex> lock(state.mutex);
    if(state.selected_id!=id)return;
    // CDN completed a NEW face while an older copy was queued, decoded or
    // waiting for upload. Invalidate all old-generation pixels and restart
    // the 11-stage hydration against the current atomic cache.
    ++state.generation;
    state.queued_sides.clear();
    state.in_flight.clear();
    state.completed=false;
    state.completed_pixels.clear();
    state.completed_id.clear();
    state.completed_side.clear();
    state.wake.notify_one();
#else
    (void)id;
#endif
}
std::uint32_t niak_load_case_art(hui::gfx::Renderer &renderer,
                                 const char *id,const char *side,float *aspect) {
#if defined(__PROSPERO__)
    // Preserve the established 11-stage prioritization but no filesystem
    // reads, PNG/WebP decompression or CPU scaling on the GL thread.
    if(!niak_valid_title_id(id)||!side ||
       (std::strcmp(side,"front") && std::strcmp(side,"back") &&
        std::strcmp(side,"spine") && std::strcmp(side,"logo") &&
        std::strcmp(side,"poster") && std::strcmp(side,"hero") &&
        std::strcmp(side,"shot1") && std::strcmp(side,"shot2")))return 0;
    queue_prepared_case_art(id,side);
    (void)renderer;(void)aspect;
    return 0;
#else
    // Original host preview remains eager and deterministic.
    std::vector<unsigned char> pixels;
    unsigned w=0,h=0;
    if(!niak_prepare_case_pixels(id,side,pixels,w,h))return 0;
    const auto handle=renderer.create_texture(int(w),int(h),pixels.data());
    if(!handle)return 0;
    if(aspect)*aspect=float(w)/float(h);
    track_case_texture(handle,w,h);
    return handle;
#endif
}

// Drop mismatched completions BEFORE the GPU allocation, not after it.
// There is no renderer work, file read or socket call on an empty poll.
std::uint32_t niak_take_prepared_case_art(
        hui::gfx::Renderer &renderer,const char *expected_id,
        char (&side)[16],float *aspect,
        bool (*accept)(const char *,void *),void *opaque) {
    side[0]=0;
#if defined(__PROSPERO__)
    auto &state=prepared_case_state();
    std::vector<unsigned char> pixels;
    std::string selected_side;
    unsigned w=0,h=0;
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        if(!state.completed)return 0;
        const bool selected=expected_id &&
            state.completed_id==expected_id &&
            state.selected_id==expected_id;
        selected_side=std::move(state.completed_side);
        if(selected) {
            pixels=std::move(state.completed_pixels);
            w=state.completed_width;
            h=state.completed_height;
        }
        state.completed_pixels.clear();
        state.completed=false;
        state.completed_id.clear();
        state.in_flight.erase(selected_side);
    }
    state.wake.notify_one();
    if(pixels.empty() || selected_side.size()>=sizeof(side) ||
       !w || !h || w>2048u || h>1536u ||
       pixels.size()!=std::size_t(w)*h*4u)return 0;
    // The catalogue can reject a superseded/redundant paper face BEFORE
    // allocating GPU memory. Always consume the result and wake the worker.
    if(accept && !accept(selected_side.c_str(),opaque))return 0;
    std::memcpy(side,selected_side.c_str(),selected_side.size()+1u);
    const auto handle=renderer.create_texture(int(w),int(h),pixels.data());
    if(handle) {
        if(aspect)*aspect=float(w)/float(h);
        track_case_texture(handle,w,h);
    }
    return handle;
#else
    (void)renderer;(void)expected_id;(void)aspect;
    (void)accept;(void)opaque;
    return 0;
#endif
}

void niak_destroy_case_texture(hui::gfx::Renderer &renderer,
                               std::uint32_t &texture){
 if(!texture)return;
 const auto it=tracked_case_textures.find(texture);
 if(it!=tracked_case_textures.end()){
     const auto bytes=it->second;
     auto &total=niak::case_media_stats.case_texture_bytes;
     total=total>=bytes?total-bytes:0;
     tracked_case_textures.erase(it);
 }
 renderer.destroy_texture(texture);
 texture=0;
}
namespace {
bool template_attempted[6]={};
std::uint32_t template_textures[6]={};
// The same authoritative PNG/WebP preference and alpha separation is used
// by the host preview and the PS5 worker; no duplicate image pipeline.
bool prepare_case_template_pixels(int generation,int side,
                                  std::vector<unsigned char> &pixels,
                                  unsigned &w,unsigned &h) {
 const char *platform=generation==0?"ps4":"ps5";
 const char *part=side==0?"front":side==1?"back":"spine";
 char file[512]{};
#if defined(__linux__)
 const auto fail=[&](const char *reason)->bool{
     std::fprintf(stderr,"[NiakPS5 preview] fixed template %s-%s: %s [%s]\\n",
                  platform,part,reason,file);
     return false;
 };
#else
 const auto fail=[&](const char *)->bool{return false;};
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
 // User-provided PNG originals always win over the built-in compressed
 // WebP defaults. This works entirely inside the NiakPS5 native title.
#if defined(__PROSPERO__)
 if(!fp) {
     std::snprintf(file,sizeof(file),
        "/data/homebrew/PPSA99386/assets/niak-templates/%s-%s.webp",
        platform,part);
     fp=std::fopen(file,"rb");
 }
 if(!fp) {
     std::snprintf(file,sizeof(file),
        "/app0/assets/niak-templates/%s-%s.webp",platform,part);
     fp=std::fopen(file,"rb");
 }
#endif
 if(!fp)return fail("not found"); // Optional on offline PS5, required in CI.
 if(std::fseek(fp,0,SEEK_END)!=0){std::fclose(fp);return false;}
 const long size=std::ftell(fp);
 if(size<33 || size>3*1024*1024 || std::fseek(fp,0,SEEK_SET)!=0)
     {std::fclose(fp);return false;}
 std::vector<unsigned char> bytes(static_cast<std::size_t>(size));
 const bool complete=std::fread(bytes.data(),1,bytes.size(),fp)==bytes.size();
 std::fclose(fp);if(!complete)return false;
 if(bytes.size()<24)return false;
 const bool webp=std::memcmp(bytes.data(),"RIFF",4)==0 &&
                  std::memcmp(bytes.data()+8,"WEBP",4)==0;
 unsigned width=0,height=0;
 if(webp) {
#if defined(__PROSPERO__)
     int iw=0,ih=0;
     if(!WebPGetInfo(bytes.data(),bytes.size(),&iw,&ih) ||
        iw<=0||ih<=0)return false;
     width=unsigned(iw);height=unsigned(ih);
#else
     return fail("WebP template unsupported by host preview");
#endif
 } else {
     if(std::memcmp(bytes.data(),"\x89PNG\r\n\x1a\n",8)!=0)return false;
     width=(unsigned(bytes[16])<<24)|(unsigned(bytes[17])<<16)|
           (unsigned(bytes[18])<<8)|bytes[19];
     height=(unsigned(bytes[20])<<24)|(unsigned(bytes[21])<<16)|
            (unsigned(bytes[22])<<8)|bytes[23];
 }
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
 w=width;h=height;
 unsigned decode_error=0;
 if(webp) {
#if defined(__PROSPERO__)
     pixels.resize(std::size_t(w)*h*4u);
     if(!WebPDecodeRGBAInto(bytes.data(),bytes.size(),pixels.data(),
                            pixels.size(),int(w*4u)))decode_error=1;
#else
     decode_error=1;
#endif
 } else {
     decode_error=lodepng::decode(pixels,w,h,bytes);
 }
 if(decode_error || w!=width || h!=height ||
    pixels.size()!=std::size_t(w)*h*4) {
#if defined(__linux__)
    std::fprintf(stderr,
        "[NiakPS5 preview] decode %s-%s error=%u expected=%ux%u decoded=%ux%u\\n",
        platform,part,decode_error,width,height,w,h);
#endif
    return fail("PNG decoding failed");
 }
 // Restore the supplied PS4/PS5 lower block above our continuous sheet.
 // Legacy opaque blocks contain their own white/anthracite paper: key it
 // out, preserving the actual logos, pictograms, labels and image details.
 if(side==1 && !niak_footer_paper_to_alpha(pixels,w,h,generation==0))
     return fail("footer paper cannot be safely separated from source art");
 // Shared mastheads/footers also avoid needless original-size GPU textures.
 if(!niak_scale_case_rgba(pixels,w,h,side==2?96u:1024u,
                          side==2?768u:512u))return fail("resampling failed");
 return true;
}
#if defined(__PROSPERO__)
struct PreparedTemplates {
 std::mutex mutex;
 std::condition_variable wake;
 std::deque<int> queue;
 std::uint64_t generation=0;
 int completed_index=-1;
 std::vector<unsigned char> completed_pixels;
 unsigned completed_width=0,completed_height=0;
 bool started=false,completed=false;
};
PreparedTemplates &template_state() {
 static auto *state=new PreparedTemplates;
 return *state;
}
void template_reader_worker() {
 auto &state=template_state();
 for(;;) {
  int index=-1;
  std::uint64_t epoch=0;
  {
   std::unique_lock<std::mutex> lock(state.mutex);
   state.wake.wait(lock,[&] {return !state.completed && !state.queue.empty();});
   index=state.queue.front();
   state.queue.pop_front();
   epoch=state.generation;
  }
  std::vector<unsigned char> pixels;
  unsigned width=0,height=0;
  // This worker touches only CPU memory and the private local asset paths.
  const bool okay=prepare_case_template_pixels(
      index/3,index%3,pixels,width,height);
  std::lock_guard<std::mutex> lock(state.mutex);
  if(epoch!=state.generation || !okay)continue;
  state.completed_index=index;
  state.completed_width=width;
  state.completed_height=height;
  state.completed_pixels=std::move(pixels);
  state.completed=true;
 }
}
void queue_case_template(int index) {
 auto &state=template_state();
 std::lock_guard<std::mutex> lock(state.mutex);
 // Exactly six canonical templates, queued once per renderer lifecycle.
 if(state.queue.size()>=6)return;
 state.queue.push_back(index);
 if(!state.started) {
  state.started=true;
  std::thread([] {template_reader_worker();}).detach();
 }
 state.wake.notify_one();
}
#endif
int case_template_index(const char *platform,const char *part) {
 const char *platforms[]={"ps4","ps5"};
 const char *parts[]={"front","back","spine"};
 int generation=-1,side=-1;
 for(int i=0;i<2;++i)
     if(platform && std::strcmp(platform,platforms[i])==0)generation=i;
 for(int i=0;i<3;++i)
     if(part && std::strcmp(part,parts[i])==0)side=i;
 return generation<0||side<0?-1:generation*3+side;
}
} // namespace

void niak_release_case_templates(hui::gfx::Renderer &renderer) {
#if defined(__PROSPERO__)
 // A worker may still decode during a catalogue rebuild; invalidate both
 // queued requests and in-flight results before freeing shared textures.
 auto &state=template_state();
 {
  std::lock_guard<std::mutex> lock(state.mutex);
  ++state.generation;
  state.queue.clear();
  state.completed=false;
  state.completed_index=-1;
  state.completed_pixels.clear();
 }
 state.wake.notify_one();
#endif
 for(int i=0;i<6;++i) {
  niak_destroy_case_texture(renderer,template_textures[i]);
  template_attempted[i]=false;
 }
}
std::uint32_t niak_get_ready_case_template(const char *platform,const char *part) {
 const int index=case_template_index(platform,part);
 return index>=0?template_textures[index]:0;
}
bool niak_upload_one_prepared_case_template(hui::gfx::Renderer &renderer) {
#if defined(__PROSPERO__)
 auto &state=template_state();
 std::vector<unsigned char> pixels;
 int index=-1;
 unsigned w=0,h=0;
 {
  std::lock_guard<std::mutex> lock(state.mutex);
  if(!state.completed)return false;
  index=state.completed_index;
  pixels=std::move(state.completed_pixels);
  w=state.completed_width;h=state.completed_height;
  state.completed=false;
  state.completed_index=-1;
 }
 state.wake.notify_one();
 // Bound all graphics allocations, and never recreate a shared slot.
 if(index<0||index>=6||template_textures[index] || !w||!h||
    w>1024u||h>768u||pixels.size()!=std::size_t(w)*h*4u)return false;
 template_textures[index]=renderer.create_texture(int(w),int(h),pixels.data());
 if(template_textures[index]) {
  track_case_texture(template_textures[index],w,h);
  return true;
 }
 return false;
#else
 (void)renderer;
 return false;
#endif
}
std::uint32_t niak_load_case_template(hui::gfx::Renderer &renderer,
                                      const char *platform,const char *part) {
 const int index=case_template_index(platform,part);
 if(index<0)return 0;
 if(template_attempted[index])return template_textures[index];
 template_attempted[index]=true;
#if defined(__PROSPERO__)
 // Decode/alpha-key/resize off the GL thread. This call never opens files.
 queue_case_template(index);
 (void)renderer;
 return 0;
#else
 // Keep synchronous host Mesa fixtures deterministic.
 std::vector<unsigned char> pixels;
 unsigned w=0,h=0;
 if(!prepare_case_template_pixels(index/3,index%3,pixels,w,h))return 0;
 template_textures[index]=renderer.create_texture(int(w),int(h),pixels.data());
 if(template_textures[index])
     track_case_texture(template_textures[index],w,h);
 return template_textures[index];
#endif
}
