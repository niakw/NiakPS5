#!/usr/bin/env python3
"""Build a safe PS4/PS5 LaunchBox retail metadata index from Metadata.zip.
Adapted to the same regional-front/back/spine model as Eden Encore.
Only text, IDs and CDN image filenames are shipped, never retail scans.
"""
from __future__ import annotations
import argparse,html,re,unicodedata,urllib.request,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

SOURCE="https://gamesdb.launchbox-app.com/Metadata.zip"
IMAGE=re.compile(r"^(?:r2_)?[A-Fa-f0-9-]{36}\.(?:png|jpe?g)$")
KINDS={"Box - Front":"front","Box - Back":"back","Box - Spine":"spine",
       "Fanart - Box - Front":"front_fanart",
       "Fanart - Box - Back":"back_fanart",
       "Clear Logo":"logo", "Fanart - Background":"hero",
       "Screenshot - Gameplay":"gameplay",
       "Screenshot - Game Title":"game_title"}
PLATFORMS={"Sony Playstation 4":"ps4","Sony Playstation 5":"ps5",
           "Sony PlayStation 4":"ps4","Sony PlayStation 5":"ps5",
           "Windows":"windows","Windows PC":"windows"}
REGIONS={"france":"fr","europe":"eu","world":"world","united kingdom":"uk",
         "north america":"us","united states":"us","canada":"ca","germany":"de",
         "japan":"jp","spain":"es","italy":"it","portugal":"pt"}
ORDER=("fr","eu","world","uk","ca","us","de","es","it","pt","jp","other")

def normalize(name):
    name=unicodedata.normalize("NFKD",str(name)).encode("ascii","ignore").decode()
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9]+"," ",name.lower())).strip()

# A PS5 physical edition can be catalogued under the base title in
# LaunchBox. Strip ONLY platform descriptors, never the year, numbered
# sequel, Deluxe/Ultimate suffix or substantive edition name.
IGNORABLE_SUFFIXES=(" console edition"," playstation 5 edition",
                    " playstation 4 edition"," ps5 edition"," ps4 edition")
def safe_titles(name):
    exact=normalize(name)
    variants=[exact] if exact else []
    for suffix in IGNORABLE_SUFFIXES:
        if exact.endswith(suffix):
            base=exact[:-len(suffix)]
            if len(base)>=5 and any(c.isalpha() for c in base):
                variants.append(base)
    return tuple(dict.fromkeys(variants))

def clean_overview(notes):
    """Only a short, sourced description, never the complete LaunchBox essay."""
    text=re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",str(notes)))).strip()
    sentences=re.split(r"(?<=[.!?])\s+",text)
    return " ".join(sentences[:3])[:360].rstrip()
def targets(path):
    index={}
    with Path(path).open(encoding="utf8") as f:
        for line in f:
            columns=line.rstrip("\r\n").split("\t")
            if len(columns)<2:continue
            title, name=columns[:2]
            if len(title)!=9 or title[:4] not in ("PPSA","CUSA"):continue
            key=normalize(name)
            if key:index.setdefault((("ps5" if title.startswith("PPSA") else "ps4"),key),[]).append(title)
    return index

def region(value):return REGIONS.get(str(value).strip().lower(),"other")
def face_options(entries):
    out=[]
    for area in ORDER:
        group=[name for where,name in entries if where==area]
        for name in group[:2]:
            choice=area+":"+name
            if choice not in out:out.append(choice)
        if len(out)>=12:break
    return ";".join(out[:12]) or "-"

def layered_media(*groups):
    """Keep source-platform preference before regional alternatives.

    Every slot can contain a PS5 choice followed by PS4 and Windows
    alternatives. Back scans may fall through all three platforms; Box - Front
    remains a true scan from the installed console platform only.
    """
    best=[]
    extras=[]
    for group in groups:
        options=[part for part in face_options(group).split(";") if part!="-"]
        if options:
            best.append(options[0])  # one candidate per platform first
            extras.extend(options[1:])
    result=[]
    used=set()
    for item in (*best,*extras):
        filename=item.split(":",1)[1]
        if filename not in used:
            used.add(filename)
            result.append(item)
        if len(result)>=12:break
    return ";".join(result) or "-"

