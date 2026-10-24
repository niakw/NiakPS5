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

static std::uint32_t niak_load_dds_avatar(
    hui::gfx::Renderer &renderer,const char *path) {
    std::FILE *file=std::fopen(path,"rb");
    if(!file)return 0;
    if(std::fseek(file,0,SEEK_END)!=0){std::fclose(file);return 0;}
    const long size=std::ftell(file);
    if(size<144||size>2*1024*1024||std::fseek(file,0,SEEK_SET)!=0)
    {std::fclose(file);return 0;}
    std::vector<std::uint8_t> encoded(static_cast<std::size_t>(size));
    const bool ok=std::fread(encoded.data(),1,encoded.size(),file)==encoded.size();
    std::fclose(file);
    if(!ok)return 0;
    int width=0,height=0;
    std::vector<std::uint8_t> rgba;
    if(!niak_decode_avatar_dds(encoded.data(),encoded.size(),width,height,rgba))
        return 0;
    return renderer.create_texture(width,height,rgba.data());
}
static std::uint32_t niak_user_avatar=0;
static int niak_avatar_owner=-1;
void niak_profile_load_avatar(hui::gfx::Renderer &renderer)
{
    // A foreground-user switch must never leak an old account's GPU texture.
    if(niak_user_avatar)renderer.destroy_texture(niak_user_avatar);
    niak_user_avatar=0;
    niak_avatar_owner=-1;
    int current=-1;
    if(sceUserServiceGetForegroundUser(&current)!=0 || current<0)return;
    niak_avatar_owner=current;
    char identity[16]{};
    std::snprintf(identity,sizeof(identity),"0x%08X",
                  static_cast<unsigned>(current));
    // Generic staged assets without a matching owner AND format are unsafe:
    // the console may have changed active users since the last FTP install.
    char marker[32]{};
    std::FILE *owner=std::fopen(
        "/data/homebrew/PPSA99386/assets/niak-profile-source.txt","rb");
    if(owner) {
        (void)std::fgets(marker,sizeof(marker),owner);
        std::fclose(owner);
    }
    const bool identified=std::strncmp(marker,identity,10)==0 && marker[10]==' ';
    const bool staged_png=identified && std::strcmp(marker+11,"png\n")==0;
    const bool staged_dds=identified && std::strcmp(marker+11,"dds\n")==0;
    if(staged_png)
        niak_user_avatar=niak_load_local_png(renderer,
            "/data/homebrew/PPSA99386/assets/niak-profile.png");
    if(!niak_user_avatar)
        niak_user_avatar=niak_load_profile_cache_png(renderer,
            static_cast<unsigned>(current));
    // A manually launched title may not have a staged profile image.
    // Probe ONLY the current foreground account's local DDS cache. This
    // is read-only and requires no payload or private image export.
    if(!niak_user_avatar) {
        char dds_path[240];
        for(const char *filename : {"avatar128.dds","avatar260.dds",
                                    "avatar64.dds"}) {
            const int count=std::snprintf(dds_path,sizeof(dds_path),
                "/system_data/priv/cache/profile/0x%08X/%s",
                static_cast<unsigned>(current),filename);
            if(count<=0 || count>=static_cast<int>(sizeof(dds_path)))continue;
            niak_user_avatar=niak_load_dds_avatar(renderer,dds_path);
            if(niak_user_avatar)break;
        }
    }
    if(!niak_user_avatar && staged_dds)
        niak_user_avatar=niak_load_dds_avatar(renderer,
            "/data/homebrew/PPSA99386/assets/niak-profile.dds");
}
std::uint32_t niak_profile_avatar() {
    if(!niak_user_avatar || niak_avatar_owner<0)return 0;
    // Never display the previous user's texture after an account switch.
    // A new profile can stage/reload its own image on the next app start.
    int current=-1;
    if(sceUserServiceGetForegroundUser(&current)!=0 ||
       current!=niak_avatar_owner)return 0;
    return niak_user_avatar;
}

// Files exported by the privileged local broker may arrive AFTER the GUI
// starts. Retry only while the user is idle, at most once every ten seconds.
// Never substitute a different user's avatar or create a fake PSN icon.
void niak_profile_refresh_avatar(hui::gfx::Renderer &renderer)
{
    static std::time_t checked_at=0;
    const std::time_t now=std::time(nullptr);
    if(checked_at && now>=checked_at && now-checked_at<10)return;
    checked_at=now;
    int current=-1;
    if(sceUserServiceGetForegroundUser(&current)!=0 || current<0)return;
    if(niak_user_avatar && current==niak_avatar_owner)return;
    niak_profile_load_avatar(renderer);
}
