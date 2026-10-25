// SPDX-License-Identifier: GPL-3.0-or-later
// Real installed PS5 game icons, read over the local ShadowMountPlus API.
// This client never requests mount/uninstall/write endpoints.
#include "niak/game_icons.hpp"
#include "niak/case_art.hpp"
extern "C" {
#include "niak/catalog.h"
}
#include "niak/lodepng.h"
#if defined(__PROSPERO__)
#include <webp/decode.h>
#endif
#include "niak/socket_guard.h"
#include "niak/http_icon_response.hpp"
#include "niak/icon_endpoint_policy.hpp"
#include "niak/loopback_connect.h"
#include "gfx/renderer.hpp"
#include "platform/ps5/system.hpp"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <array>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <thread>
#include <unordered_set>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>

namespace {
constexpr std::size_t kMaximumPng = 4U * 1024U * 1024U;
// Library tiles are ~200 px wide. 256 px icon textures save 75% of the
// RGBA8 GPU memory per installed title compared with the old 512 px cache.
constexpr int kTarget = 256;
NiakIconEndpointPolicy icon_endpoint;
std::uint64_t endpoint_now_ms() {
    using namespace std::chrono;
    return static_cast<std::uint64_t>(
        duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count());
}
bool download(const std::string &uri, std::vector<unsigned char> &out)
{
    if(!icon_endpoint.allowed(endpoint_now_ms()))return false;
    // Whole-operation deadline: a slow local HTTP response must not hold
    // the renderer thread indefinitely by trickling one fragment at a time.
    const auto deadline=std::chrono::steady_clock::now()+
                        std::chrono::milliseconds(220);
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        icon_endpoint.transport_failed(endpoint_now_ms());
        return false;
    }
    // ShadowMountPlus may close its HTTP socket while assets are loading;
    // do not let SIGPIPE kill the entire native title.
    niak_socket_guard(sock);
    // Socket timeouts are individual limits, not the overall deadline.
    timeval timeout{0, 100000};
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(10101);
    address.sin_addr.s_addr = htonl(0x7f000001u);
    if (niak_connect_bounded(sock, reinterpret_cast<sockaddr *>(&address), sizeof(address), 75) < 0)
    {
        close(sock);
        icon_endpoint.transport_failed(endpoint_now_ms());
        return false;
    }
    const std::string request =
        "GET " + uri + " HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
    std::size_t sent = 0;
    while (sent < request.size())
    {
        if(std::chrono::steady_clock::now()>=deadline) {
            close(sock);icon_endpoint.transport_failed(endpoint_now_ms());return false;
        }
        const ssize_t n = niak_socket_send(sock, request.data() + sent, request.size() - sent);
        if (n <= 0) { close(sock); icon_endpoint.transport_failed(endpoint_now_ms()); return false; }
        sent += static_cast<std::size_t>(n);
    }
    std::vector<unsigned char> response;
    response.reserve(256*1024);
    // The framing parser rechecks buffered bytes as fragments arrive.
    // Read in 64 KiB slabs rather than 8 KiB to reduce repeated scans
    // and receive syscalls for multi-megabyte PNGs (same bounded total size).
    std::array<unsigned char,65536> buffer{};
    // Complete Content-Length and chunked bodies without waiting for EOF:
    // the local API may legitimately keep its HTTP connection open.
    while(response.size()<kMaximumPng+8192+256*1024) {
        const auto remaining=std::chrono::duration_cast<std::chrono::microseconds>(
            deadline-std::chrono::steady_clock::now()).count();
        if(remaining<=0) {icon_endpoint.transport_failed(endpoint_now_ms());break;}
        const auto wait_us=std::min<std::int64_t>(remaining,100000);
        timeval recv_timeout{0,static_cast<suseconds_t>(std::max<std::int64_t>(wait_us,1000))};
        (void)setsockopt(sock,SOL_SOCKET,SO_RCVTIMEO,&recv_timeout,sizeof(recv_timeout));
        const ssize_t count=recv(sock,buffer.data(),buffer.size(),0);
        if(count>0) {
            response.insert(response.end(),buffer.begin(),buffer.begin()+count);
            // 404 is a complete and valid refusal for THIS icon, not an
            // endpoint failure. A 200 header alone is not enough: a server
            // can stall before delivering any body data.
            const auto reply=niak_icon_reply(response.data(),response.size());
            if(reply==NiakIconReply::OtherStatus) {
                icon_endpoint.responded();
                close(sock);
                return false;
            }
            if(reply==NiakIconReply::Invalid)break;
            const auto state=niak_http_icon_body(response,false,kMaximumPng,out);
            if(state==NiakHttpState::Complete) {
                icon_endpoint.responded();
                close(sock);
                return out.size()>=24 && out.size()<=kMaximumPng;
            }
            if(state==NiakHttpState::Invalid)break;
            continue;
        }
        if(count==0) {
            const auto state=niak_http_icon_body(response,true,kMaximumPng,out);
            if(state==NiakHttpState::Complete)icon_endpoint.responded();
            else icon_endpoint.transport_failed(endpoint_now_ms());
            close(sock);
            return state==NiakHttpState::Complete &&
                   out.size()>=24 && out.size()<=kMaximumPng;
        }
        icon_endpoint.transport_failed(endpoint_now_ms());
        break;
    }
    close(sock);
    return false;
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
// Verified installed PNG and modern quality-80 WebP, bounded before allocation.
// Inspect scene geometry before decoding potentially large source images.
// An icon, portrait or square cover must not consume 16 MiB of RGBA
// allocation only to be rejected as a background after decompression.
bool valid_scene_dimensions(unsigned width,unsigned height) {
    return width>=512 && height>=256 &&
           width<=2048 && height<=1536 &&
           std::uint64_t(width)*10u>=std::uint64_t(height)*13u &&
           std::uint64_t(width)*2u<=std::uint64_t(height)*5u;
}
bool decode_installed_art(const std::vector<unsigned char> &bytes,
                          std::vector<unsigned char> &rgba,
                          unsigned &w,unsigned &h,
                          bool landscape_scene=false)
{
    if(bytes.size()<24||bytes.size()>kMaximumPng)return false;
    const bool webp=std::memcmp(bytes.data(),"RIFF",4)==0 &&
                    std::memcmp(bytes.data()+8,"WEBP",4)==0;
    if(webp) {
#if defined(__PROSPERO__)
        int iw=0,ih=0;
        if(!WebPGetInfo(bytes.data(),bytes.size(),&iw,&ih)||
           iw<32||ih<32||iw>2048||ih>2048)return false;
        w=unsigned(iw);h=unsigned(ih);
        if(landscape_scene && !valid_scene_dimensions(w,h))return false;
        rgba.resize(std::size_t(w)*h*4u);
        return WebPDecodeRGBAInto(bytes.data(),bytes.size(),rgba.data(),
                                  rgba.size(),int(w*4u))!=nullptr;
#else
        return false;
#endif
    }
    static const unsigned char signature[8]={137,80,78,71,13,10,26,10};
    if(std::memcmp(bytes.data(),signature,8)!=0)return false;
    const unsigned iw=size32(bytes.data()+16),ih=size32(bytes.data()+20);
    if(iw<32||ih<32||iw>2048||ih>2048)return false;
    if(landscape_scene && !valid_scene_dimensions(iw,ih))return false;
    if(lodepng::decode(rgba,w,h,bytes)!=0||w!=iw||h!=ih)return false;
    return rgba.size()==std::size_t(w)*h*4u;
}
// CPU-only and reentrant: usable by the HTTP worker or by the local-art
// reader. Network completions carry only 256x256 RGBA, never compressed
// multi-megabyte input or large decoded 2048x2048 image buffers.
bool decode_icon_thumbnail(const std::vector<unsigned char> &image,
                           std::vector<unsigned char> &scaled)
{
    std::vector<unsigned char> rgba;
    unsigned w=0,h=0;
    if(!decode_installed_art(image,rgba,w,h))return false;
    if(w==kTarget && h==kTarget) {
        scaled=std::move(rgba);
        return true;
    }
    scaled.resize(static_cast<std::size_t>(kTarget)*kTarget*4u);
    for(int y=0;y<kTarget;++y) {
        const unsigned sy=std::min(h-1,static_cast<unsigned>(
            (static_cast<std::uint64_t>(y)*h)/kTarget));
        for(int x=0;x<kTarget;++x) {
            const unsigned sx=std::min(w-1,static_cast<unsigned>(
                (static_cast<std::uint64_t>(x)*w)/kTarget));
            const std::size_t a=(static_cast<std::size_t>(sy)*w+sx)*4u;
            const std::size_t b=(static_cast<std::size_t>(y)*kTarget+x)*4u;
            for(int c=0;c<4;++c)scaled[b+c]=rgba[a+c];
        }
    }
    return true;
}
std::uint32_t decode_upload(hui::gfx::Renderer &renderer,
                             const std::vector<unsigned char> &image)
{
    // Locally installed artwork still uses this synchronous path; only
    // network icons are decoded and resized by the dedicated HTTP worker.
    std::vector<unsigned char> pixels;
    if(!decode_icon_thumbnail(image,pixels))return 0;
    return renderer.create_texture(kTarget,kTarget,pixels.data());
}
// Preserve installed-art priority on BOTH PS5 and host. Only the worker
// opens local files on PS5; the host preview retains its existing eager path.
constexpr const char *kInstalledIconPaths[] = {
        "/app0/assets/niak-installed/%s-icon.webp",
        "/data/homebrew/PPSA99386/assets/niak-installed/%s-icon.webp",
        "/app0/assets/niak-installed/%s-icon.png",
        "/data/homebrew/PPSA99386/assets/niak-installed/%s-icon.png",
        "/data/homebrew/%s/sce_sys/icon0.png",
        "/user/app/%s/sce_sys/icon0.png",
        "/user/appmeta/%s/icon0.png",
        "/system_ex/app/%s/sce_sys/icon0.png",
        "/mnt/ext0/user/app/%s/sce_sys/icon0.png",
        "/mnt/ext1/user/app/%s/sce_sys/icon0.png",
        "/mnt/ext0/user/appmeta/%s/icon0.png",
        "/mnt/ext1/user/appmeta/%s/icon0.png"};
bool load_installed_icon_pixels(const char *id,
                                std::vector<unsigned char> &pixels) {
    for(const char *format : kInstalledIconPaths) {
        char path[160]{};
        const int n=std::snprintf(path,sizeof(path),format,id);
        if(n<=0 || n>=int(sizeof(path)))continue;
        std::vector<unsigned char> encoded;
        if(read_local_png(path,encoded) &&
           decode_icon_thumbnail(encoded,pixels))return true;
    }
    return false;
}
// One background reader for missing installed icons. The GPU renderer never
// calls a socket API: it only consumes a completed byte vector. One completion
// slot applies backpressure (one 256x256 RGBA buffer: 256 KiB).
// This process-lifetime object is intentional: the detached reader must not
// reference destroyed static mutexes or catalogue-owned Item pointers.
#if defined(__PROSPERO__)
struct AsyncIconDownloads {
    std::mutex mutex;
    std::condition_variable wake;
    std::deque<std::string> queue;
    std::unordered_set<std::string> seen;
    std::string completed_title;
    std::vector<unsigned char> completed_pixels;
    bool completed=false;
    bool started=false;
};
AsyncIconDownloads &async_icons() {
    static auto *state=new AsyncIconDownloads;
    return *state;
}
void icon_reader_worker() {
    auto &state=async_icons();
    for(;;) {
        std::string id;
        {
            std::unique_lock<std::mutex> lock(state.mutex);
            state.wake.wait(lock,[&] {
                return !state.completed && !state.queue.empty();
            });
            id=std::move(state.queue.front());
            state.queue.pop_front();
        }
        // Installed art is authoritative. Reading, PNG/WebP decoding and
        // downsampling all happen here, never on the PS5 render thread.
        std::vector<unsigned char> pixels;
        if(!load_installed_icon_pixels(id.c_str(),pixels)) {
            std::vector<unsigned char> bytes;
            const std::string url="/api/v1/games/icon?title_id="+id;
            bool complete=download(url,bytes);
            // A 404 applies only to the full-size image. Do not repeat a
            // failed transport request for its thumbnail.
            if(!complete && !icon_endpoint.consecutive_failures) {
                bytes.clear();
                complete=download(url+"&size=thumb",bytes);
            }
            if(!complete || !decode_icon_thumbnail(bytes,pixels)) {
                // Temporary outage, denied media or corrupt response:
                // allow the throttled idle retry to revisit this title.
                std::lock_guard<std::mutex> lock(state.mutex);
                state.seen.erase(id);
                continue;
            }
        }
        {
            std::lock_guard<std::mutex> lock(state.mutex);
            state.completed_title=std::move(id);
            state.completed_pixels=std::move(pixels);
            state.completed=true;
        }
        // The reader cannot get ahead of the renderer and accumulate raw
        // HTTP responses. The next tick consumes this one on the GL thread.
    }
}
void request_missing_icon(const char *id) {
    auto &state=async_icons();
    std::lock_guard<std::mutex> lock(state.mutex);
    // "seen" tracks QUEUED/in-flight/unconsumed responses, not permanent
    // success or failure. Cleared at worker failure or renderer consumption.
    if(state.seen.size()>=4096 || !state.seen.emplace(id).second)return;
    state.queue.emplace_back(id);
    if(!state.started) {
        state.started=true;
        std::thread([] {icon_reader_worker();}).detach();
    }
    state.wake.notify_one();
}
// This SECOND bounded CPU worker is dedicated to installed pic1 / scene art.
// It never touches OpenGL, remote services or catalogue-owned Item pointers.
// Results are one 768x320..560 RGBA buffer (~1.7 MiB maximum) pending upload.
struct AsyncCaseBackground {
    std::mutex mutex;
    std::condition_variable wake;
    std::deque<std::string> queue;
    std::unordered_set<std::string> queued;
    // Every focus change supersedes ALL earlier scene work, including an
    // in-flight decode. No stale artwork may monopolize the next GPU upload.
    std::uint64_t generation=0;
    std::string latest_title;
    std::string completed_title;
    std::vector<unsigned char> completed_pixels;
    unsigned completed_width=0,completed_height=0;
    bool completed=false,started=false;
};
AsyncCaseBackground &case_background_state() {
    static auto *state=new AsyncCaseBackground;
    return *state;
}
void case_background_worker() {
    auto &state=case_background_state();
    for(;;) {
        std::string id;
        std::uint64_t generation=0;
        {
            std::unique_lock<std::mutex> lock(state.mutex);
            state.wake.wait(lock,[&] {
                return !state.completed && !state.queue.empty();
            });
            id=std::move(state.queue.front());
            state.queue.pop_front();
            generation=state.generation;
        }
        std::vector<unsigned char> pixels;
        unsigned target_w=0,target_h=0;
        // Priority matches the production path: WebP cache, installed
        // scene, then pic1.png on internal and external storage.
        for(const char *format : {
            "/app0/assets/niak-installed/%s-scene.webp",
            "/data/homebrew/PPSA99386/assets/niak-installed/%s-scene.webp",
            "/app0/assets/niak-installed/%s-scene.png",
            "/data/homebrew/PPSA99386/assets/niak-installed/%s-scene.png",
            "/data/homebrew/%s/sce_sys/pic1.png",
            "/user/app/%s/sce_sys/pic1.png",
            "/user/appmeta/%s/pic1.png",
            "/system_ex/app/%s/sce_sys/pic1.png",
            "/mnt/ext0/user/app/%s/sce_sys/pic1.png",
            "/mnt/ext1/user/app/%s/sce_sys/pic1.png"
        }) {
            char path[200]{};
            const int n=std::snprintf(path,sizeof(path),format,id.c_str());
            if(n<=0 || n>=int(sizeof(path)))continue;
            std::vector<unsigned char> image,rgba;
            unsigned width=0,height=0;
            if(!read_local_png(path,image))continue;
            if(!decode_installed_art(image,rgba,width,height,true))continue;
            target_w=768;
            target_h=std::max(320u,std::min(560u,
                unsigned((std::uint64_t(target_w)*height)/width)));
            pixels.resize(std::size_t(target_w)*target_h*4u);
            for(unsigned y=0;y<target_h;++y) {
                const unsigned sy=std::min(height-1,unsigned(
                    (std::uint64_t(y)*height)/target_h));
                for(unsigned x=0;x<target_w;++x) {
                    const unsigned sx=std::min(width-1,unsigned(
                        (std::uint64_t(x)*width)/target_w));
                    const auto src=(std::size_t(sy)*width+sx)*4u;
                    const auto dst=(std::size_t(y)*target_w+x)*4u;
                    for(int k=0;k<4;++k)pixels[dst+k]=rgba[src+k];
                }
            }
            break;
        }
        std::lock_guard<std::mutex> lock(state.mutex);
        // A user can select many games while one big PNG is decoding.
        // Discard superseded results without modifying queued work for the
        // latest selection, even if the old and new title IDs are equal.
        if(generation!=state.generation || id!=state.latest_title)
            continue;
        if(pixels.empty()) {
            state.queued.erase(id);
            continue;
        }
        state.completed_title=std::move(id);
        state.completed_width=target_w;
        state.completed_height=target_h;
        state.completed_pixels=std::move(pixels);
        state.completed=true;
    }
}
void enqueue_missing_scene(const char *id) {
    auto &state=case_background_state();
    std::lock_guard<std::mutex> lock(state.mutex);
    // There is only one selected 3D case. Older queued requests are not
    // useful; clear them and invalidate a previous completed buffer.
    if(state.latest_title!=id) {
        state.latest_title=id;
        ++state.generation;
        state.queue.clear();
        state.queued.clear();
        state.completed=false;
        state.completed_title.clear();
        state.completed_pixels.clear();
    }
    // Deduplicate a pending/in-flight/completed request for this title.
    if(state.queued.size()>=1 || !state.queued.emplace(id).second)return;
    state.queue.emplace_back(id);
    if(!state.started) {
        state.started=true;
        std::thread([] {case_background_worker();}).detach();
    }
    state.wake.notify_one();
}
#endif
} // namespace