def parse(xml,installed,diagnostics=None):
    games,aliases,media={}, {}, {}
    # Metadata.zip can group GameImage/GameAlternateName independently of
    # Game entries. Never assume an image's game was already encountered.
    # Pass one collects names/aliases; pass two reads images ONLY for game
    # IDs that could match a title installed on this console.
    iterator=ET.iterparse(xml,events=("start","end"))
    _,root=next(iterator)
    for event,el in iterator:
        if event!="end":continue
        tag=el.tag.rsplit("}",1)[-1]
        if tag=="Game":
            platform=PLATFORMS.get(el.findtext("Platform",""))
            gid=el.findtext("DatabaseID","")
            if platform and gid.isdecimal():
                games[gid]=(platform,el.findtext("Name",""),
                            clean_overview(el.findtext("Overview","") or
                                           el.findtext("Notes","")))
        elif tag=="GameAlternateName":
            gid=el.findtext("DatabaseID","")
            if gid.isdecimal():
                aliases.setdefault(gid,[]).append(el.findtext("AlternateName",""))
        if tag in ("Game","GameAlternateName","GameImage"):
            el.clear();root.clear()

    exact_matches={}
    edition_matches={}
    for gid,(platform,name,notes) in games.items():
        for alias in (name,*aliases.get(gid,[])):
            variants=safe_titles(alias)
            if not variants:continue
            exact_matches.setdefault((platform,variants[0]),set()).add(gid)
            for key in variants[1:]:
                edition_matches.setdefault((platform,key),set()).add(gid)
    # Collect tightly matched PS5/PS4/Windows editions separately. A PC
    # screenshot can enrich a PS5 back, but cannot replace a PS5 box front.
    def related(key,platform):
        names=safe_titles(key[1])
        matches=set()
        for name in names:
            matches.update(exact_matches.get((platform,name),()))
            matches.update(edition_matches.get((platform,name),()))
        return matches
    wanted=set()
    for key in installed:
        for platform in (key[0],"ps4","ps5","windows"):
            wanted.update(related(key,platform))
    if wanted:
        xml.seek(0)  # ZipExtFile and BytesIO support rewinding.
        iterator=ET.iterparse(xml,events=("start","end"))
        _,root=next(iterator)
        for event,el in iterator:
            if event!="end":continue
            tag=el.tag.rsplit("}",1)[-1]
            if tag=="GameImage":
                gid=el.findtext("DatabaseID","")
                if gid in wanted:
                    kind=KINDS.get(el.findtext("Type",""))
                    filename=el.findtext("FileName","")
                    if kind and IMAGE.fullmatch(filename):
                        media.setdefault(gid,{}).setdefault(kind,[]).append(
                            (region(el.findtext("Region","")),filename))
            if tag in ("Game","GameAlternateName","GameImage"):
                el.clear();root.clear()
    rows=[]
    for key,ids in sorted(installed.items()):
        matched=exact_matches.get(key,set())
        # Prefer a unique, platform-exact LaunchBox record. An alternative
        # edition scan is allowed only when exact has no FRONT artwork.
        candidates=matched if len(matched)==1 else set()
        if not any(media.get(g,{}).get("front") or
                   media.get(g,{}).get("front_fanart") for g in candidates):
            alternative=set(edition_matches.get(key,set()))
            # Symmetric lookup: Anno 1800 Console Edition on the console may
            # have a PS5 LaunchBox image filed under "Anno 1800" itself.
            for base in safe_titles(key[1])[1:]:
                alternative.update(exact_matches.get((key[0],base),set()))
            fronts={g for g in alternative if media.get(g,{}).get("front") or
                    media.get(g,{}).get("front_fanart")}
            if len(fronts)==1:candidates=fronts
        # A console entry may be absent from LaunchBox while the same game
        # has excellent PC fanart/gameplay/screenshots. Do NOT discard it:
        # create a scenery-only record and leave its physical FRONT empty.
        # Exact console IDs must never become an unrelated Windows box scan.
        ps5_ids=related(key,"ps5")
        ps4_ids=related(key,"ps4")
        pc_ids=related(key,"windows")
        ps5_gid=next(iter(ps5_ids)) if len(ps5_ids)==1 else None
        ps4_gid=next(iter(ps4_ids)) if len(ps4_ids)==1 else None
        pc_gid=next(iter(pc_ids)) if len(pc_ids)==1 else None
        ps5=media.get(ps5_gid,{}) if ps5_gid else {}
        ps4=media.get(ps4_gid,{}) if ps4_gid else {}
        pc=media.get(pc_gid,{}) if pc_gid else {}
        other_gid=ps4_gid if key[0]=="ps5" else ps5_gid
        if len(candidates)==1:
            gid=next(iter(candidates))
            images=media.get(gid,{})
            # The chosen native edition is authoritative even when the
            # broader alias lookup finds several editions on this platform.
            if key[0]=="ps5":
                ps5,ps5_gid=images,gid
            else:
                ps4,ps4_gid=images,gid
        else:
            # Ambiguous native matches/editions are not assigned at random.
            # A unique secondary record can still supply non-box media.
            if len(matched)>1 or (not other_gid and not pc_gid):
                continue
            gid=other_gid or pc_gid
            images={}
        info=games[gid]
        faces=[face_options(images.get("front",[]) or
                            images.get("front_fanart",[])),
               face_options(images.get("back",[]) or
                            images.get("back_fanart",[])),
               face_options(images.get("spine",[])),
               face_options(images.get("logo",[]))]
        # Box - Front MUST be the installed platform's real retail cover.
        # Box - Back may fall back PS5 -> PS4 -> PC, in that exact order,
        # even when an earlier source has a broken CDN file. Never substitute
        # a PC front as a retail front for a PlayStation game.
        def box_back(group):
            return group.get("back",[]) or group.get("back_fanart",[])
        faces[1]=layered_media(box_back(ps5),box_back(ps4),box_back(pc))
        # Supplementary media also follows PS5 -> PS4 -> PC.
        faces[3]=layered_media(ps5.get("logo",[]),ps4.get("logo",[]),
                               pc.get("logo",[]))
        hero=layered_media(ps5.get("hero",[]),ps4.get("hero",[]),
                           pc.get("hero",[]))
        used={part.split(":",1)[1] for part in hero.split(";") if ":" in part}
        # Two intentionally DIFFERENT screenshot classes:
        # Gameplay is the first image; a Game Title screenshot is preferred
        # for the second. This guarantees both kinds can appear on a
        # reconstructed back even if gameplay has many regional images.
        # The Fanart Background remains an independent HERO slot.
        shots=[]
        shot_kinds=[]
        def add_first(kind):
            for group in (ps5,ps4,pc):
                for area in ORDER:
                    for where,filename in group.get(kind,[]):
                        if where!=area or filename in used:continue
                        used.add(filename)
                        shots.append(area+":"+filename)
                        shot_kinds.append(kind)
                        return True
            return False
        add_first("gameplay")
        add_first("game_title")
        # Missing a separate title image? Use a SECOND distinct gameplay
        # image, then other title screens, never a duplicate of the hero.
        for kind in ("gameplay","game_title"):
            if len(shots)>=2:break
            add_first(kind)
        # Each of the TWO distinct screenshot slots may fall back to its
        # matching PC image when a console CDN candidate is unavailable.
        # Never use the same primary frame as another slot or any hero image.
        def screenshot_sources(slot):
            if slot>=len(shots):return "-"
            primary=shots[slot]
            primary_name=primary.split(":",1)[1]
            forbidden={x.split(":",1)[1] for x in hero.split(";") if ":" in x}
            forbidden.update(x.split(":",1)[1] for i,x in enumerate(shots)
                             if i!=slot)
            options=layered_media(*(
                [(area,filename) for area,filename in group.get(shot_kinds[slot],[])
                 if filename not in forbidden]
                for group in (ps5,ps4,pc)
            ))
            result=[primary]
            seen={primary_name}
            for choice in options.split(";"):
                if ":" not in choice:continue
                filename=choice.split(":",1)[1]
                if filename not in seen:
                    seen.add(filename)
                    result.append(choice)
                if len(result)>=4:break
            return ";".join(result)
        shot1,shot2=screenshot_sources(0),screenshot_sources(1)
        overview=info[2] or (
            games[ps5_gid][2] if ps5_gid else "") or (
            games[ps4_gid][2] if ps4_gid else "") or (
            games[pc_gid][2] if pc_gid else "") or "-"
        for title in sorted(set(ids)):
            rows.append((title,overview,*faces,hero,shot1,shot2,gid))
    rows.sort()
    if diagnostics is not None:
        # The public Metadata.zip must really contain all three media types.
        # Only aggregate counts are printed; no private PS5 IDs/names.
        diagnostics.update({
            kind:sum(len(group.get(kind,())) for group in media.values())
            for kind in ("hero","gameplay","game_title")
        })
    return rows

