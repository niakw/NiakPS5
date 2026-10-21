// SPDX-License-Identifier: GPL-3.0-or-later
// Only the current user's display name; never logs, persists or transmits it.
#include "niak/profile.hpp"
#include "niak/game_icons.hpp"
#include "gfx/renderer.hpp"
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
}
std::uint32_t niak_profile_avatar() {return niak_user_avatar;}
