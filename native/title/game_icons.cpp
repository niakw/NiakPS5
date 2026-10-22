// SPDX-License-Identifier: GPL-3.0-or-later
// Real installed PS5 game icons, read over the local ShadowMountPlus API.
// This client never requests mount/uninstall/write endpoints.
#include "niak/game_icons.hpp"
extern "C" {
#include "niak/catalog.h"
}
#include "niak/lodepng.h"
#include "gfx/renderer.hpp"
#include "platform/ps5/system.hpp"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace {
constexpr std::size_t kMaximumPng = 4U * 1024U * 1024U;
constexpr int kTarget = 512;
bool download(const std::string &uri, std::vector<unsigned char> &out)
{
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return false;
    timeval timeout{1, 500000};
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(10101);
    address.sin_addr.s_addr = htonl(0x7f000001u);
    if (connect(sock, reinterpret_cast<sockaddr *>(&address), sizeof(address)) < 0)
    {
        close(sock);
        return false;
    }
    const std::string request =
        "GET " + uri + " HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
    std::size_t sent = 0;
    while (sent < request.size())
    {
        const ssize_t n = send(sock, request.data() + sent, request.size() - sent, 0);
        if (n <= 0) { close(sock); return false; }
        sent += static_cast<std::size_t>(n);
    }
    std::vector<unsigned char> response;
    response.reserve(256*1024);
    std::array<unsigned char, 8192> buffer{};
    ssize_t count = 0;
    while (response.size() < kMaximumPng + 8192)
    {
        count = recv(sock, buffer.data(), buffer.size(), 0);
        if (count <= 0) break;
        response.insert(response.end(), buffer.begin(), buffer.begin() + count);
    }
    close(sock);
    if (count < 0 || response.size() >= kMaximumPng + 8192 || response.size() < 24)
        return false;
    const char header[] = "\r\n\r\n";
    const auto split = std::search(response.begin(), response.end(),
                                    header, header + 4);
    if (split == response.end() || response.size() < 12 ||
        (std::memcmp(response.data(), "HTTP/1.1 200", 12) &&
         std::memcmp(response.data(), "HTTP/1.0 200", 12)))
        return false;
    const std::string headers(response.begin(), split);
    if (headers.find("Transfer-Encoding: chunked") != std::string::npos ||
        headers.find("transfer-encoding: chunked") != std::string::npos)
        return false;
    out.assign(split+4, response.end());
    return out.size() >= 24 && out.size() <= kMaximumPng;
}
unsigned size32(const unsigned char *bytes)
{
    return (static_cast<unsigned>(bytes[0])<<24) |
           (static_cast<unsigned>(bytes[1])<<16) |
           (static_cast<unsigned>(bytes[2])<<8) |
           static_cast<unsigned>(bytes[3]);
}
bool read_local_png(const char *path,std::vector<unsigned char> &png) {
    std::FILE *fp=std::fopen(path,"rb");
    if(!fp)return false;
    if(std::fseek(fp,0,SEEK_END)!=0){std::fclose(fp);return false;}
    const long length=std::ftell(fp);
    if(length<33||length>long(kMaximumPng)||std::fseek(fp,0,SEEK_SET)!=0) {
        std::fclose(fp);return false;
    }
    png.resize(static_cast<std::size_t>(length));
    const bool ok=std::fread(png.data(),1,png.size(),fp)==png.size();
    std::fclose(fp);return ok;
}
std::uint32_t decode_upload(hui::gfx::Renderer &renderer,
                             const std::vector<unsigned char> &png)
{
    static const unsigned char signature[8] = {137,80,78,71,13,10,26,10};
    if (png.size() < 33 || std::memcmp(png.data(),signature,8)) return 0;
    const unsigned initial_w = size32(png.data()+16);
    const unsigned initial_h = size32(png.data()+20);
    if (initial_w < 32 || initial_h < 32 || initial_w > 2048 || initial_h > 2048)
        return 0;
    std::vector<unsigned char> rgba;
    unsigned w = 0, h = 0;
    if (lodepng::decode(rgba,w,h,png) != 0 || w != initial_w || h != initial_h)
        return 0;
    if (rgba.size() != static_cast<std::size_t>(w)*h*4) return 0;
    // CPU downsample/upsample with four-pixel interpolation, bounded GPU allocation.
    std::vector<unsigned char> scaled(static_cast<std::size_t>(kTarget)*kTarget*4);
    for (int y=0;y<kTarget;++y)
    {
        const unsigned sy=std::min(h-1,static_cast<unsigned>((static_cast<std::uint64_t>(y)*h)/kTarget));
        for (int x=0;x<kTarget;++x)
        {
            const unsigned sx=std::min(w-1,static_cast<unsigned>((static_cast<std::uint64_t>(x)*w)/kTarget));
            const std::size_t a=(static_cast<std::size_t>(sy)*w+sx)*4;
            const std::size_t b=(static_cast<std::size_t>(y)*kTarget+x)*4;
            for(int c=0;c<4;++c) scaled[b+c]=rgba[a+c];
        }
    }
    return renderer.create_texture(kTarget,kTarget,scaled.data());
}
} // namespace

