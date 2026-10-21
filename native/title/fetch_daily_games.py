#!/usr/bin/env python3
"""Fetch recent released Steam games' *screenshots* into an offline-ready
wallpaper pool. Never sends PS5 library/profile data to Steam. Build-time only;
the installed PS5 title rotates its bounded pool daily without network.
All imagery remains owned by the relevant publishers.
"""
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import argparse
import json
import sys

HOSTS = {"shared.fastly.steamstatic.com", "shared.akamai.steamstatic.com",
         "cdn.akamai.steamstatic.com", "steamcdn-a.akamaihd.net"}
MAX_JSON = 1024 * 1024
MAX_IMAGE = 8 * 1024 * 1024
MAX_GAMES = 7

def fetch(url, limit, hosts):
    urlparts = urlparse(url)
    if urlparts.scheme != "https" or urlparts.hostname not in hosts:
        raise ValueError("Untrusted download host")
    req = Request(url, headers={"User-Agent": "NiakPS5/0.4 (native title build)"})
    with urlopen(req, timeout=12) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}")
        data = response.read(limit + 1)
    if not data or len(data) > limit:
        raise ValueError("Resource exceeds size limit")
    return data

def released_at(s):
    for fmt in ("%d %b, %Y", "%b %d, %Y", "%d %B, %Y", "%B %d, %Y",
                "%d %b %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def build(output, now=None, max_games=MAX_GAMES):
    from PIL import Image, ImageOps
    today = now or date.today()
    output.mkdir(parents=True, exist_ok=True)
    api = {"store.steampowered.com"}
    url = "https://store.steampowered.com/api/featuredcategories/?cc=fr&l=english"
    feed = json.loads(fetch(url, MAX_JSON, api))
    # Prioritize the store's popular titles that actually released recently.
    # "new_releases" alone is polluted with very small / adult-only releases.
    best = feed.get("top_sellers", {}).get("items", [])
    fresh = feed.get("new_releases", {}).get("items", [])
    rows = best + fresh
    used = set()
    records = []
    # Explicitly launched games only, released in past 365 days.
    for row in rows[:80]:
        if len(records) >= max_games:
            break
        appid = row.get("id", row.get("appid"))
        if not isinstance(appid, int) or not 0 < appid < 10_000_000 or appid in used:
            continue
        used.add(appid)
        try:
            details_url = (f"https://store.steampowered.com/api/appdetails"
                           f"?appids={appid}&cc=fr&l=english")
            item = json.loads(fetch(details_url, MAX_JSON, api))[str(appid)]
            if not item.get("success"):
                continue
            game = item["data"]
            release = game.get("release_date") or {}
            day = released_at(release.get("date", ""))
            if release.get("coming_soon") or day is None or not today - timedelta(days=365) <= day <= today:
                continue
            # Adult content can be free and required_age can be a string.
            # Keep the TV/console home wallpaper suitable for a shared room.
            age = str(game.get("required_age", "0"))
            if age.isdecimal() and int(age) >= 18:
                continue
            descriptors = game.get("content_descriptors") or {}
            flags = set(descriptors.get("ids") or [])
            if any(x in flags for x in (3, 4, 5)):
                continue
            title = str(game.get("name", "")).lower()
            if any(token in title for token in
                   ("hentai", "porn", "sex ", "sex:", "xxx", "erotic",
                    "lust", "nudity", "fetish", "adult only")):
                continue
            if game.get("type") not in ("game", None):
                continue
            shots = game.get("screenshots", [])[:3]
            for shot in shots:
                source = shot.get("path_full") or ""
                if urlparse(source).hostname not in HOSTS:
                    continue
                raw = fetch(source, MAX_IMAGE, HOSTS)
                with Image.open(BytesIO(raw)) as original:
                    original.load()
                    if original.width < 960 or original.height < 540 or original.width < original.height:
                        continue
                    im = ImageOps.fit(original.convert("RGB"), (1280,720),
                                      method=Image.Resampling.LANCZOS)
                    name = f"wall-{len(records):02d}.tga"
                    im.save(output / name, format="TGA")
                records.append({"appid": appid, "title": str(game.get("name", ""))[:90],
                                "release_date": day.isoformat(), "file": name})
                break
        except (ValueError, KeyError, OSError, TimeoutError, TypeError) as error:
            print(f"Skip Steam app {appid}: {error}", file=sys.stderr)
            continue
    # Atomic manifest publication. All wallpapers are optional runtime assets.
    tmp = output / "index.json.tmp"
    tmp.write_text(json.dumps({"source":"Steam Store API (publisher images)",
                                "generated": today.isoformat(),
                                "games": records}, ensure_ascii=False, indent=2))
    tmp.replace(output / "index.json")
    print(f"NiakPS5 daily backgrounds: {len(records)} recent screenshots; day {today}")
    return len(records)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    try:
        build(a.output)
    except Exception as error:
        print(f"Daily API unavailable, continuing with procedural smoke: {error}", file=sys.stderr)
        a.output.mkdir(parents=True, exist_ok=True)
        (a.output / "index.json").write_text(json.dumps({"source":"offline", "games":[]}))
