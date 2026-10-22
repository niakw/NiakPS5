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

    # Give EVERY preview-only title its own original illustration. The older
    # snapshot left non-FC titles as solid blue rectangles, which masked visual
    # defects and suggested that real LaunchBox art was missing on console.
    # These synthetic QA assets never ship with the PS5 application.
    examples=(
        ("PPSA06186","HUMANKIND",(34,63,92),(112,155,178)),
        ("PPSA05683","TROPICO 6",(29,85,88),(155,180,90)),
        ("PPSA04716","ANNO 1800",(39,53,94),(151,116,76)),
    )
    for title_id,caption,color_a,color_b in examples:
        front=gradient(480,640,color_a,color_b)
        paint=ImageDraw.Draw(front)
        paint.rectangle((0,0,479,68),fill=(244,247,253))
        paint.text((22,13),"PS5",fill=(20,40,70),font=font(43))
        paint.line((0,68,479,68),fill=(22,91,176),width=3)
        paint.ellipse((180,154,450,424),outline=(230,249,248),width=10)
        paint.polygon([(30,476),(180,288),(244,372),(355,222),(458,404),
                       (458,546),(30,546)],fill=(15,36,80))
        paint.text((32,110),caption,fill=(255,255,255),font=font(36))
        paint.text((32,565),"APERÇU HÔTE / VISUEL NON OFFICIEL",
                   fill=(241,252,255),font=font(17))
        front.save(output/f"{title_id}-front.png",optimize=True)
        rear=gradient(480,640,(235,240,247),(161,192,217))
        paint=ImageDraw.Draw(rear)
        paint.text((30,40),caption,fill=(15,50,88),font=font(33))
        paint.rectangle((30,110,450,375),fill=(20,62,100))
        paint.polygon([(50,341),(154,190),(239,280),(354,148),(430,330)],
                      fill=(57,154,176))
        paint.text((29,410),"APERÇU TECHNIQUE DU VERSO",fill=(19,58,88),
                   font=font(22))
        paint.text((29,610),"VISUEL DE TEST / NON COMMERCIAL",
                   fill=(19,58,88),font=font(16))
        rear.save(output/f"{title_id}-back.png",optimize=True)
        side=gradient(44,640,(228,244,255),(74,145,213))
        paint=ImageDraw.Draw(side)
        paint.rectangle((0,0,43,639),outline=(22,80,156),width=3)
        for index,letter in enumerate("PS5"):
            paint.text((13,12+index*40),letter,fill=(12,49,108),
                       font=font(24))
        paint.line((11,172,11,585),fill=(31,99,177),width=3)
        side.save(output/f"{title_id}-spine.png",optimize=True)


    # Synthetic, non-branded QA overlays verify the *real* private-template
    # decoder, UV placement and cache. These are NOT copied to PS5 packages.
    templates=kit/"assets"/"niak-preview-templates"
    templates.mkdir(parents=True,exist_ok=True)
    for family,tint in (("ps4",(14,78,163)),("ps5",(232,242,251))):
        header=gradient(720,104,tint,tuple(min(255,n+15) for n in tint))
        painter=ImageDraw.Draw(header)
        painter.text((38,30),family.upper()+"  /  QA HEADER",
                     fill=(255,255,255) if family=="ps4" else (19,51,87),
                     font=font(40))
        header.save(templates/f"{family}-front.png",optimize=True)
        footer=gradient(720,295,(224,235,246),(165,188,212))
        painter=ImageDraw.Draw(footer)
        painter.rectangle((20,20,700,275),outline=(18,57,102),width=5)
        painter.text((38,48),family.upper()+" / QA FOOTER",fill=(25,61,108),
                     font=font(33))
        footer.save(templates/f"{family}-back.png",optimize=True)
        spine=gradient(68,820,tint,(25,49,83))
        painter=ImageDraw.Draw(spine)
        for i,letter in enumerate(family.upper()):
            painter.text((17,24+i*54),letter,fill=(255,255,255),
                         font=font(29))
        spine.save(templates/f"{family}-spine.png",optimize=True)

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
    const char *names[]={"EA SPORTS FC 27","Humankind","ZZZ PS4 boxed demo",
                         "Anno 1800 Console Edition","NiakPS5"};
    const char *ids[]={"PPSA34015","PPSA06186","CUSA00053","PPSA04716","PPSA99386"};
    for(int n=0;n<5;++n) {
        owned_titles_.emplace_back(names[n]);
        Item item{};
        item.title=owned_titles_.back().c_str();
        item.studio="Aperçu hors console";
        item.genre=n==4?"HOMEBREW":"PS5";
        item.blurb="Aperçu C++/OpenGL hors console. Catalogue utilisateur non accessible.";
        item.homebrew=n==4;
        item.application=n==4; // Exercise the real apps/homebrew second row.
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
    # Capture a SEALED case from four real OpenGL angles, never its inside.
    one(main, '    if (const char *strip = std::getenv("HUI_STRIP"))', """    if (std::getenv("NIAK_CASE_TOUR")) {
        hui::InputFrame idle;
        idle.connected = true;
        shell.show(0, false);
        for(int frame=0;frame<475;++frame) {
            if(frame==91) {
                hui::InputFrame r1;
                r1.connected=true;
                r1.pressed=hui::action_bit(hui::Action::page_next);
                shell.update(r1,kDt);
                render("case-05-wallpaper-r1");
            } else shell.update(idle,kDt);
            if(frame==90)render("case-00-front");
            if(frame==202)render("case-01-spine");
            if(frame==330)render("case-02-back");
            if(frame==445)render("case-03-return");
        }
        // Visit the real Applications/homebrew shelf. The fifth title has
        // NO retail scans, intentionally testing the generic physical box.
        hui::InputFrame next;
        next.connected=true;
        next.nav=hui::Direction::down;
        shell.update(next,kDt);
        for(int frame=0;frame<100;++frame) shell.update(idle,kDt);
        render("case-04-homebrew-fallback");
        // Visit PS4 first-shelf item with no scans; real platform header and
        // private back footer must be mapped in the same renderer.
        hui::InputFrame up;
        up.connected=true;
        up.nav=hui::Direction::up;
        shell.update(up,kDt);
        for(int frame=0;frame<20;++frame)shell.update(idle,kDt);
        hui::InputFrame right;
        right.connected=true;
        right.nav=hui::Direction::right;
        for(int move=0;move<4;++move) {
            shell.update(right,kDt);
            for(int frame=0;frame<20;++frame)shell.update(idle,kDt);
        }
        render("case-07-ps4-template-front");
        for(int frame=0;frame<235;++frame)shell.update(idle,kDt);
        render("case-08-ps4-template-back");
        hui::InputFrame down;
        down.connected=true;
        down.nav=hui::Direction::down;
        shell.update(down,kDt);
        for(int frame=0;frame<25;++frame)shell.update(idle,kDt);
        hui::InputFrame touchpad;
        touchpad.connected=true;
        touchpad.pressed=hui::action_bit(hui::Action::touch);
        shell.update(touchpad,kDt);
        for(int frame=0;frame<32;++frame) shell.update(idle,kDt);
        render("case-06-touchpad-details");
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
