// SPDX-License-Identifier: GPL-3.0-or-later
// Only the current user's display name; never logs, persists or transmits it.
#include "niak/profile.hpp"
#include "niak/game_icons.hpp"
#include "gfx/renderer.hpp"
#include "niak/avatar_dds.hpp"
#include <vector>
#include <array>
#include <sys/stat.h>
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

/* A marker only authorizes an image from the SAME source directory.
 * Never combine a new foreground user's marker with an older /app0 image
 * from another installation or account.
 */
bool matching_avatar_marker(const char *path,int current,const char *format) {
    char expected[32]{};
    const int length=std::snprintf(expected,sizeof(expected),
                        "0x%08X %s\n",static_cast<unsigned>(current),format);
    if(length<=0||length>=static_cast<int>(sizeof(expected)))return false;
    std::FILE *file=std::fopen(path,"rb");
    if(!file)return false;
    char observed[32]{};
    const std::size_t read=std::fread(observed,1,sizeof(observed),file);
    const bool complete=std::feof(file)!=0;
    std::fclose(file);
    return complete && read==static_cast<std::size_t>(length) &&
           std::memcmp(observed,expected,read)==0;
}

bool prepare_current_avatar(int current,int &width,int &height,
                            std::vector<std::uint8_t> &pixels) {
    const bool data_png=matching_avatar_marker(
        "/data/NiakPS5/assets/niak-profile-source.txt",
        current,"png");
    const bool app_png=matching_avatar_marker(
        "/app0/assets/niak-profile-source.txt",current,"png");
    const bool data_dds=matching_avatar_marker(
        "/data/NiakPS5/assets/niak-profile-source.txt",
        current,"dds");
    const bool app_dds=matching_avatar_marker(
        "/app0/assets/niak-profile-source.txt",current,"dds");
    // The broker's current private staging takes precedence. A fallback
    // package image is allowed only with its OWN matching owner/type marker.
    if((data_png && niak_prepare_profile_png_file(
           "/data/NiakPS5/assets/niak-profile.png",pixels)) ||
       (app_png && niak_prepare_profile_png_file(
           "/app0/assets/niak-profile.png",pixels))) {
        width=height=256;
        return true;
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
    for(const char *filename : {"avatar440.dds","avatar260.dds",
                                "avatar128.dds","avatar64.dds"}) {
        const int n=std::snprintf(dds_path,sizeof(dds_path),
            "/system_data/priv/cache/profile/0x%08X/%s",
            static_cast<unsigned>(current),filename);
        if(n<=0 || n>=static_cast<int>(sizeof(dds_path)))continue;
        if(prepare_dds_avatar(dds_path,width,height,pixels))return true;
    }
    if((data_dds && prepare_dds_avatar(
           "/data/NiakPS5/assets/niak-profile.dds",
           width,height,pixels)) ||
       (app_dds && prepare_dds_avatar(
           "/app0/assets/niak-profile.dds",width,height,pixels)))
        return true;
    return false;
}

// Only the current account's five source-cache files plus the six
// application-local avatar files are observed. Stat runs on the avatar CPU
// worker, not the GPU/input thread, so FTP replacement is cheap to detect.
struct AvatarFileStamp {
    std::uint64_t size=0,mtime=0,ctime=0,inode=0;
    bool regular=false;
    bool operator==(const AvatarFileStamp &other)const {
        return size==other.size && mtime==other.mtime &&
               ctime==other.ctime && inode==other.inode &&
               regular==other.regular;
    }
};
using AvatarFileStamps=std::array<AvatarFileStamp,11>;
AvatarFileStamp avatar_file_stamp(const char *path) {
    struct stat st{};
    if(::stat(path,&st)!=0 || !S_ISREG(st.st_mode))return {};
    return {static_cast<std::uint64_t>(st.st_size),
            static_cast<std::uint64_t>(st.st_mtime),
            static_cast<std::uint64_t>(st.st_ctime),
            static_cast<std::uint64_t>(st.st_ino),true};
}
AvatarFileStamps read_avatar_source_stamps(int current) {
    AvatarFileStamps stamps{};
    static const char *const private_files[]={
        "/data/NiakPS5/assets/niak-profile-source.txt",
        "/data/NiakPS5/assets/niak-profile.png",
        "/data/NiakPS5/assets/niak-profile.dds",
        "/app0/assets/niak-profile-source.txt",
        "/app0/assets/niak-profile.png",
        "/app0/assets/niak-profile.dds"};
    for(std::size_t i=0;i<6;++i)stamps[i]=avatar_file_stamp(private_files[i]);
    static const char *const native_files[]={
        "avatar.png","avatar440.dds","avatar260.dds",
        "avatar128.dds","avatar64.dds"};
    if(current>=0)for(std::size_t i=0;i<5;++i) {
        char path[240]{};
        const int n=std::snprintf(path,sizeof(path),
            "/system_data/priv/cache/profile/0x%08X/%s",
            static_cast<unsigned>(current),native_files[i]);
        if(n>0 && n<static_cast<int>(sizeof(path)))
            stamps[i+6]=avatar_file_stamp(path);
    }
    return stamps;
}
struct AvatarReadState {
    std::mutex mutex;
    std::condition_variable wake;
    int selected_user=-1;
    int completed_user=-1;
    std::uint64_t generation=0;
    bool started=false,pending=false,in_flight=false,completed=false;
    bool texture_live=false,have_stamps=false;
    AvatarFileStamps observed_stamps{};
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
        // A new staged avatar may arrive while a previously displayed
        // image remains cached. Probe only metadata on this worker. Decode
        // and re-upload ONLY when the owner's source files have changed.
        const AvatarFileStamps stamps=read_avatar_source_stamps(user);
        {
            std::lock_guard<std::mutex> lock(state.mutex);
            if(epoch!=state.generation || user!=state.selected_user)
                continue;
            if(state.texture_live && state.have_stamps &&
               stamps==state.observed_stamps) {
                state.in_flight=false;
                continue;
            }
        }
        int width=0,height=0;
        std::vector<std::uint8_t> pixels;
        const bool ready=prepare_current_avatar(user,width,height,pixels);
        {
            std::lock_guard<std::mutex> lock(state.mutex);
            if(epoch!=state.generation || user!=state.selected_user)
                continue;
            state.in_flight=false;
            state.observed_stamps=stamps;
            state.have_stamps=true;
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
        state.texture_live=false;
        state.have_stamps=false;
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
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        if(state.selected_user==user)state.texture_live=true;
    }
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
    if(niak_user_avatar && current==niak_avatar_owner) {
        // A successful avatar is no longer a permanent cache miss for
        // future FTP updates. The worker checks source file stamps without
        // loading an image or touching the renderer when nothing changed.
        request_avatar_for(current);
        return;
    }
    niak_profile_load_avatar(renderer);
}
