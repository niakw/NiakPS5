#!/usr/bin/env python3
"""Host-only patches for the exact C++/OpenGL renderer used by NiakPS5."""
from pathlib import Path
import argparse
def one(path,old,new):
    data=path.read_text("utf8")
    if data.count(old)!=1:raise RuntimeError(f"Preview mismatch: {path}: {old[:80]}")
    path.write_text(data.replace(old,new,1),"utf8")
def patch(kit):
    main=kit/"host/snapshot_main.cpp"
    for original,new in (("inter-regular.huifont","niak-manrope.huifont"),
                         ("inter-semibold.huifont","niak-manrope.huifont"),
                         ("montserrat-medium.huifont","niak-instrument-serif.huifont")):
        one(main,original,new)
    catalog=kit/"src/demo/catalog.cpp"
    one(catalog,"Catalog::Catalog()\n{",'''Catalog::Catalog()
{
#ifdef __linux__
    // Offline host preview only. Never packaged in the native PS5 title.
    const char *names[]={"EA SPORTS FC 27","Humankind","Tropico 6",
                         "Anno 1800 Console Edition","NiakPS5"};
    const char *ids[]={"PPSA34015","PPSA06186","PPSA05683","PPSA04716","PPSA99386"};
    for(int n=0;n<5;++n) {
        owned_titles_.emplace_back(names[n]);
        Item item{};
        item.title=owned_titles_.back().c_str();
        item.studio="Aperçu hors console";
        item.genre=n==4?"HOMEBREW":"PS5";
        item.blurb="Aperçu C++/OpenGL hors console. Catalogue utilisateur non accessible.";
        item.homebrew=n==4;
        std::snprintf(item.title_id,sizeof(item.title_id),"%s",ids[n]);
        item.dark=gfx::Color::rgb(0x081719);
        item.mid=gfx::Color::rgb(0x183e44);
        item.accent=gfx::Color::rgb(0x91f5df);
        items_.push_back(item);
    }
    return;
#endif''')
    platform=kit/"host/platform_host.cpp"
    platform.write_text(platform.read_text("utf8")+'''
extern "C" int sceSystemServiceLaunchApp(const char*,const char**,void*){return -1;}
extern "C" int sceUserServiceGetForegroundUser(int *user){if(user)*user=1;return 0;}
extern "C" int sceUserServiceGetUserName(int,char *name,std::size_t capacity){
    if(name && capacity)std::snprintf(name,capacity,"Aperçu hôte");
    return 0;
}
''',"utf8")
    host=kit/"tools/host-snapshots.sh"
    contents=host.read_text("utf8")
    if "! -name main.cpp -print0" not in contents:
        raise RuntimeError("Host inputs changed")
    contents=contents.replace("! -name main.cpp -print0",
                              "! -name main.cpp ! -name localtime_compat.c -print0")
    term='"'+chr(36)+'{objects[@]}" -lEGL -lGL -lm -o'
    new='"'+chr(36)+'{objects[@]}" -lEGL -lGL -lsqlite3 -pthread -lm -o'
    if term not in contents:raise RuntimeError("Host linker args changed")
    host.write_text(contents.replace(term,new),"utf8")
if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("--kit",type=Path,required=True)
    patch(cli.parse_args().kit)
