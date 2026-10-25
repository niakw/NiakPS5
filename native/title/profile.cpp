// SPDX-License-Identifier: GPL-3.0-or-later
// Only the current user's display name; never logs, persists or transmits it.
#include "niak/profile.hpp"
#include "niak/game_icons.hpp"
#include "gfx/renderer.hpp"
#include "niak/avatar_dds.hpp"
#include <vector>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <ctime>
extern "C" {
int sceUserServiceGetForegroundUser(int *user);
int sceUserServiceGetUserName(int user, char *name, std::size_t capacity);
}
const char *niak_ps5_user_label()
{
    static char label[72]="Profil PS5 indisponible";
    static std::time_t checked_at=0;
    const std::time_t now=std::time(nullptr);
    // A profile can change while the title remains alive. Refresh once
    // per wall-clock second, not at every rendered frame.
    if(!checked_at || now!=checked_at) {
        checked_at=now;
        int user=-1;
        char name[64]{};
        if(sceUserServiceGetForegroundUser(&user)==0 && user>=0 &&
           sceUserServiceGetUserName(user,name,sizeof(name))==0 &&
           name[0] && std::strlen(name)<sizeof(name))
            std::snprintf(label,sizeof(label),"%s",name);
        else
            std::snprintf(label,sizeof(label),"%s","Profil PS5 indisponible");
    }
    return label;
}

// DDS, PNG and owner checks run exclusively on the CPU worker. The only
// GPU operation in this file is uploading an already prepared avatar.
#include <condition_variable>
#include <mutex>
#include <thread>
#include <utility>
#include <cstdint>
#include <string>

namespace {
static std::uint32_t niak_user_avatar=0;
static int niak_avatar_owner=-1;

bool prepare_dds_avatar(const char *path,int &width,int &height,
                        std::vector<std::uint8_t> &pixels) {
    std::FILE *file=std::fopen(path,"rb");
    if(!file)return false;
    if(std::fseek(file,0,SEEK_END)!=0){std::fclose(file);return false;}
    const long size=std::ftell(file);
    if(size<144||size>2*1024*1024||std::fseek(file,0,SEEK_SET)!=0) {
        std::fclose(file);return false;
    }
    std::vector<std::uint8_t> encoded(static_cast<std::size_t>(size));
    const bool ok=std::fread(encoded.data(),1,encoded.size(),file)==encoded.size();
    std::fclose(file);
    return ok && niak_decode_avatar_dds(
        encoded.data(),encoded.size(),width,height,pixels);
}

bool prepare_current_avatar(int current,int &width,int &height,
                            std::vector<std::uint8_t> &pixels) {
    // Owner marker is checked before trying any staged (potentially stale)
    // user assets. The current account's private read-only cache is separate.
    char identity[16]{};
    std::snprintf(identity,sizeof(identity),"0x%08X",
                  static_cast<unsigned>(current));
    char marker[32]{};
    std::FILE *owner=std::fopen("/app0/assets/niak-profile-source.txt","rb");
    if(!owner)owner=std::fopen(
        "/data/homebrew/PPSA99386/assets/niak-profile-source.txt","rb");
    if(owner) {
        (void)std::fgets(marker,sizeof(marker),owner);
        std::fclose(owner);
    }
    const bool identified=std::strncmp(marker,identity,10)==0 && marker[10]==' ';
    const bool staged_png=identified && std::strcmp(marker+11,"png\\n")==0;
    const bool staged_dds=identified && std::strcmp(marker+11,"dds\\n")==0;
    if(staged_png) {
        if(niak_prepare_profile_png_file(
                "/app0/assets/niak-profile.png",pixels) ||
           niak_prepare_profile_png_file(
                "/data/homebrew/PPSA99386/assets/niak-profile.png",pixels)) {
            width=height=256;
            return true;
        }
    }
    char cache[200]{};
    std::snprintf(cache,sizeof(cache),
        "/system_data/priv/cache/profile/0x%08X/avatar.png",
        static_cast<unsigned>(current));
    if(niak_prepare_profile_png_file(cache,pixels)) {
        width=height=256;
        return true;
    }
    // Probe ONLY the foreground account's cache. The DDS reader is offline
    // and bounded to 2 MiB input and a maximum 512x512 RGBA result.
    char dds_path[240]{};
    for(const char *filename : {"avatar128.dds","avatar260.dds",
                                "avatar64.dds"}) {
        const int n=std::snprintf(dds_path,sizeof(dds_path),
            "/system_data/priv/cache/profile/0x%08X/%s",
            static_cast<unsigned>(current),filename);
        if(n<=0 || n>=static_cast<int>(sizeof(dds_path)))continue;
        if(prepare_dds_avatar(dds_path,width,height,pixels))return true;
    }
    if(staged_dds) {
        if(prepare_dds_avatar("/app0/assets/niak-profile.dds",
                              width,height,pixels) ||
           prepare_dds_avatar(
                "/data/homebrew/PPSA99386/assets/niak-profile.dds",
                width,height,pixels))return true;
    }
    return false;
}

struct AvatarReadState {
    std::mutex mutex;
    std::condition_variable wake;
    int selected_user=-1;
    int completed_user=-1;
    std::uint64_t generation=0;
    bool started=false,pending=false,in_flight=false,completed=false;
    std::vector<std::uint8_t> completed_pixels;
    int width=0,height=0;
};
AvatarReadState &avatar_state() {
    static auto *state=new AvatarReadState;
    return *state;
}
void avatar_reader() {
    auto &state=avatar_state();
    for(;;) {
        int user=-1;
        std::uint64_t epoch=0;
        {
            std::unique_lock<std::mutex> lock(state.mutex);
            state.wake.wait(lock,[&] {return state.pending;});
            user=state.selected_user;
            epoch=state.generation;
            state.pending=false;
            state.in_flight=true;
        }
        int width=0,height=0;
        std::vector<std::uint8_t> pixels;
        const bool ready=prepare_current_avatar(user,width,height,pixels);
        {
            std::lock_guard<std::mutex> lock(state.mutex);
            if(epoch!=state.generation || user!=state.selected_user)
                continue;
            state.in_flight=false;
            if(!ready)continue;
            state.completed_user=user;
            state.width=width;
            state.height=height;
            state.completed_pixels=std::move(pixels);
            state.completed=true;
        }
    }
}
void request_avatar_for(int current) {
    auto &state=avatar_state();
    std::lock_guard<std::mutex> lock(state.mutex);
    if(state.selected_user!=current) {
        state.selected_user=current;
        ++state.generation;
        state.completed=false;
        state.completed_pixels.clear();
        state.pending=false;
        state.in_flight=false;
    }
    if(state.pending || state.in_flight || state.completed)return;
    state.pending=true;
    if(!state.started) {
        state.started=true;
        std::thread([] {avatar_reader();}).detach();
    }
    state.wake.notify_one();
}
} // namespace