std::uint32_t niak_load_game_icon(hui::gfx::Renderer &renderer, const char *id)
{
    // Media applications may use NPXSxxxxx, unlike regular PPSA/CUSA games.
    bool media=id && std::strlen(id)==9 &&
               std::strncmp(id,"NPXS",4)==0;
    if(media)for(int i=4;i<9;++i)
        if(id[i]<'0'||id[i]>'9')media=false;
    if(!niak_valid_title_id(id) && !media)return 0;
#if defined(__PROSPERO__)
    // No local disk access, decompression, HTTP or GPU upload during initial
    // shelf streaming. The sole CPU worker tries installed art before HTTP.
    request_missing_icon(id);
    return 0;
#else
    std::vector<unsigned char> png;
#if defined(__linux__)
    // Host-only art is original QA artwork; not packaged or consulted on PS5.
    if(const char *fixtures=std::getenv("NIAK_CASE_PREVIEW_MEDIA")) {
        if(fixtures[0]) {
            char path[480]{};
            std::snprintf(path,sizeof(path),"%s/%s-icon.png",fixtures,id);
            if(read_local_png(path,png))
                if(const auto handle=decode_upload(renderer,png))return handle;
        }
    }
#endif
    // Try the actual installed icon first. This also works for homebrews
    // when ShadowMountPlus does not expose their icon endpoint.
    for(const char *format : kInstalledIconPaths) {
        char path[160]{};
        std::snprintf(path,sizeof(path),format,id);
        png.clear();
        if(read_local_png(path,png))
            if(const auto handle=decode_upload(renderer,png)) return handle;
    }
    png.clear();
    const std::string url=std::string("/api/v1/games/icon?title_id=")+id;
    if(download(url,png)) {
        if(const auto texture=decode_upload(renderer,png))return texture;
    }
    if(!icon_endpoint.consecutive_failures) {
        png.clear();
        if(download(url+"&size=thumb",png))
            return decode_upload(renderer,png);
    }
#endif
    return 0;
}

