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
       "Clear Logo":"logo"}
PLATFORMS={"Sony Playstation 4":"ps4","Sony Playstation 5":"ps5",
           "Sony PlayStation 4":"ps4","Sony PlayStation 5":"ps5"}
REGIONS={"france":"fr","europe":"eu","world":"world","united kingdom":"uk",
         "north america":"us","united states":"us","canada":"ca","germany":"de",
         "japan":"jp","spain":"es","italy":"it","portugal":"pt"}
ORDER=("fr","eu","world","uk","ca","us","de","es","it","pt","jp","other")

def normalize(name):
    name=unicodedata.normalize("NFKD",str(name)).encode("ascii","ignore").decode()
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9]+"," ",name.lower())).strip()
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
            if gid in games:aliases.setdefault(gid,[]).append(el.findtext("AlternateName",""))
        elif tag=="GameImage":
            gid=el.findtext("DatabaseID","")
            kind=KINDS.get(el.findtext("Type",""))
            filename=el.findtext("FileName","")
            if gid in games and kind and IMAGE.fullmatch(filename):
                media.setdefault(gid,{}).setdefault(kind,[]).append(
                    (region(el.findtext("Region","")),filename))
        if tag in ("Game","GameAlternateName","GameImage"):
            el.clear();root.clear()
    by_key={}
    for gid,(platform,name,notes) in games.items():
        for alias in (name,*aliases.get(gid,[])):
            key=(platform,normalize(alias))
            if key in installed:by_key.setdefault(key,set()).add(gid)
    rows=[]
    for key,ids in sorted(installed.items()):
        matched=by_key.get(key,set())
        if len(matched)!=1:continue
        gid=next(iter(matched))
        info=games[gid];images=media.get(gid,{})
        faces=[face_options(images.get(kind,[])) for kind in
               ("front","back","spine","logo")]
        for title in sorted(set(ids)):
            overview=info[2] or "-"
            rows.append((title,overview,*faces,gid))
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
    output.write_text("# title\tOverview\tFront\tBack\tSpine\tLogo\tLaunchBoxID\n"+
                      "".join("\t".join(parts)+"\n" for parts in rows),"utf8")
    print("PS4/PS5 LaunchBox exact regional matches:",len(rows))

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