void niak_profile_load_avatar(hui::gfx::Renderer &renderer) {
    int current=-1;
    if(sceUserServiceGetForegroundUser(&current)!=0 || current<0)return;
    if(niak_user_avatar && current==niak_avatar_owner)return;
    // An account switch releases the prior user's texture immediately.
    if(niak_user_avatar)renderer.destroy_texture(niak_user_avatar);
    niak_user_avatar=0;
    niak_avatar_owner=-1;
    request_avatar_for(current);
}
std::uint32_t niak_profile_avatar() {
    if(!niak_user_avatar || niak_avatar_owner<0)return 0;
    int current=-1;
    // Never show the previous account's avatar after a profile switch.
    if(sceUserServiceGetForegroundUser(&current)!=0 ||
       current!=niak_avatar_owner)return 0;
    return niak_user_avatar;
}
void niak_profile_poll_avatar(hui::gfx::Renderer &renderer) {
    auto &state=avatar_state();
    int user=-1,w=0,h=0;
    std::vector<std::uint8_t> pixels;
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        if(!state.completed)return;
        user=state.completed_user;
        w=state.width;h=state.height;
        pixels=std::move(state.completed_pixels);
        state.completed=false;
    }
    int current=-1;
    if(sceUserServiceGetForegroundUser(&current)!=0 || current!=user ||
       w<16||h<16||w>512||h>512||
       pixels.size()!=std::size_t(w)*h*4u)return;
    const auto texture=renderer.create_texture(w,h,pixels.data());
    if(!texture)return;
    if(niak_user_avatar)renderer.destroy_texture(niak_user_avatar);
    niak_user_avatar=texture;
    niak_avatar_owner=user;
}
// Broker files may arrive AFTER startup. Recheck only once per 10 seconds;
// ordinary frames do no filesystem I/O, decoding or unnecessary GPU work.
void niak_profile_refresh_avatar(hui::gfx::Renderer &renderer) {
    static std::time_t checked_at=0;
    const std::time_t now=std::time(nullptr);
    if(checked_at && now>=checked_at && now-checked_at<10)return;
    checked_at=now;
    int current=-1;
    if(sceUserServiceGetForegroundUser(&current)!=0 || current<0)return;
    if(niak_user_avatar && current==niak_avatar_owner)return;
    niak_profile_load_avatar(renderer);
}
