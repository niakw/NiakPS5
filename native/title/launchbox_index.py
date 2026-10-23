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
       "Clear Logo":"logo", "Fanart - Background":"hero",
       "Screenshot - Gameplay":"screenshot",
       "Screenshot - Game Title":"screenshot"}
PLATFORMS={"Sony Playstation 4":"ps4","Sony Playstation 5":"ps5",
           "Sony PlayStation 4":"ps4","Sony PlayStation 5":"ps5"}
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
    text=html.unescape(re.sub(r"<[^>]*>"," ",str(notes)))
    return re.sub(r"\s+"," ",text).replace("\t"," ").strip()[:620]
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

def parse(xml,installed):
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
                            clean_overview(el.findtext("Notes","")))
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
    # Only collect cover metadata for plausible exact/platform/edition
    # matches, not the millions of unrelated images in the global archive.
    wanted=set()
    for key in installed:
        wanted.update(exact_matches.get(key,()))
        wanted.update(edition_matches.get(key,()))
        for base in safe_titles(key[1])[1:]:
            wanted.update(exact_matches.get((key[0],base),()))
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
        if not any(media.get(g,{}).get("front") for g in candidates):
            alternative=set(edition_matches.get(key,set()))
            # Symmetric lookup: Anno 1800 Console Edition on the console may
            # have a PS5 LaunchBox image filed under "Anno 1800" itself.
            for base in safe_titles(key[1])[1:]:
                alternative.update(exact_matches.get((key[0],base),set()))
            fronts={g for g in alternative if media.get(g,{}).get("front")}
            if len(fronts)==1:candidates=fronts
        if len(candidates)!=1:continue
        gid=next(iter(candidates))
        info=games[gid];images=media.get(gid,{})
        faces=[face_options(images.get(kind,[])) for kind in
               ("front","back","spine","logo")]
        # A genuine scene and gameplay captures have their own slots. Use
        # unique source filenames: never promote the same hero to two images.
        hero=face_options(images.get("hero",[]))
        used={part.split(":",1)[1] for part in hero.split(";")
              if ":" in part}
        shots=[]
        for candidate in face_options(images.get("screenshot",[])).split(";"):
            if ":" not in candidate:continue
            filename=candidate.split(":",1)[1]
            if filename in used:continue
            used.add(filename)
            shots.append(candidate)
            if len(shots)==2:break
        shot1,shot2=(shots+["-","-"])[:2]
        for title in sorted(set(ids)):
            overview=info[2] or "-"
            rows.append((title,overview,*faces,hero,shot1,shot2,gid))
    rows.sort()
    return rows

def build(archive,ids_file,out):
    installed=targets(ids_file)
    with zipfile.ZipFile(archive) as bundle:
        xml=[p for p in bundle.infolist() if Path(p.filename).name.lower()=="metadata.xml"]
        if len(xml)!=1 or xml[0].file_size>2*1024**3:
            raise ValueError("LaunchBox archive is malformed")
        with bundle.open(xml[0]) as source:
            rows=parse(source,installed)
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
