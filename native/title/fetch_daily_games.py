#!/usr/bin/env python3
"""Recent PS5 games' real publisher artwork from a public GitHub PS5 database.
No authentication, PSN identifiers or user data. Build-time job, not runtime
console HTTPS. Local date rotates installed images; fresh assets need new build.
"""
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import argparse
import json
import sys

DATA_URL="https://raw.githubusercontent.com/sharpemu/sharpemu-site/main/src/data/games.json"
IMAGE_HOSTS={"image.api.playstation.com"}
MAX_JSON=8*1024*1024
MAX_IMAGE=8*1024*1024
MAX_GAMES=14

def fetch(url, limit, hosts):
    parsed=urlparse(url)
    if parsed.scheme!="https" or parsed.hostname not in hosts:
        raise ValueError("Non-allowlisted HTTPS resource")
    req=Request(url, headers={"User-Agent":"NiakPS5/1.0 (PS5 wallpaper build)"})
    with urlopen(req,timeout=14) as response:
        if response.status!=200 or urlparse(response.url).hostname not in hosts:
            raise ValueError("Invalid response or redirect")
        data=response.read(limit+1)
    if not data or len(data)>limit:raise ValueError("Resource too large")
    return data

def candidates(games, today):
    first=today-timedelta(days=365)
    eligible=[]
    for g in games:
        if not g.get("enriched") or not g.get("releaseDate") or not g.get("cover"):
            continue
        try:when=datetime.fromisoformat(g["releaseDate"].replace("Z","+00:00")).date()
        except ValueError:continue
        # Skip a title if its release date is tomorrow or future.
        if not first<=when<today:continue
        name=str(g.get("name","")).lower()
        if any(term in name for term in ("hentai","adult only","porn","xxx","erotic")):
            continue
        eligible.append((when,g))
    eligible.sort(key=lambda x:x[0],reverse=True)
    return eligible

def build(output, now=None, maximum=MAX_GAMES):
    from PIL import Image, ImageOps
    today=now or date.today()
    output.mkdir(parents=True,exist_ok=True)
    raw=fetch(DATA_URL,MAX_JSON,{"raw.githubusercontent.com"})
    entries=candidates(json.loads(raw),today)
    records=[]
    for release,game in entries:
        if len(records)>=maximum:break
        address=game["cover"]
        if urlparse(address).hostname not in IMAGE_HOSTS:continue
        try:
            raw_image=fetch(address,MAX_IMAGE,IMAGE_HOSTS)
            with Image.open(BytesIO(raw_image)) as original:
                original.load()
                if original.width<700 or original.height<390:
                    continue
                # PS5 publisher image can be landscape or portrait. Crop to a
                # GPU-friendly 16:9 hero image, leaving smoke effects behind it.
                image=ImageOps.fit(original.convert("RGB"),(1280,720),
                                   method=Image.Resampling.LANCZOS)
                name=f"wall-{len(records):02d}.tga"
                image.save(output/name,format="TGA")
            records.append({"title":str(game.get("name",""))[:120],
                            "title_id":game.get("titleId"),
                            "released":release.isoformat(),"file":name,
                            "source":"PlayStation publisher artwork via sharpemu GitHub"})
        except (ValueError,KeyError,TypeError,TimeoutError,OSError) as e:
            print(f"PS5 image rejected: {str(e)[:100]}",file=sys.stderr)
    manifest={"source":"sharpemu/sharpemu-site (GitHub); publisher artwork",
              "generated":today.isoformat(),"games":records}
    temp=output/"index.json.tmp"
    temp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),"utf-8")
    temp.replace(output/"index.json")
    print(f"NiakPS5: {len(records)} verified recent-PS5 wallpapers; {today}")
    return len(records)

if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("--output",type=Path,required=True)
    opts=cli.parse_args()
    try:build(opts.output)
    except Exception as e:
        print("PS5 wallpaper feed unavailable; retain procedural smoke: "+str(e),file=sys.stderr)
        opts.output.mkdir(parents=True,exist_ok=True)
        (opts.output/"index.json").write_text('{"games":[],"source":"offline"}',"utf-8")
