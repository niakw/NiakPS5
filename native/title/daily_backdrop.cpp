// SPDX-License-Identifier: GPL-3.0-or-later
// Native PS5 wallpaper: a real PS5 feed queried once per calendar day.
// The OpenGL UI never waits for HTTP; last packaged art remains available.
#include "niak/daily_backdrop.hpp"
#include "niak/daily_runtime.hpp"
#include "niak/lodepng.h"
#include "gfx/renderer.hpp"
#include "platform/ps5/system.hpp"
#include <array>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace {
constexpr std::size_t MAX_BYTES=7u*1024u*1024u;
std::array<std::uint32_t,14> images{};
std::array<std::string,14> wallpaper_labels{};
int count=0;
int override_offset=0;
int override_day=-1;
// Today's manual wallpaper choice survives closing/reopening NiakPS5.
// A different local date ALWAYS resets to the automatic daily selection.
void restore_day_choice(int day) {
    if(override_day==day)return;
    override_day=day;
    override_offset=0;
    FILE *file=std::fopen("/download0/niak-wallpaper-choice.txt","rb");
    if(!file)return;
    int cached_day=-1,cached_offset=0;
    if(std::fscanf(file,"%d %d",&cached_day,&cached_offset)==2 &&
       cached_day==day && cached_offset>=0 && cached_offset<count)
        override_offset=cached_offset;
    std::fclose(file);
}
void save_day_choice(int day) {
    const char *tmp="/download0/niak-wallpaper-choice.txt.tmp";
    FILE *file=std::fopen(tmp,"wb");
    if(!file)return;
    const int wrote=std::fprintf(file,"%d %d\n",day,override_offset);
    const int flushed=std::fflush(file);
    const int closed=std::fclose(file);
    if(wrote<0 || flushed!=0 || closed!=0 ||
       std::rename(tmp,"/download0/niak-wallpaper-choice.txt")!=0)
        std::remove(tmp);
}
struct Runtime {
    std::mutex mutex;
    int started_day=-1, ready_day=-1, live_day=-1;
    bool pending=false;
    std::vector<std::uint8_t> bytes;
    std::uint32_t texture=0;
    hui::gfx::Renderer *renderer=nullptr;
};
Runtime &state() {
    // Intentionally process-lifetime: detached HTTP reader cannot reference
    // an object destroyed during title teardown. Memory stays bounded.
    static Runtime *runtime=new Runtime;
    return *runtime;
}
bool decode_png(const std::vector<std::uint8_t> &raw,
                unsigned &w,unsigned &h,
                std::vector<std::uint8_t> &rgba) {
    static const std::uint8_t sig[]={137,80,78,71,13,10,26,10};
    if(raw.size()<33||raw.size()>MAX_BYTES ||
       std::memcmp(raw.data(),sig,8)!=0)return false;
    w=(unsigned(raw[16])<<24)|(unsigned(raw[17])<<16)|
      (unsigned(raw[18])<<8)|unsigned(raw[19]);
    h=(unsigned(raw[20])<<24)|(unsigned(raw[21])<<16)|
      (unsigned(raw[22])<<8)|unsigned(raw[23]);
    if(w<320||h<320||w>4096||h>4096||
       std::uint64_t(w)*h>10'000'000)return false;
    unsigned dw=0,dh=0;
    if(lodepng::decode(rgba,dw,dh,raw)!=0||dw!=w||dh!=h ||
       rgba.size()!=std::size_t(w)*h*4)return false;
    return true;
}
bool load_packaged(const char *path,std::vector<std::uint8_t> &rgba) {
    std::FILE *file=std::fopen(path,"rb");if(!file)return false;
    if(std::fseek(file,0,SEEK_END)!=0){std::fclose(file);return false;}
    const long len=std::ftell(file);
    if(len<32||len>long(MAX_BYTES)||std::fseek(file,0,SEEK_SET)!=0) {
        std::fclose(file);return false;
    }
    std::vector<std::uint8_t> buffer(std::size_t(len),0);
    const bool ok=std::fread(buffer.data(),1,buffer.size(),file)==buffer.size();
    std::fclose(file);if(!ok)return false;
    unsigned w=0,h=0;
    return decode_png(buffer,w,h,rgba) && w==1280 && h==720;
}
bool read_cache(const char *day,std::vector<std::uint8_t> &bytes) {
    FILE *id=std::fopen("/download0/niak-wallpaper-date.txt","rb");
    if(!id)return false;
    char stored[16]{};
    const bool valid=std::fgets(stored,sizeof(stored),id)!=nullptr;
    std::fclose(id);
    if(!valid || std::strncmp(stored,day,10)!=0)return false;
    FILE *file=std::fopen("/download0/niak-wallpaper.png","rb");
    if(!file)return false;
    if(std::fseek(file,0,SEEK_END)!=0){std::fclose(file);return false;}
    long size=std::ftell(file);
    if(size<33||size>long(MAX_BYTES)||std::fseek(file,0,SEEK_SET)!=0){
        std::fclose(file);return false;
    }
    bytes.resize(std::size_t(size));
    const bool ok=std::fread(bytes.data(),1,bytes.size(),file)==bytes.size();
    std::fclose(file);
    return ok;
}
void save_cache(const char *day,const std::vector<std::uint8_t> &bytes) {
    FILE *image=std::fopen("/download0/niak-wallpaper.png.tmp","wb");
    if(!image)return;
    const bool written=std::fwrite(bytes.data(),1,bytes.size(),image)==bytes.size();
    const int flushed=std::fflush(image);
    const int closed=std::fclose(image);
    if(!written||flushed||closed||
       std::rename("/download0/niak-wallpaper.png.tmp",
                   "/download0/niak-wallpaper.png")!=0) {
        std::remove("/download0/niak-wallpaper.png.tmp");return;
    }
    FILE *stamp=std::fopen("/download0/niak-wallpaper-date.txt.tmp","wb");
    if(!stamp)return;
    const bool stamped=std::fwrite(day,1,10,stamp)==10;
    const int result=std::fclose(stamp);
    if(!stamped||result||
       std::rename("/download0/niak-wallpaper-date.txt.tmp",
                   "/download0/niak-wallpaper-date.txt")!=0)
        std::remove("/download0/niak-wallpaper-date.txt.tmp");
}
void worker(int day,std::string date) {
    std::vector<std::uint8_t> png;
    bool cached=read_cache(date.c_str(),png);
    if(!cached) {
        // No user account, game library, IP address or other console data
        // is included in the public PlayStation HTTPS requests.
        if(!niak_fetch_latest_ps5_wallpaper(date.c_str(),unsigned(day),png))
            return;
        save_cache(date.c_str(),png);
    }
    unsigned w=0,h=0;std::vector<std::uint8_t> rgba;
    if(!decode_png(png,w,h,rgba))return;
    Runtime &s=state();
    std::lock_guard<std::mutex> lock(s.mutex);
    s.bytes=std::move(png);
    s.ready_day=day;
    s.pending=true;
}
std::vector<std::uint8_t> fit_wallpaper(const std::vector<std::uint8_t> &input,
                                        unsigned w,unsigned h) {
    constexpr unsigned W=1280,H=720;
    std::vector<std::uint8_t> dest(std::size_t(W)*H*4);
    // A full-bleed crop for landscapes. For portrait cover art, preserve its
    // aspect ratio over a dark tinted soft backdrop (no stretched jacket).
    const bool portrait=float(w)/float(h)<1.42f;
    const float scale=std::max(float(W)/w,float(H)/h);
    const float scaled_w=w*scale,scaled_h=h*scale;
    for(unsigned y=0;y<H;++y)for(unsigned x=0;x<W;++x) {
        const auto xx=std::min(w-1,unsigned(std::max(0.f,
               (float(x)+(scaled_w-W)*.5f)/scale)));
        const auto yy=std::min(h-1,unsigned(std::max(0.f,
               (float(y)+(scaled_h-H)*.5f)/scale)));
        const auto src=(std::size_t(yy)*w+xx)*4,dst=(std::size_t(y)*W+x)*4;
        for(int c=0;c<3;++c)dest[dst+c]=portrait?std::uint8_t(input[src+c]/3):input[src+c];
        dest[dst+3]=255;
    }
    if(portrait) {
        const float front_scale=std::min(540.f/w,660.f/h);
        const unsigned fw=std::max(1u,unsigned(w*front_scale));
        const unsigned fh=std::max(1u,unsigned(h*front_scale));
        const unsigned ox=(W-fw)/2,oy=(H-fh)/2;
        for(unsigned y=0;y<fh;++y)for(unsigned x=0;x<fw;++x) {
            const unsigned xx=std::min(w-1,unsigned(float(x)/front_scale));
            const unsigned yy=std::min(h-1,unsigned(float(y)/front_scale));
            const auto a=(std::size_t(yy)*w+xx)*4;
            const auto b=(std::size_t(oy+y)*W+ox+x)*4;
            const unsigned alpha=input[a+3];
            for(int c=0;c<3;++c)
                dest[b+c]=std::uint8_t((unsigned(input[a+c])*alpha+
                                       unsigned(dest[b+c])*(255-alpha))/255);
        }
    }
    return dest;
}
int day_now(char (&date)[11]) {
    const auto now=std::time(nullptr);const auto *tm=std::localtime(&now);
    if(!tm)return -1;
    std::strftime(date,sizeof(date),"%Y-%m-%d",tm);
    return (tm->tm_year+1900)*372+tm->tm_mon*31+tm->tm_mday;
}
}
void niak_load_daily_backdrops(hui::gfx::Renderer &renderer,const char *directory) {
    Runtime &runtime=state();runtime.renderer=&renderer;
    count=0;
    std::array<std::string,14> by_file{};
    char manifest[256];
    if(std::snprintf(manifest,sizeof(manifest),"%s/labels.tsv",directory)>0) {
        FILE *labels=std::fopen(manifest,"rb");
        if(labels) {
            char line[320];
            while(std::fgets(line,sizeof(line),labels)) {
                int idx=-1;char title[140]{},date[24]{};
                if(std::sscanf(line,"wall-%02d.png\\t%139[^\\t]\\t%23[^\\r\\n]",
                               &idx,title,date)==3 &&
                   idx>=0 && idx<14 && std::strlen(date)==10 &&
                   date[4]=='-' && date[7]=='-') {
                    by_file[std::size_t(idx)]=std::string("Fond · ")+title+
                        " · "+std::string(date+8,2)+"/"+
                        std::string(date+5,2)+"/"+std::string(date,4);
                }
            }
            std::fclose(labels);
        }
    }
    for(int i=0;i<14;++i) {
        char path[256];std::snprintf(path,sizeof(path),"%s/wall-%02d.png",directory,i);
        std::vector<std::uint8_t> pixels;
        if(!load_packaged(path,pixels))continue;
        const auto texture=renderer.create_texture(1280,720,pixels.data());
        if(texture) {
            images[std::size_t(count)]=texture;
            wallpaper_labels[std::size_t(count)]=std::move(by_file[std::size_t(i)]);
            ++count;
        }
    }
    hui::sys::log("[NiakPS5] packaged PS5 wallpapers=%d, online refresh is optional",count);
}
std::uint32_t niak_daily_backdrop() {
    Runtime &s=state();char today[11]={};const int day=day_now(today);
    if(day<0)return count?images[0]:0;
    restore_day_choice(day);
#if defined(__PROSPERO__)
    if(s.started_day!=day) {
        s.started_day=day;
        // Network and JSON parsing stay off the render thread.
        std::thread([day,date=std::string(today)] {worker(day,date);}).detach();
    }
#endif
    {
        std::vector<std::uint8_t> bytes;
        {
            // The worker publishes only under this mutex. Never read the
            // completion flag without locking (would be a C++ data race).
            std::lock_guard<std::mutex> lock(s.mutex);
            if(s.pending&&s.ready_day==day) {
                bytes=std::move(s.bytes);
                s.pending=false;
            }
        }
        if(!bytes.empty()&&s.renderer) {
            unsigned w=0,h=0;std::vector<std::uint8_t> rgba;
            if(decode_png(bytes,w,h,rgba)) {
                auto image=fit_wallpaper(rgba,w,h);
                auto handle=s.renderer->create_texture(1280,720,image.data());
                if(handle) {
                    if(s.texture)s.renderer->destroy_texture(s.texture);
                    s.texture=handle;s.live_day=day;
                }
            }
        }
    }
    if(override_offset==0 && s.texture&&s.live_day==day)return s.texture;
    return count?images[std::size_t(((day+override_offset)%count+count)%count)]:0;
}

const char *niak_daily_backdrop_caption() {
    static constexpr const char *kUnknown="Fond · Sélection PS5";
    static constexpr const char *kLive="Fond du jour · Sélection PS5 en ligne";
    char today[11]{};const int day=day_now(today);
    if(day<0 || count==0)return kUnknown;
    restore_day_choice(day);
    Runtime &s=state();
    if(override_offset==0 && s.texture && s.live_day==day)return kLive;
    const int idx=((day+override_offset)%count+count)%count;
    const std::string &label=wallpaper_labels[std::size_t(idx)];
    return label.empty()?kUnknown:label.c_str();
}
void niak_next_daily_backdrop() {
    char date[11]{};
    const int day=day_now(date);
    if(count<2 || day<0)return;
    restore_day_choice(day);
    override_offset=(override_offset+1)%count;
    save_day_choice(day);
}