void niak_request_missing_game_icon(const char *id) {
#if defined(__PROSPERO__)
    if(!id || !*id || std::strlen(id)>=16)return;
    bool media=std::strlen(id)==9 && std::strncmp(id,"NPXS",4)==0;
    if(media)for(int i=4;i<9;++i)
        if(id[i]<'0'||id[i]>'9')media=false;
    if(!niak_valid_title_id(id) && !media)return;
    // Pure queue management; no filesystem read, socket call or GPU upload.
    request_missing_icon(id);
#else
    (void)id;
#endif
}

std::uint32_t niak_take_downloaded_game_icon(hui::gfx::Renderer &renderer,
                                             char (&title_id)[16],
                                             bool (*accept)(const char *,void *),
                                             void *opaque) {
    title_id[0]=0;
#if defined(__PROSPERO__)
    auto &state=async_icons();
    std::string id;
    std::vector<unsigned char> bytes;
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        if(!state.completed)return 0;
        id=std::move(state.completed_title);
        bytes=std::move(state.completed_pixels);
        state.completed=false;
        // A future catalogue rebuild may need the same title again; no
        // permanent "already downloaded" blacklist is permitted.
        state.seen.erase(id);
    }
    state.wake.notify_one();
    if(id.size()>=sizeof(title_id))return 0;
    std::memcpy(title_id,id.data(),id.size());
    title_id[id.size()]=0;
    // The worker already decoded/resampled this image; only the GPU texture
    // allocation remains on its owning thread. Never decode here.
    if(bytes.size()!=std::size_t(kTarget)*kTarget*4u)return 0;
    // Drop an icon for an absent/fully loaded title BEFORE allocating VRAM.
    // The result was consumed above, so the worker is never blocked.
    if(accept && !accept(title_id,opaque))return 0;
    return renderer.create_texture(kTarget,kTarget,bytes.data());
