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
extern "C" {
int sceUserServiceGetForegroundUser(int *user);
int sceUserServiceGetUserName(int user, char *name, std::size_t capacity);
}
const char *niak_ps5_user_label()
{
    static bool initialized=false;
    static char label[72]="Profil PS5 indisponible";
    if (!initialized)
    {
        initialized=true;
        int user=-1;
        char name[64]{};
        if (sceUserServiceGetForegroundUser(&user)==0 && user>=0 &&
            sceUserServiceGetUserName(user,name,sizeof(name))==0 &&
            name[0] && std::strlen(name)<sizeof(name))
        {
            std::snprintf(label,sizeof(label),"%s",name);
        }
    }
    return label;
}

static std::uint32_t niak_user_avatar=0;
void niak_profile_load_avatar(hui::gfx::Renderer &renderer)
{
    niak_user_avatar=0;
    int current=-1;
    if(sceUserServiceGetForegroundUser(&current)!=0 || current<0)return;
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
    if(niak_user_avatar || !staged_dds)return;
    std::FILE *file=std::fopen(
        "/data/homebrew/PPSA99386/assets/niak-profile.dds","rb");
    if(!file)return;
    if(std::fseek(file,0,SEEK_END)!=0){std::fclose(file);return;}
    const long size=std::ftell(file);
    if(size<144||size>2*1024*1024||std::fseek(file,0,SEEK_SET)!=0)
    {std::fclose(file);return;}
    std::vector<std::uint8_t> encoded(static_cast<std::size_t>(size));
    const bool ok=std::fread(encoded.data(),1,encoded.size(),file)==encoded.size();
    std::fclose(file);
    if(!ok)return;
    int width=0,height=0;
    std::vector<std::uint8_t> rgba;
    if(niak_decode_avatar_dds(encoded.data(),encoded.size(),width,height,rgba))
        niak_user_avatar=renderer.create_texture(width,height,rgba.data());
}
std::uint32_t niak_profile_avatar() {return niak_user_avatar;}
