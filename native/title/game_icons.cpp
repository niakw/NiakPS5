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
    if (!niak_valid_title_id(id)) return 0;
    std::vector<unsigned char> png;
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