std::uint32_t niak_load_game_icon(hui::gfx::Renderer &renderer, const char *id)
{
    // Media applications may use NPXSxxxxx, unlike regular PPSA/CUSA games.
    bool media=id && std::strlen(id)==9 &&
               std::strncmp(id,"NPXS",4)==0;
    if(media)for(int i=4;i<9;++i)
        if(id[i]<'0'||id[i]>'9')media=false;
    if(!niak_valid_title_id(id) && !media)return 0;
    std::vector<unsigned char> png;
    // Try the actual installed icon first. This also works for homebrews
    // when ShadowMountPlus does not expose their icon endpoint.
    for(const char *format : {
        "/data/homebrew/%s/sce_sys/icon0.png",
        "/user/app/%s/sce_sys/icon0.png",
        "/user/appmeta/%s/icon0.png",
        "/system_ex/app/%s/sce_sys/icon0.png"}) {
        char path[160]{};
        std::snprintf(path,sizeof(path),format,id);
        png.clear();
        if(read_local_png(path,png))
            if(const auto handle=decode_upload(renderer,png)) return handle;
    }
    png.clear();
    const std::string url=std::string("/api/v1/games/icon?title_id=")+id;
    if (download(url,png))
    {
        if (const auto texture=decode_upload(renderer,png)) return texture;
    }
    png.clear();
    if (download(url+"&size=thumb",png))
        return decode_upload(renderer,png);
    return 0;
}

std::uint32_t niak_load_profile_cache_png(hui::gfx::Renderer &renderer,unsigned user) {
    char path[160];
    std::snprintf(path,sizeof(path),
        "/system_data/priv/cache/profile/0x%08X/avatar.png",user);
    std::vector<unsigned char> png;
    return read_local_png(path,png)?decode_upload(renderer,png):0;
}

std::uint32_t niak_load_local_png(hui::gfx::Renderer &renderer, const char *path)
{
    if(!path || (std::strcmp(path,"/app0/assets/niak-profile.png") != 0 &&
        std::strcmp(path,"/data/homebrew/PPSA99386/assets/niak-profile.png") != 0))
        return 0;
    std::FILE *f=std::fopen(path,"rb");
    if(!f)return 0;
    if(std::fseek(f,0,SEEK_END)!=0){std::fclose(f);return 0;}
    const long size=std::ftell(f);
    if(size<33 || size>2*1024*1024 || std::fseek(f,0,SEEK_SET)!=0)
    {std::fclose(f);return 0;}
    std::vector<unsigned char> data(static_cast<std::size_t>(size));
    const bool okay=std::fread(data.data(),1,data.size(),f)==data.size();
    std::fclose(f);
    return okay ? decode_upload(renderer,data) : 0;
}
