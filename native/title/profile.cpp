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
int sceUserServiceGetInitialUser(int *user);
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
        if (sceUserServiceGetInitialUser(&user)==0 && user>=0 &&
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
    niak_user_avatar=niak_load_local_png(renderer, "/app0/assets/niak-profile.png");
    if(niak_user_avatar) return;
    // Fallback: the PS5 avatar cache commonly stores 128x128 DDS (DXT5).
    // Read only our own staged copy inside /app0, never a system path.
    std::FILE *file=std::fopen("/app0/assets/niak-profile.dds","rb");
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