def build(archive,ids_file,out):
    installed=targets(ids_file)
    with zipfile.ZipFile(archive) as bundle:
        xml=[p for p in bundle.infolist() if Path(p.filename).name.lower()=="metadata.xml"]
        if len(xml)!=1 or xml[0].file_size>2*1024**3:
            raise ValueError("LaunchBox archive is malformed")
        with bundle.open(xml[0]) as source:
            stats={}
            rows=parse(source,installed,stats)
    back_types=[stats.get(k,0) for k in ("hero","gameplay","game_title")]
    print("LaunchBox real media [fanart, gameplay, game title]:",back_types)
    if len(rows)>1000 and min(back_types)<100:
        raise ValueError("LaunchBox back image category missing from live metadata")
    output=Path(out)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text("# title\tOverview\tFront\tBack\tSpine\tLogo\tHero\tShot1\tShot2\tLaunchBoxID\n"+
                      "".join("\t".join(parts)+"\n" for parts in rows),"utf8")
    fronts=sum(row[2]!="-" for row in rows)
    backs=sum(row[3]!="-" for row in rows)
    spines=sum(row[4]!="-" for row in rows)
    print("PS4/PS5 LaunchBox verified-platform matches:",len(rows),
          "fronts:",fronts,"backs:",backs,"spines:",spines)

def download(path):
    req=urllib.request.Request(SOURCE,headers={"User-Agent":"NiakPS5/1.0"})
    with urllib.request.urlopen(req,timeout=50) as resp,Path(path).open("wb") as out:
        size=0
        while True:
            chunk=resp.read(1024*1024)
            if not chunk:break
            size+=len(chunk)
            if size>220*1024*1024:raise ValueError("Oversize metadata archive")
            out.write(chunk)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--zip",type=Path)
    p.add_argument("--download",action="store_true")
    p.add_argument("--titles",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    archive=args.zip or Path("/tmp/niak-launchbox-metadata.zip")
    if args.download:download(archive)
    build(archive,args.titles,args.output)
if __name__=="__main__":
    main()
