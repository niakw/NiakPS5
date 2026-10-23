#!/usr/bin/env python3
"""PS5-only daily wallpaper *build snapshot* from public PS Store title data.

The package rotates the results by local day without contacting an external
service from the console. New PlayStation media is fetched on CI rebuilds only.
Images are resized, quantized and stored as optimized PNG (not unsupported WebP).
"""
from datetime import date,datetime,timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request,urlopen
import argparse,json,sys

SOURCE="https://raw.githubusercontent.com/sharpemu/sharpemu-site/main/src/data/games.json"
ALLOWED_IMAGE_HOST="image.api.playstation.com"
MAX_FEED=5*1024*1024
MAX_IMAGE=7*1024*1024
MAX_WALLS=14
def get(url,limit,hosts):
    parsed=urlparse(url)
    if parsed.scheme!="https" or parsed.hostname not in hosts:
        raise ValueError("Image/data host is not allowlisted")
    req=Request(url,headers={"User-Agent":"NiakPS5-PS5-Daily-Wallpaper/1.0"})
    with urlopen(req,timeout=18) as resp:
        result=resp.read(limit+1)
    if not result or len(result)>limit:raise ValueError("Resource too large")
    return result

def released(value,today):
    try:
        when=datetime.fromisoformat(value.replace("Z","+00:00")).date()
    except (TypeError,AttributeError,ValueError):
        return None
    if not today-timedelta(days=455)<=when<=today:return None
    return when

def candidates(feed,today):
    # PlayStation PS5 dataset only. Filter preorders, duplicates, missing art,
    # adult-themed names and non-game services. Source isn't a rating provider.
    deny=("hentai","porn","sex ", "erotic","casino","gambling","adult only")
    seen=set()
    hits=[]
    for item in feed:
        name=str(item.get("name") or "")
        ident=item.get("conceptId")
        cover=str(item.get("cover") or "")
        day=released(item.get("releaseDate"),today)
        if not name or not day or not cover or ident in seen:continue
        if any(word in name.casefold() for word in deny):continue
        if urlparse(cover).hostname != ALLOWED_IMAGE_HOST:continue
        if not str(item.get("titleId","")).startswith("PPSA"):continue
        if not item.get("enriched"):continue
        genres=item.get("genres") or []
        if "Adult" in genres:continue
        seen.add(ident)
        hits.append((day,name,ident,cover))
    hits.sort(key=lambda e:(-e[0].toordinal(),e[1].casefold()))
    return hits

def build(folder,now=None,limit=MAX_WALLS):
    from PIL import Image,ImageFilter,ImageOps
    folder.mkdir(parents=True,exist_ok=True)
    today=now or date.today()
    feed=json.loads(get(SOURCE,MAX_FEED,{"raw.githubusercontent.com"}))
    records=[]
    for day,name,ident,cover in candidates(feed,today)[:85]:
        if len(records)>=limit:break
        try:
            raw=get(cover,MAX_IMAGE,{ALLOWED_IMAGE_HOST})
            with Image.open(BytesIO(raw)) as im:
                im.load()
                if im.width<300 or im.height<250 or im.width*im.height>12_000_000:
                    continue
                rgb=im.convert("RGB")
                if rgb.width/rgb.height>=1.6:
                    visual=ImageOps.fit(rgb,(1280,720),method=Image.Resampling.LANCZOS)
                else:
                    # Square cover art is not stretched: blurred page-wide
                    # backdrop plus accurately proportioned central art.
                    visual=ImageOps.fit(rgb,(1280,720),method=Image.Resampling.LANCZOS)
                    visual=visual.filter(ImageFilter.GaussianBlur(radius=27))
                    foreground=rgb.copy()
                    foreground.thumbnail((510,670),Image.Resampling.LANCZOS)
                    visual.paste(foreground,((1280-foreground.width)//2,
                                              (720-foreground.height)//2))
                # Quantized PNG is universally decoded by the vendored LodePNG.
                # WebP would require a separate runtime decoder on PS5.
                optimized=visual.quantize(colors=160,method=Image.Quantize.MEDIANCUT)
                output=folder/f"wall-{len(records):02d}.png"
                optimized.save(output,format="PNG",optimize=True)
            records.append({"game":name,"date":day.isoformat(),"conceptId":ident,
                            "source":cover,"file":output.name,
                            "bytes":output.stat().st_size})
        except (OSError,ValueError,TimeoutError,KeyError) as exc:
            print("Skipped artwork:",name,type(exc).__name__,file=sys.stderr)
    # Remove previous unused files so art count can't lag after a rebuild.
    keep={item["file"] for item in records}
    for path in folder.glob("wall-*.png"):
        if path.name not in keep:path.unlink()
    manifest={"source":"PlayStation 5 media, sharpemu public title catalogue",
              "generated":today.isoformat(),"games":records}
    (folder/"index.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),"utf8")
    # The native PS5 app uses a compact local text manifest for provenance;
    # no live JSON parsing or network request on the rendering thread.
    (folder/"labels.tsv").write_text(
        "".join(f"{r['file']}\t{r['game'].replace(chr(9),' ').replace(chr(10),' ')[:110]}\t{r['date']}\n"
                for r in records),"utf8")
    print("PS5 backgrounds",len(records),"optimized PNG files",
          sum(x["bytes"] for x in records),"bytes")
    return len(records)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    try:
        build(args.output)
    except Exception as error:
        # Preserve the animated smoke if network fetching is unavailable.
        print("PlayStation images unavailable; preserve smoke:",error,file=sys.stderr)
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/"index.json").write_text('{"source":"offline","games":[]}')
        (args.output/"labels.tsv").write_text("")