#else
    (void)renderer;(void)accept;(void)opaque;
    return 0;
#endif
}

std::uint32_t niak_load_game_background(hui::gfx::Renderer &renderer,const char *id,float *aspect) {
    bool media=id && std::strlen(id)==9 && std::strncmp(id,"NPXS",4)==0;
    if(media)for(int i=4;i<9;++i)
        if(id[i]<'0'||id[i]>'9')media=false;
    if(!niak_valid_title_id(id) && !media)return 0;
#if defined(__PROSPERO__)
    // Stage-4 loader now schedules CPU-only work and returns immediately.
    // Result is installed later by refresh_pending_case_background().
    enqueue_missing_scene(id);
    (void)renderer;(void)aspect;
    return 0;
#else
    std::vector<unsigned char> png;
    std::vector<std::string> locations;
#if defined(__linux__)
    if(const char *fixtures=std::getenv("NIAK_CASE_PREVIEW_MEDIA")) {
        if(fixtures[0])locations.emplace_back(
            std::string(fixtures)+"/"+id+"-scene.png");
    }
#endif
    for(const char *format : {
        "/app0/assets/niak-installed/%s-scene.webp",
        "/data/homebrew/PPSA99386/assets/niak-installed/%s-scene.webp",
        "/app0/assets/niak-installed/%s-scene.png",
        "/data/homebrew/PPSA99386/assets/niak-installed/%s-scene.png",
        "/data/homebrew/%s/sce_sys/pic1.png",
        "/user/app/%s/sce_sys/pic1.png",
        "/user/appmeta/%s/pic1.png",
        "/system_ex/app/%s/sce_sys/pic1.png",
        "/mnt/ext0/user/app/%s/sce_sys/pic1.png",
        "/mnt/ext1/user/app/%s/sce_sys/pic1.png"
    }) {
        char path[200]{};
        std::snprintf(path,sizeof(path),format,id);
        locations.emplace_back(path);
    }
    for(const std::string &path:locations) {
        png.clear();
        if(!read_local_png(path.c_str(),png))continue;
        std::vector<unsigned char> rgba;
        unsigned w=0,h=0;
        // Reject non-landscape art before a costly PNG/WebP pixel decode.
        if(!decode_installed_art(png,rgba,w,h,true))continue;
        const unsigned target_w=768;
        const unsigned target_h=std::max(320u,std::min(560u,
            static_cast<unsigned>((std::uint64_t(target_w)*h)/w)));
        std::vector<unsigned char> scaled(std::size_t(target_w)*target_h*4);
        for(unsigned y=0;y<target_h;++y) {
            const unsigned sy=std::min(h-1,static_cast<unsigned>(
                (std::uint64_t(y)*h)/target_h));
            for(unsigned x=0;x<target_w;++x) {
                const unsigned sx=std::min(w-1,static_cast<unsigned>(
                    (std::uint64_t(x)*w)/target_w));
                const std::size_t src=(std::size_t(sy)*w+sx)*4;
                const std::size_t dst=(std::size_t(y)*target_w+x)*4;
                for(int k=0;k<4;++k)scaled[dst+k]=rgba[src+k];
            }
        }
        const auto texture=renderer.create_texture(
            int(target_w),int(target_h),scaled.data());
        // A rejected GPU allocation must not suppress the next local image.
        if(!texture)continue;
        niak_track_case_texture(texture,target_w,target_h);
        if(aspect)*aspect=float(target_w)/float(target_h);
        return texture;
    }
    return 0;
#endif
}

