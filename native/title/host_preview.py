#!/usr/bin/env python3
"""Host-only patches for the exact C++/OpenGL renderer used by NiakPS5."""
from pathlib import Path
import argparse

def make_case_art_fixtures(kit):
    """Generate original QA textures to test actual front/back/spine UV mapping.

    This deliberately does not use or publish anybody's retail box scans.
    The native PS5 application still loads the owner's private LaunchBox scans.
    """
    from PIL import Image, ImageDraw, ImageFont
    output=kit/"assets"/"niak-preview-cases"
    output.mkdir(parents=True,exist_ok=True)
    source_font=Path(__file__).parents[1]/"assets"/"manrope.ttf"
    def font(size):
        return ImageFont.truetype(str(source_font),size) if source_font.is_file() else ImageFont.load_default()
    def gradient(w,h,upper,lower):
        im=Image.new("RGB",(w,h))
        d=ImageDraw.Draw(im)
        for y in range(h):
            t=y/max(h-1,1)
            d.line((0,y,w,y),fill=tuple(round(upper[i]*(1-t)+lower[i]*t) for i in range(3)))
        return im
    ident="PPSA34015"
    face=gradient(480,640,(13,34,66),(17,110,138))
    d=ImageDraw.Draw(face)
    d.rectangle((0,0,479,67),fill=(239,244,249))
    d.text((24,15),"PS5",fill=(17,28,44),font=font(43))
    d.line((0,67,479,67),fill=(22,88,158),width=4)
    d.polygon([(0,490),(140,280),(215,365),(334,162),(480,381),(480,640),(0,640)],
              fill=(10,42,91))
    d.ellipse((298,160,422,284),outline=(126,225,216),width=9)
    d.text((32,352),"BOÎTIER 3D",fill=(255,255,255),font=font(42))
    d.text((32,402),"APERÇU TECHNIQUE",fill=(202,236,242),font=font(23))
    d.text((32,587),"IMAGE DE CONTRÔLE — NON COMMERCIALE",
           fill=(225,242,245),font=font(15))
    face.save(output/f"{ident}-front.png",optimize=True)

    back=gradient(480,640,(228,234,239),(174,203,223))
    d=ImageDraw.Draw(back)
    d.text((28,22),"APERÇU DU VERSO",fill=(17,37,75),font=font(30))
    d.rounded_rectangle((23,80,457,335),radius=12,fill=(15,51,87))
    d.polygon([(42,312),(146,164),(225,243),(319,107),(439,286),(439,314)],
              fill=(43,129,159))
    d.ellipse((320,114,405,199),outline=(146,223,226),width=6)
    d.text((27,370),"Face arrière : texture distincte",
           fill=(21,44,82),font=font(21))
    d.text((27,408),"Perspective, coins, tranche et épaisseur",
           fill=(31,59,88),font=font(17))
    for y in (460,475,490):
        d.line((26,y,453,y),fill=(69,98,128),width=2)
    # A synthetic barcode makes mirror/UV orientation errors obvious.
    for x in range(290,453,5):
        if x%3:d.line((x,548,x,600),fill=(16,35,66),width=2)
    d.text((24,610),"QA ASSET — NOT RETAIL ART",fill=(18,36,71),font=font(13))
    back.save(output/f"{ident}-back.png",optimize=True)

    spine=gradient(44,640,(230,240,250),(92,149,202))
    d=ImageDraw.Draw(spine)
    d.rectangle((0,0,43,640),outline=(24,85,174),width=3)
    d.text((13,15),"P",fill=(18,35,74),font=font(23))
    d.text((13,50),"S",fill=(18,35,74),font=font(23))
    d.text((13,85),"5",fill=(18,35,74),font=font(23))
    d.line((10,145,10,580),fill=(27,103,175),width=4)
    spine.save(output/f"{ident}-spine.png",optimize=True)
    # Original QA art only; same no-gap atlas generator as private FTP.
    from ftp_install import _compose_case_wrap
    components={side:(output/f"{ident}-{side}.png").read_bytes()
                for side in ("front","spine","back")}
    wrap=_compose_case_wrap(components)
    if wrap is None:raise RuntimeError("Continuous preview sleeve failed")
    (output/f"{ident}-wrap.png").write_bytes(wrap)

def one(path,old,new):
    data=path.read_text("utf8")
    if data.count(old)!=1:raise RuntimeError(f"Preview mismatch: {path}: {old[:80]}")
    path.write_text(data.replace(old,new,1),"utf8")
def patch(kit):
    make_case_art_fixtures(kit)
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
    # Host renderer must load the same downloaded PS5 wallpapers as the
    # deployed title. Preview absolute paths differ from /app0.
    one(main,'#include "demo/catalog.hpp"',
        '#include "demo/catalog.hpp"\n#include "niak/daily_backdrop.hpp"')
    one(main,'    hui::demo::Catalog catalog;',
        '    niak_load_daily_backdrops(renderer,(assets+"/niak-daily").c_str());\n    hui::demo::Catalog catalog;')
    platform=kit/"host/platform_host.cpp"
    platform.write_text(platform.read_text("utf8")+'''
extern "C" int sceSystemServiceLaunchApp(const char*,const char**,void*){return -1;}
extern "C" int sceUserServiceGetForegroundUser(int *user){if(user)*user=1;return 0;}
extern "C" int sceUserServiceGetUserName(int,char *name,std::size_t capacity){
    if(name && capacity)std::snprintf(name,capacity,"Aperçu hôte");
    return 0;
}
''',"utf8")
    # The same selected case is photographed at four real animation angles.
    # Advance the actual Aurora UI's C++ clock; no synthetic image rotation.
    one(main, '    if (const char *strip = std::getenv("HUI_STRIP"))', """    if (std::getenv("NIAK_CASE_TOUR")) {
        hui::InputFrame idle;
        idle.connected = true;
        shell.show(0, false);
        for(int frame=0;frame<715;++frame) {
            shell.update(idle,kDt);
            if(frame==90)render("case-00-front");
            if(frame==180)render("case-01-unlatch");
            if(frame==248)render("case-02-open");
            if(frame==348)render("case-03-close");
            if(frame==420)render("case-04-turn");
            if(frame==540)render("case-05-back");
            if(frame==690)render("case-06-return");
        }
        return ok ? 0 : 1;
    }
    if (const char *strip = std::getenv("HUI_STRIP"))""")
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
