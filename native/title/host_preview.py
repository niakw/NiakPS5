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
        # QA: Humankind has genuine front but NO retail back; Anno has
        # genuine back but NO retail front. Independent fallbacks must show
        # each missing face without overwriting the other authentic side.
        if title_id not in ("PPSA04716","PPSA06186"):
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
        if title_id!="PPSA06186":
            rear.save(output/f"{title_id}-back.png",optimize=True)
        side=gradient(44,640,(228,244,255),(74,145,213))
        paint=ImageDraw.Draw(side)
        paint.rectangle((0,0,43,639),outline=(22,80,156),width=3)
        for index,letter in enumerate("PS5"):
            paint.text((13,12+index*40),letter,fill=(12,49,108),
                       font=font(24))
        paint.line((11,172,11,585),fill=(31,99,177),width=3)
        # Humankind has no scanned spine: force the real PS5 fixed template
        # to appear on the rotated physical sleeve in the standard artifact.
        # FC27/Anno/Tropico keep their separate existing spine scans.
        if title_id!="PPSA06186":
            side.save(output/f"{title_id}-spine.png",optimize=True)


    # The STANDARD GitHub artifact MUST render the user's actual PS4/PS5
    # visual blocks, not procedural QA HEADER / QA FOOTER substitutes.
    # A visually compressed CI copy is versioned as six ASCII chunks; the
    # original, full-resolution owner ZIP is not included in PS5 packages.
    from base64 import b64decode
    from hashlib import sha256
    from io import BytesIO
    from zipfile import ZipFile
    parts=Path(__file__).resolve().parent/"assets"/"preview-blocks"
    sources=[parts/f"{i:02}.b64" for i in range(6)]
    if not all(p.is_file() for p in sources):
        raise RuntimeError("Six real PS4/PS5 preview blocks missing; fake QA fallback forbidden")
    archive=b64decode("".join(p.read_text("ascii").strip() for p in sources),
                      validate=True)
    if sha256(archive).hexdigest()!="cd3383fa7705ec19ebfbb5923d67d75c9c9c3fd2c290b91edd562c2792c0ecc4":
        raise RuntimeError("PS4/PS5 preview block source hash mismatch")
    templates=kit/"assets"/"niak-preview-templates"
    templates.mkdir(parents=True,exist_ok=True)
    expected={f"{family}-{side}.webp"
              for family in ("ps4","ps5")
              for side in ("front","back","spine")}
    with ZipFile(BytesIO(archive)) as source:
        if set(source.namelist())!=expected or source.testzip() is not None:
            raise RuntimeError("Missing/corrupt branded template in CI source")
        for name in sorted(expected):
            with source.open(name) as data:
                asset=Image.open(data)
                asset.load()
                if asset.format!="WEBP":
                    raise RuntimeError("Invalid PS4/PS5 original-preview visual")
                asset.convert("RGBA").save(
                    templates/name.replace(".webp",".png"),optimize=True)
    # Human-readable proof INSIDE THE SAME STANDARD ARTIFACT:
    # six fixed pieces shown by platform, independently of tiny 3D sleeves.
    proof=Image.new("RGB",(1920,1080),(17,23,35))
    labels=ImageDraw.Draw(proof)
    labels.text((60,25),"BLOCS FIXES PS4 / PS5 — SOURCES FOURNIES",
                fill=(248,249,252),font=font(40))
    for family,left in (("ps4",60),("ps5",1000)):
        labels.text((left,94),family.upper(),fill=(238,242,252),font=font(36))
        for side,box in (
            ("front",(left,165,left+840,295)),
            ("back",(left,330,left+670,790)),
            ("spine",(left+725,330,left+860,920)),
        ):
            asset=Image.open(templates/f"{family}-{side}.png").convert("RGB")
            x0,y0,x1,y1=box
            scale=min((x1-x0)/asset.width,(y1-y0)/asset.height)
            asset=asset.resize((max(1,round(asset.width*scale)),
                                max(1,round(asset.height*scale))),
                               Image.Resampling.LANCZOS)
            proof.paste(asset,(x0,y0))
            labels.text((x0,y1+8),{"front":"Bandeau","back":"Dos fixe",
                                      "spine":"Tranche"}[side],
                        fill=(175,190,207),font=font(25))
    proof.save(templates/"00-fixed-elements-PS4-PS5.png",optimize=True)
    print("NIAK_CASE_ORIGINAL_BLOCKS: six real user-supplied fixed elements loaded")

    # Exercise true full-bleed composition with distinct LANDSCAPE screenshots
    # and genuine alpha logos. Real PS5 loads owner-installed icon0/pic1.
    media=kit/"assets"/"niak-preview-media"
    media.mkdir(parents=True,exist_ok=True)
    for game,name,hue in (
        ("PPSA06186","HUMANKIND",(18,110,130)),
        ("PPSA04716","ANNO 1800",(157,113,65)),
        ("CUSA00053","SHADOWFALL",(74,105,154)),
        ("PPSA99386","NIAK",(33,112,164)),
    ):
        scene=gradient(1024,576,(14,28,55),hue)
        draw=ImageDraw.Draw(scene)
        draw.polygon([(0,540),(180,290),(420,420),(690,120),(1024,390),
                      (1024,576),(0,576)],fill=(15,42,83))
        draw.ellipse((650,130,885,365),outline=(204,231,219),width=19)
        draw.text((36,40),name,fill=(248,248,248),font=font(55))
        scene.save(media/f"{game}-scene.png",optimize=True)
        icon=gradient(512,512,(20,47,93),hue)
        draw=ImageDraw.Draw(icon)
        draw.rounded_rectangle((50,80,462,448),radius=30,
                               outline=(234,244,252),width=9)
        draw.text((40,213),name[:12],font=font(42),fill=(247,253,255))
        icon.save(media/f"{game}-icon.png",optimize=True)
        logo=Image.new("RGBA",(512,140),(0,0,0,0))
        draw=ImageDraw.Draw(logo)
        draw.text((25,28),name,font=font(49),
                  fill=(245,250,255,255),stroke_width=2,
                  stroke_fill=(12,30,52,240))
        logo.save(output/f"{game}-logo.png",optimize=True)

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
    // Two deterministic titles WITHOUT official scans. Their PS4/PS5
    // mastheads, legal backs and spines are rendered from fixed templates.
    const char *names[]={"SHADOWFALL","Humankind"};
    const char *ids[]={"CUSA00053","PPSA06186"};
    for(int n=0;n<2;++n) {
        owned_titles_.emplace_back(names[n]);
        Item item{};
        item.title=owned_titles_.back().c_str();
        item.studio="Aperçu hors console";
        item.genre=ids[n][0]=='C'?"PS4":"PS5";
        item.blurb="Un jeu d'aventure avec des environnements varies, "
                   "des personnages et des captures de gameplay.";
        item.homebrew=false;
        item.application=false;
        // The real shelf sorts by most-recent play, then alphabetically.
        // "Humankind" otherwise sorts BEFORE "SHADOWFALL" and silently
        // swaps PS4/PS5 filenames in the six-capture artifact.
        // Explicit local-only timestamps guarantee PS4 at shelf index 0.
        std::snprintf(item.recently_used,sizeof(item.recently_used),"%s",
                      n==0?"2026-10-23T12:00:00":"2026-10-22T12:00:00");
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
        '#include "demo/catalog.hpp"\n#include "niak/daily_backdrop.hpp"\n#include "niak/asset_stats.hpp"')
    # Host QA takes snapshots of several titles after their graphics have
    # reached the GPU. The real PS5 stream remains incremental; only the
    # OFFLINE preview fixture is drained before starting screenshot tours.
    one(main, '    // HUI_ICON=<file.png>: draw the 512x512 launcher icon with the kit and stop.',
        '''    // Force both missing faces and their fixed back/spine overlays.
    // These counters represent genuine retail scans, not mockups.
    (void)catalog.stream_next_covers(renderer,fonts,catalog.size());
    const auto &media=niak::case_media_stats;
    if(media.titles!=2 || media.fronts!=0 || media.backs!=0 ||
       media.spines!=0) {
        std::fprintf(stderr,
            "six-view fixtures invalid: titles=%u front=%u back=%u spine=%u templates=%u\\n",
            media.titles,media.fronts,media.backs,media.spines,media.templates);
        return 1;
    }
    // HUI_ICON=<file.png>: draw the 512x512 launcher icon with the kit and stop.''')
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
    one(main, '    if (const char *strip = std::getenv("HUI_STRIP"))', """    if (std::getenv("NIAK_HOME_PREVIEW")) {
        // Screenshot of the actual native OpenGL HOME surface, not a
        // marketing mockup. Host test titles/media are explicit fixtures.
        hui::InputFrame idle;
        idle.connected=true;
        shell.show(0,false);
        for(int n=0;n<120;++n)shell.update(idle,kDt);
        render("niakps5-home");
        return ok ? 0 : 1;
    }
    if (std::getenv("NIAK_CASE_TOUR")) {
        // Exactly TWO titles, one PS4 then one PS5: no commercial box
        // scans for any of their three faces. These are real GL snapshots.
        hui::InputFrame idle;
        idle.connected=true;
        shell.show(0,false);
        auto capture=[&](const std::string &platform) {
            // yaw_at(): front held through 2.7 s, spine near 3.375 s,
            // back fully visible after 4.05 s. Stable positions only.
            for(int n=0;n<20;++n)shell.update(idle,kDt);
            render(platform+"-front");
            for(int n=20;n<203;++n)shell.update(idle,kDt);
            render(platform+"-spine");
            for(int n=203;n<270;++n)shell.update(idle,kDt);
            render(platform+"-back");
        };
        capture("ps4");
        hui::InputFrame right;
        right.connected=true;
        right.nav=hui::Direction::right;
        shell.update(right,kDt);
        capture("ps5");
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
