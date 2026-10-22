#!/usr/bin/env python3
"""Private, opt-in PS4/PS5 cover providers for NiakPS5 FTP installation.

TheGamesDB: platform-verified physical front/back box art.
SteamGridDB: community portrait artwork FRONT ONLY, never labelled retail.
Never bundle downloaded artwork or API credentials in a public application.
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
import urllib.request
from urllib.parse import urlsplit

MAX_JSON=1024*1024
IMAGE_HOSTS={"cdn.thegamesdb.net","cdn.steamgriddb.com","cdn2.steamgriddb.com"}
PLATFORM_NAMES={
    "ps5":{"sony playstation 5","playstation 5","ps5","sony ps5"},
    "ps4":{"sony playstation 4","playstation 4","ps4","sony ps4"},
}
IGNORABLE_SUFFIXES=(" console edition"," playstation 5 edition",
                    " playstation 4 edition"," ps5 edition"," ps4 edition")


def normalize(name):
    plain=unicodedata.normalize("NFKD",str(name)).encode("ascii","ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+",plain.lower()))


def name_variants(name):
    exact=normalize(name)
    variants=[exact] if exact else []
    for ending in IGNORABLE_SUFFIXES:
        if exact.endswith(ending) and len(exact)>len(ending)+4:
            variants.append(exact[:-len(ending)])
    return tuple(dict.fromkeys(variants))


def trusted_image_url(url):
    """Reject arbitrary hostnames and redirects from untrusted API metadata."""
    if not isinstance(url,str) or len(url)>600:
        return False
    p=urlsplit(url)
    return (p.scheme=="https" and p.hostname in IMAGE_HOSTS
            and p.username is None and p.password is None
            and not p.fragment and p.port in (None,443))


def get_json(url, headers=None):
    p=urlsplit(url)
    if p.scheme!="https" or p.hostname not in (
        "api.thegamesdb.net","www.steamgriddb.com"):
        raise ValueError("Unexpected API host")
    req=urllib.request.Request(url,headers=headers or {"User-Agent":"NiakPS5-private-art/1.1"})
    with urllib.request.urlopen(req,timeout=12) as response:
        resolved=getattr(response,"geturl",lambda:url)()
        if urlsplit(resolved).hostname!=p.hostname:
            raise ValueError("Unexpected API redirect")
        body=response.read(MAX_JSON+1)
    if len(body)>MAX_JSON:
        raise ValueError("Oversize API response")
    return json.loads(body)


def tgdb_cover_urls(title,platform,key):
    """Strict title + returned platform match; never guess across PS4/PS5."""
    if not key or platform not in PLATFORM_NAMES or not title.strip():
        return {}
    query=urllib.parse.urlencode({
        "apikey":key,"name":title[:120],"fields":"platform",
        "include":"boxart,platform"})
    data=get_json("https://api.thegamesdb.net/v1.1/Games/ByGameName?"+query)
    games=data.get("data",{}).get("games",[])
    platform_data=data.get("include",{}).get("platform",{}).get("data",{})
    boxart=data.get("include",{}).get("boxart",{}).get("data",{})
    if not isinstance(games,list) or not isinstance(platform_data,dict) or not isinstance(boxart,dict):
        return {}
    names=set(name_variants(title))
    matched=[]
    for game in games[:60]:
        if not isinstance(game,dict):continue
        # Both sources can have homonymous games: require exact names.
        if not set(name_variants(str(game.get("game_title") or game.get("name") or ""))) & names:
            continue
        pid=str(game.get("platform",""))
        item=platform_data.get(pid)
        if not isinstance(item,dict):continue
        label=normalize(item.get("name",""))
        if label not in PLATFORM_NAMES[platform]:continue
        matched.append(game)
    if len(matched)!=1:
        return {}
    gid=str(matched[0].get("id",""))
    images=boxart.get(gid,[])
    if not isinstance(images,list):return {}
    result={}
    for item in images:
        if not isinstance(item,dict):continue
        side=item.get("side")
        filename=item.get("filename")
        if side not in ("front","back") or side in result or not isinstance(filename,str):
            continue
        # Trust only the official fixed image CDN and a side-specific path.
        if not re.fullmatch(r"boxart/"+side+r"/[A-Za-z0-9_/-]{1,150}\.(?:jpg|jpeg|png|webp)",filename):
            continue
        url="https://cdn.thegamesdb.net/images/original/"+filename
        if trusted_image_url(url):result[side]=url
    return result


def steamgriddb_portrait_url(title,key):
    """Community vertical grid only. Not PS5 retail packaging or a back/spine."""
    if not key or not title.strip():return {}
    headers={"Authorization":"Bearer "+key,"User-Agent":"NiakPS5-private-art/1.1"}
    url="https://www.steamgriddb.com/api/v2/search/autocomplete/"+urllib.parse.quote(title[:120],safe="")
    data=get_json(url,headers)
    entries=data.get("data",[])
    if not isinstance(entries,list):return {}
    norm=normalize(title)
    matches=[x for x in entries if isinstance(x,dict) and
             normalize(x.get("name",""))==norm and
             "software" not in x.get("types",[])]
    if len(matches)!=1:return {}
    gid=matches[0].get("id")
    if not isinstance(gid,int) or gid<=0:return {}
    grids=get_json(
        "https://www.steamgriddb.com/api/v2/grids/game/"+str(gid)+
        "?dimensions=600x900,342x482,660x930&types=static&nsfw=false&humor=false&epilepsy=false&limit=25",
        headers).get("data",[])
    if not isinstance(grids,list):return {}
    for grid in sorted((x for x in grids if isinstance(x,dict)),
                       key=lambda x:x.get("score",0) if isinstance(x.get("score"),(int,float)) else 0,
                       reverse=True):
        candidate=grid.get("url")
        if trusted_image_url(candidate):
            return {"front":candidate}
    return {}