std::uint32_t niak_take_downloaded_game_background(
        hui::gfx::Renderer &renderer,char (&title_id)[16],float *aspect,
        const char *expected_id) {
    title_id[0]=0;
#if defined(__PROSPERO__)
    auto &state=case_background_state();
    std::string id;
    std::vector<unsigned char> pixels;
    unsigned width=0,height=0;
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        if(!state.completed)return 0;
        id=std::move(state.completed_title);
        pixels=std::move(state.completed_pixels);
        width=state.completed_width;
        height=state.completed_height;
        state.completed=false;
        state.queued.erase(id);
    }
    state.wake.notify_one();
    if(id.size()>=sizeof(title_id)||width!=768u||height<320u ||
       height>560u||pixels.size()!=std::size_t(width)*height*4u)
        return 0;
    // On rapid navigation, never allocate a stale scene merely to free it.
    // Even an empty/invalid selection drains the completed worker slot.
    if(!expected_id || id!=expected_id)return 0;
    std::memcpy(title_id,id.c_str(),id.size()+1u);
    // Never upload GL textures on the CPU worker.
    const auto texture=renderer.create_texture(int(width),int(height),pixels.data());
    if(texture) {
        niak_track_case_texture(texture,width,height);
        if(aspect)*aspect=float(width)/float(height);
    }
    return texture;
#else
    (void)renderer;(void)aspect;(void)expected_id;
    return 0;
#endif
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

// Pure CPU helper for the foreground user's explicitly selected PNG paths.
// The caller is responsible for verifying the active profile/owner marker.
bool niak_prepare_profile_png_file(const char *path,
                                   std::vector<std::uint8_t> &pixels) {
    if(!path)return false;
    std::vector<unsigned char> encoded;
    return read_local_png(path,encoded) && decode_icon_thumbnail(encoded,pixels);
}
