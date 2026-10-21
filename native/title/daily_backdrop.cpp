// SPDX-License-Identifier: GPL-3.0-or-later
// Local daily backdrop cache (download handled outside PS5 at build time).
#include "niak/daily_backdrop.hpp"
#include "gfx/renderer.hpp"
#include "platform/ps5/system.hpp"
#include <array>
#include <cstdio>
#include <cstdint>
#include <ctime>
#include <vector>

namespace {
std::array<std::uint32_t, 14> textures{};
int images=0;
bool load_tga(const char *path, int *width, int *height, std::vector<std::uint8_t> &rgba) {
    FILE *f=std::fopen(path,"rb");
    if (!f) return false;
    std::uint8_t header[18]{};
    bool ok=std::fread(header,1,18,f)==18;
    const int w=header[12] | (header[13]<<8);
    const int h=header[14] | (header[15]<<8);
    const int channels=header[16]/8;
    if (!ok || header[1]!=0 || header[2]!=2 || header[0]!=0 ||
        w<320 || h<180 || w>1920 || h>1080 || (channels!=3 && channels!=4)) {
        std::fclose(f);return false;
    }
    const std::size_t bytes=static_cast<std::size_t>(w)*h*channels;
    std::vector<std::uint8_t> rgb(bytes);
    ok=std::fread(rgb.data(),1,bytes,f)==bytes;
    // Pillow writes the legal 26-byte TRUEVISION-XFILE footer after pixels.
    // The old exact-EOF check rejected EVERY valid packaged TGA wallpaper.
    // Decode only the bounded raster; ignore the optional footer.
    std::fclose(f);
    if (!ok)return false;
    rgba.resize(static_cast<std::size_t>(w)*h*4);
    const bool top=(header[17]&0x20)!=0;
    for (int y=0;y<h;++y)for (int x=0;x<w;++x) {
        const std::size_t src=(static_cast<std::size_t>(top?y:(h-1-y))*w+x)*channels;
        const std::size_t dst=(static_cast<std::size_t>(y)*w+x)*4;
        rgba[dst]=rgb[src+2];rgba[dst+1]=rgb[src+1];
        rgba[dst+2]=rgb[src];rgba[dst+3]=255;
    }
    *width=w;*height=h;return true;
}
} // namespace

void niak_load_daily_backdrops(hui::gfx::Renderer &renderer) {
    for(int n=0;n<14;++n) {
        char path[110];
        std::snprintf(path,sizeof(path),"/app0/assets/niak-daily/wall-%02d.tga",n);
        int w=0,h=0;std::vector<std::uint8_t> rgba;
        if(!load_tga(path,&w,&h,rgba))break;
        const auto id=renderer.create_texture(w,h,rgba.data());
        if (!id)break;
        textures[static_cast<std::size_t>(n)]=id;
        ++images;
    }
    hui::sys::log("[NiakPS5] daily wallpapers cached=%d; image delivery not sent to console",images);
}
std::uint32_t niak_daily_backdrop() {
    if(images==0)return 0;
    const std::time_t now=std::time(nullptr);
    // Stable one-game-per-local-day rotation; no network or disk access per frame.
    const std::tm *local=std::localtime(&now);
    if(!local)return textures[0];
    const int day=(local->tm_year+1900)*372+local->tm_mon*31+local->tm_mday;
    return textures[static_cast<std::size_t>((day%images+images)%images)];
}
