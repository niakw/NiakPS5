#!/usr/bin/env python3
"""Deploy a single NiakPS5 title folder through PS5 FTP, optionally enabling
its separate Payload Manager one-shot boot entry.

No credentials, addresses or console data are embedded in the project.
Uses the standard ftplib FTP protocol (unencrypted; only on a trusted LAN).
"""
import argparse
from ftplib import FTP, error_perm
from getpass import getpass
from io import BytesIO
import hashlib
from pathlib import Path
import posixpath
import re
import json

TITLE = "PPSA99386"
PAYLOAD = "/data/pldmgr/payloads/niakps5/niakps5.elf"
PAYLOAD_META = PAYLOAD + ".json"
AUTOLOAD_NAME = "niakps5.elf"
AUTOLOAD = "/data/pldmgr/autoload.txt"
CONFIG = "/data/pldmgr/pldmgr_config.txt"

def mkdirs(ftp, dirname):
    current = ""
    for part in dirname.strip("/").split("/"):
        current += "/" + part
        try:
            ftp.mkd(current)
        except error_perm as exc:
            if not str(exc).startswith("550"):
                raise
        else:
            # Only chmod newly created NiakPS5-owned directories. Never
            # change /data, other homebrew apps, or Payload Manager's roots.
            owned = (current.startswith("/data/homebrew/PPSA99386/") or
                     current == "/data/homebrew/PPSA99386" or
                     current.startswith("/data/pldmgr/payloads/niakps5/") or
                     current == "/data/pldmgr/payloads/niakps5")
            if owned:
                try:
                    ftp.sendcmd("SITE CHMOD 755 " + current)
                except error_perm:
                    pass

def retrieve(ftp, path):
    output = BytesIO()
    try:
        ftp.retrbinary("RETR " + path, output.write)
    except error_perm as exc:
        if str(exc).startswith("550"):
            return None
        raise
    return output.getvalue()

def upload(ftp, path, content):
    mkdirs(ftp, posixpath.dirname(path))
    ftp.storbinary("STOR " + path, BytesIO(content))
    try:
        ftp.sendcmd("SITE CHMOD 755 " + path if path.endswith(".elf") or path.endswith("eboot.bin")
                    else "SITE CHMOD 644 " + path)
    except error_perm:
        # Not every PS5 FTP server implements SITE CHMOD; archive encodes POSIX modes.
        pass

PROFILE_ROOT="/system_data/priv/cache/profile"
MAX_AVATAR=2*1024*1024

def _bounded_retrieve(ftp,path,limit=MAX_AVATAR):
    out=BytesIO()
    def feed(block):
        if out.tell()+len(block)>limit:
            raise ValueError("Avatar exceeds safe size")
        out.write(block)
    try: ftp.retrbinary("RETR "+path,feed)
    except error_perm as error:
        if str(error).startswith("550"):return None
        raise
    return out.getvalue()

def copy_avatar_for_ftp(ftp, user_id=None):
    """Opt-in source: only read user's current profile cache over FTP.

    Auto-select exactly one profile; never arbitrarily choose between accounts.
    If more than one exists, caller can specify --avatar-user-id 0x12345678.
    The private avatar is copied ONLY to the console's local title assets.
    """
    candidates=[]
    if user_id:
        if not re.fullmatch(r"0x[0-9A-Fa-f]{8}",user_id):
            raise ValueError("Avatar user ID must be the 0xXXXXXXXX format")
        candidates=[user_id]
    else:
        try: names=ftp.nlst(PROFILE_ROOT)
        except (error_perm,AttributeError):return False
        candidates=sorted({posixpath.basename(name.rstrip("/")) for name in names
                           if re.fullmatch(r"0x[0-9A-Fa-f]{8}",
                                           posixpath.basename(name.rstrip("/")))})
        if len(candidates)!=1:
            print("Avatar: 0 or several profiles; no automatic choice made.")
            return False
    user=candidates[0]
    for name,signature in (("avatar.png",b"\x89PNG\r\n\x1a\n"),
                           ("avatar128.dds",b"DDS "),
                           ("avatar260.dds",b"DDS "),
                           ("avatar64.dds",b"DDS ")):
        try: blob=_bounded_retrieve(ftp,f"{PROFILE_ROOT}/{user}/{name}")
        except (ValueError,OSError):continue
        if not blob or len(blob)<144 or blob[:len(signature)]!=signature:
            continue
        suffix=".png" if name.endswith(".png") else ".dds"
        # The owner marker is intentionally cleared FIRST. An interrupted
        # FTP upload must never expose another user's new avatar under an old
        # account's previously cached marker.
        marker=f"/data/homebrew/{TITLE}/assets/niak-profile-source.txt"
        upload(ftp,marker,b"")
        upload(ftp,f"/data/homebrew/{TITLE}/assets/niak-profile{suffix}",blob)
        owner=f"0x{int(user,16):08X} {suffix[1:]}\n"
        upload(ftp,f"/data/homebrew/{TITLE}/assets/niak-profile-source.txt",
               owner.encode("ascii"))
        print("Avatar: actual PS5 profile image staged locally.")
        return True
    print("Avatar: no readable profile image; Sony profile left untouched.")
    return False

def upload_local_homebrew_names(ftp):
    """Build a small local-only title overlay from real PS5 param.json files.
    It stays on the owner's PS5; no online lookup or repository upload.
    """
    # Native game (0) vs media app (65536/65792/66048) is encoded in
    # PS5 param.json. No guessing from a title name or PPSA prefix.
    roots=("/data/homebrew","/user/app","/system_ex/app",
           "/mnt/ext0/user/app","/mnt/ext1/user/app")
    records={}
    readable_roots=0
    for root in roots:
      try: entries=ftp.nlst(root)
      except (error_perm,AttributeError,OSError):continue
      readable_roots+=1
      for dirname in entries[:300]:
        ident=posixpath.basename(dirname.rstrip("/"))
        if not re.fullmatch(r"(PPSA|CUSA|LAPY|FAKE|NPXS)[0-9]{5}",ident):continue
        try: body=_bounded_retrieve(ftp,f"{root}/{ident}/sce_sys/param.json")
        except (OSError,ValueError):continue
        if not body or len(body)>65536:continue
        try: meta=json.loads(body)
        except (ValueError,UnicodeDecodeError):continue
        if not isinstance(meta,dict):continue
        declared=meta.get("titleId")
        if declared is not None and declared!=ident:
            # Ignore copied, malformed or stale metadata under the wrong
            # title folder, even when the declared ID has a non-string type.
            continue
        params=meta.get("localizedParameters")
        if not isinstance(params,dict):
            params={}
        languages=["fr-FR","en-US",str(params.get("defaultLanguage",""))]
        languages += [k for k in params if isinstance(params[k],dict)]
        title=meta.get("titleName")
        if not title:
            for lang in languages:
                value=params.get(lang)
                if isinstance(value,dict) and value.get("titleName"):
                    title=value["titleName"];break
        if isinstance(title,str):
            title=" ".join(title.split())[:120]
            category=meta.get("applicationCategoryType")
            genre=""
            if isinstance(category,str) and category.isdecimal():
                category=int(category)
            if type(category) is int:
                if category==0:genre="Jeu"
                elif category in (65536,65792,66048):genre="Application"
            # NPXS also covers Sony system services. Only verified installed
            # media applications qualify for this private metadata overlay.
            if ident.startswith("NPXS") and genre!="Application":
                continue
            if title and "\t" not in title:
                records[ident]=(title,genre)
    # Clear stale entries only if some directories were actually readable.
    # If every root refused FTP access, installation state is UNKNOWN, not
    # empty: preserve the last verified private title overlay.
    if not readable_roots:
        print("Titles: cannot list installed title roots; previous private metadata preserved.")
        return 0
    contents="".join(f"{id}\t{name}\t{kind}\t\t\n"
                     for id,(name,kind) in sorted(records.items()))
    upload(ftp,f"/data/homebrew/{TITLE}/assets/niak-local-titles.tsv",
           contents.encode("utf-8"))
    print(f"Titles: {len(records)} installed PS4/PS5 title/category records resolved locally.")
    return len(records)


def _installed_title_ids(ftp, limit=150):
    """Discover PS4/PS5 folders on the owner's console, without touching app.db."""
    found=set()
    for base in ("/user/app","/system_ex/app","/data/homebrew",
                 "/mnt/ext0/user/app","/mnt/ext1/user/app"):
        try: entries=ftp.nlst(base)
        except (error_perm,AttributeError,OSError):continue
        for entry in entries[:300]:
            ident=posixpath.basename(str(entry).rstrip("/"))
            if ident!=TITLE and re.fullmatch(r"(PPSA|CUSA|LAPY|FAKE)[0-9]{5}",ident):
                found.add(ident)
        if len(found)>=limit:break
    return sorted(found)[:limit]


# A sandboxed title may not read another game's icon0/pic1 even though
# the owner's FTP server can. Cache publisher-provided game artwork in
# NiakPS5's own data directory, not private captures or screenshots.
INSTALLED_ART_ROOT=f"/data/homebrew/{TITLE}/assets/niak-installed"

def _prepare_installed_png(data,scene=False):
    """Bounded PNG for the native decoder, reduced with Pillow if available."""
    if not data or len(data)>5*1024*1024 or data[:8]!=b"\x89PNG\r\n\x1a\n":
        return None
    if len(data)<33:return None
    width=int.from_bytes(data[16:20],"big")
    height=int.from_bytes(data[20:24],"big")
    if width<32 or height<32 or width>4096 or height>2304 or width*height>9500000:
        return None
    if scene and (width<512 or height<256 or not 1.3<=width/height<=2.5):
        return None
    try:
        from PIL import Image
        output=BytesIO()
        with Image.open(BytesIO(data)) as source:
            if source.format!="PNG":return None
            source.load()
            source.thumbnail((1024,768) if scene else (512,512),Image.Resampling.LANCZOS)
            source.convert("RGB" if scene else "RGBA").save(
                output,format="PNG",optimize=True,compress_level=9)
        encoded=output.getvalue()
        if len(encoded)<=4*1024*1024:return encoded
    except ImportError:
        pass
    except (OSError,ValueError,OverflowError):
        return None
    if len(data)<=4*1024*1024 and width<=2048 and height<=2048:
        return data
    return None

def _verified_media_ids(ftp):
    """Only NPXS titles explicitly marked as installed media applications."""
    try:
        raw=_bounded_retrieve(
            ftp,f"/data/homebrew/{TITLE}/assets/niak-local-titles.tsv",limit=512*1024)
    except (OSError,ValueError):
        return []
    if not raw:return []
    ids=set()
    for line in raw.decode("utf-8","replace").splitlines():
        columns=line.split("\t")
        if len(columns)>=3 and re.fullmatch(r"NPXS[0-9]{5}",columns[0]) and columns[2]=="Application":
            ids.add(columns[0])
    return sorted(ids)

def stage_installed_artwork(ftp,maximum_titles=150,force=False):
    """Store actual installed-title icon0/pic1 locally; never scrape user media."""
    ids=_installed_title_ids(ftp,maximum_titles)
    # NPXS covers Sony system services too; stage only verified media apps
    # from the private param.json overlay, never arbitrary system titles.
    ids=list(dict.fromkeys((ids+_verified_media_ids(ftp))[:maximum_titles]))
    existing=_remote_filenames(ftp,INSTALLED_ART_ROOT) or set()
    count=0
    rejected=0
    for ident in ids:
        for side,filename in (("icon","icon0.png"),("scene","pic1.png")):
            destination=f"{INSTALLED_ART_ROOT}/{ident}-{side}.png"
            if posixpath.basename(destination) in existing and not force:
                continue
            sources=(
                f"/data/homebrew/{ident}/sce_sys/{filename}",
                f"/user/app/{ident}/sce_sys/{filename}",
                f"/user/appmeta/{ident}/{filename}",
                f"/system_ex/app/{ident}/sce_sys/{filename}",
                f"/mnt/ext0/user/app/{ident}/sce_sys/{filename}",
                f"/mnt/ext0/user/appmeta/{ident}/{filename}",
                f"/mnt/ext1/user/app/{ident}/sce_sys/{filename}",
                f"/mnt/ext1/user/appmeta/{ident}/{filename}",
            )
            for source in sources:
                try:
                    raw=_bounded_retrieve(ftp,source,limit=5*1024*1024)
                except (OSError,ValueError):
                    rejected+=1
                    continue
                if raw is None:continue
                png=_prepare_installed_png(raw,scene=side=="scene")
                if not png:
                    rejected+=1
                    continue
                try:upload(ftp,destination,png)
                except (OSError,error_perm):
                    rejected+=1
                    break
                existing.add(posixpath.basename(destination))
                count+=1
                break
    print(f"Visuels installés : {count} PNG copiés depuis {len(ids)} titres "
          f"(rejets/permissions : {rejected}).")
    return count

def _decode_retail_image(raw,side):
    """Personal-use PS5 optimized PNG; no unauthorized source is republished."""
    try:
        from PIL import Image
    except ImportError:
        Image=None
    if Image:
        with Image.open(BytesIO(raw)) as source:
            source.load()
            if source.width<(16 if side=="spine" else 64) or source.height<40 or source.width*source.height>14_000_000:
                raise ValueError("Unexpected image geometry")
            if side=="logo":
                image=source.convert("RGBA")
                image.thumbnail((850,300),Image.Resampling.LANCZOS)
            else:
                if source.height<200 or source.width/source.height>(0.42 if side=="spine" else 1.4):
                    raise ValueError("Not a retail box scan")
                image=source.convert("RGB")
                image.thumbnail((600,900),Image.Resampling.LANCZOS)
                image=image.quantize(colors=160,method=Image.Quantize.MEDIANCUT)
            out=BytesIO()
            image.save(out,"PNG",optimize=True)
            return out.getvalue()
    # macOS has sips preinstalled: use it to convert JPG to PNG locally
    # without requiring Pillow. No image needs to leave this machine.
    import shutil,subprocess,tempfile
    if shutil.which("sips"):
        with tempfile.TemporaryDirectory() as temp:
            src=Path(temp)/"source.jpg";dst=Path(temp)/"case.png"
            src.write_bytes(raw)
            result=subprocess.run(["sips","-s","format","png","-Z","900",
                                   str(src),"--out",str(dst)],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL,
                                  timeout=25)
            if result.returncode==0 and dst.exists():
                return dst.read_bytes()
    return None

def fetch_retail_covers(ftp, folder, maximum_titles=150, force=False):
    """Download LaunchBox regional scans directly to owner's PS5 via FTP.
    Build ZIP ships text index only; third-party scans never enter repository.
    """
    index=folder/"assets/niak-launchbox-cases.tsv"
    if not index.is_file():
        print("LaunchBox: index absent du paquet. Aucun téléchargement possible.")
        return 0
    installed=set(_installed_title_ids(ftp,maximum_titles))
    if not installed:
        print("LaunchBox: aucun titre trouvé par FTP dans les dossiers autorisés.")
        return 0
    import urllib.request
    import urllib.error
    cached=_remote_filenames(ftp,f"/data/homebrew/{TITLE}/assets/niak-cases") or set()
    shipped=0
    indexed_matches=0
    attempted=0
    failed_http={}
    failed_network=0
    failed_image=0
    failed_ftp=0
    for line in index.read_text("utf8").splitlines():
        if not line or line.startswith("#"):continue
        columns=line.split("\t")
        if len(columns)<7 or columns[0] not in installed:continue
        ident=columns[0]
        indexed_matches+=1
        if indexed_matches>maximum_titles:break
        # Metadata fields: ID, description, front, back, spine, logo, sourceID.
        for side,field in (("front",2),("back",3),("spine",4),("logo",5)):
            destination=f"/data/homebrew/{TITLE}/assets/niak-cases/{ident}-{side}.png"
            if posixpath.basename(destination) in cached and not force:
                continue
            choices=columns[field]
            if choices=="-":continue
            for candidate in choices.split(";")[:8]:
                parts=candidate.split(":",1)
                if len(parts)!=2:continue
                name=parts[1]
                if not re.fullmatch(r"(?:r2_)?[0-9A-Fa-f-]{36}\.(?:jpe?g|png)",name):
                    continue
                attempted+=1
                url="https://images.launchbox-app.com/"+name
                try:
                    req=urllib.request.Request(url,headers={
                        "User-Agent":"NiakPS5-private-FTP-art/1.0"})
                    with urllib.request.urlopen(req,timeout=10) as response:
                        raw=response.read(5*1024*1024+1)
                except urllib.error.HTTPError as error:
                    failed_http[error.code]=failed_http.get(error.code,0)+1
                    continue
                except (OSError,TimeoutError,ValueError):
                    failed_network+=1
                    continue
                if not raw or len(raw)>5*1024*1024:
                    failed_image+=1
                    continue
                try:
                    png=_decode_retail_image(raw,side)
                except (OSError,ValueError,TimeoutError):
                    failed_image+=1
                    continue
                if not png or len(png)>3*1024*1024:
                    failed_image+=1
                    continue
                try:
                    upload(ftp,destination,png)
                except (OSError,ValueError):
                    failed_ftp+=1
                    continue
                cached.add(posixpath.basename(destination))
                shipped+=1
                break
    print(f"LaunchBox: {len(installed)} titres installés visibles par FTP, "
          f"{indexed_matches} correspondances exactes, {attempted} visuels tentés, "
          f"{shipped} fichiers transférés.")
    if any((failed_http,failed_network,failed_image,failed_ftp)):
        codes=", ".join(f"{code}: {count}" for code,count in sorted(failed_http.items()))
        print("LaunchBox diagnostic : "
              f"HTTP [{codes or 'aucun'}], réseau={failed_network}, "
              f"images rejetées={failed_image}, FTP refusé={failed_ftp}.")
        if failed_http.get(403) or failed_http.get(429):
            print("LaunchBox : source distante restreinte ou limitée ; "
                  "conserver le cache et utiliser le boîtier reconstruit.")
        if failed_ftp:
            print("LaunchBox : écriture des visuels non autorisée ; "
                  "vérifier l'accès FTP à /data/homebrew/PPSA99386/assets/niak-cases.")
    if not indexed_matches:
        print("LaunchBox: vérifier le nom/version du titre dans l'index; "
              "aucune jaquette ne peut être déduite d'un identifiant seul.")
    return shipped



def _name_index(ftp,folder):
    """Use real local PS5 param.json names first, packaged public index second."""
    result={}
    for raw in (
        _bounded_retrieve(ftp,f"/data/homebrew/{TITLE}/assets/niak-local-titles.tsv"),
        (folder/"assets/niak-ps-titles.tsv").read_bytes()
            if (folder/"assets/niak-ps-titles.tsv").is_file() else None):
        if raw is None:continue
        for line in raw.decode("utf8","replace").splitlines():
            parts=line.split("\t")
            if len(parts)<2:continue
            ident,name=parts[:2]
            if re.fullmatch(r"(PPSA|CUSA|LAPY|FAKE)[0-9]{5}",ident) and 2<len(name)<=120:
                result.setdefault(ident,name)
    return result


def fetch_alternative_covers(ftp,folder,maximum_titles=150,force=False):
    """Supplement missing private LaunchBox scans with optional API providers.

    Keys are supplied through the calling COMPUTER'S environment only, never
    saved to PS5, title assets, Git, logs or command-line arguments. Platform
    checking and image-domain allowlists are enforced by cover_sources.py.
    """
    import os,importlib.util,urllib.request
    tgdb=os.environ.get("NIAK_THEGAMESDB_KEY","").strip()
    sgdb=os.environ.get("NIAK_STEAMGRIDDB_KEY","").strip()
    if not (tgdb or sgdb):
        print("Sources alternatives: inactives (clés API non configurées sur l'ordinateur).")
        return 0
    module=Path(__file__).resolve().with_name("cover_sources.py")
    if not module.is_file():
        print("Sources alternatives: module cover_sources.py absent du paquet.")
        return 0
    spec=importlib.util.spec_from_file_location("niak_cover_sources",module)
    providers=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(providers)
    ids=_installed_title_ids(ftp,maximum_titles)
    names=_name_index(ftp,folder)
    cached=_remote_filenames(ftp,f"/data/homebrew/{TITLE}/assets/niak-cases") or set()
    total=0
    requests=0
    used={"thegamesdb":0,"steamgriddb":0}
    for ident in ids:
        name=names.get(ident)
        if not name:continue
        paths={side:f"/data/homebrew/{TITLE}/assets/niak-cases/{ident}-{side}.png"
               for side in ("front","back")}
        missing={side for side,path in paths.items()
                 if force or posixpath.basename(path) not in cached}
        if not missing:continue
        platform="ps5" if ident.startswith("PPSA") else "ps4"
        def candidate_sources():
            nonlocal requests
            if tgdb:
                requests+=1
                try:
                    yield "thegamesdb",providers.tgdb_cover_urls(name,platform,tgdb)
                except (OSError,ValueError,KeyError,TypeError):
                    # Never print exceptions containing API URLs or credentials.
                    yield "thegamesdb",{}
            # Query the community provider ONLY after the physical-cover
            # provider has actually failed to deliver a valid FRONT scan.
            if sgdb and "front" in missing:
                requests+=1
                try:
                    yield "steamgriddb",providers.steamgriddb_portrait_url(name,sgdb)
                except (OSError,ValueError,KeyError,TypeError):
                    yield "steamgriddb",{}
        for source,art in candidate_sources():
            for side in ("front","back"):
                if side not in missing:continue
                url=art.get(side) if isinstance(art,dict) else None
                if not providers.trusted_image_url(url):continue
                try:
                    req=urllib.request.Request(url,headers={
                        "User-Agent":"NiakPS5-private-FTP-art/1.1"})
                    with urllib.request.urlopen(req,timeout=12) as response:
                        # HTTP redirects must not escape the image CDN.
                        redirected=getattr(response,"geturl",lambda:url)()
                        if not providers.trusted_image_url(redirected):
                            continue
                        raw=response.read(5*1024*1024+1)
                    if not raw or len(raw)>5*1024*1024:continue
                    png=_decode_retail_image(raw,side)
                    if not png or len(png)>3*1024*1024:continue
                    upload(ftp,paths[side],png)
                    cached.add(posixpath.basename(paths[side]))
                    missing.remove(side)
                    used[source]+=1
                    total+=1
                except (OSError,ValueError,TimeoutError):
                    continue
    print(f"Sources alternatives : {len(ids)} titres inspectés, "
          f"{requests} recherches, {used['thegamesdb']} scans TheGamesDB, "
          f"{used['steamgriddb']} illustrations SteamGridDB copiées en privé.")
    if sgdb:
        print("SteamGridDB : illustrations communautaires de face AVANT seulement, "
              "pas des jaquettes PS5/PS4 physiques garanties.")
    return total


def _listed(ftp,path):
    """An unavailable FTP directory is unknown, never assumed empty."""
    try:
        return {str(x) for x in ftp.nlst(path)}
    except (error_perm,AttributeError,OSError):
        return None


def _remote_filenames(ftp,path):
    """Normalize both absolute and basename-only LIST replies, read-only.

    FTP daemons may return /data/foo/image.png, image.png, or foo/image.png.
    Compare by basename only INSIDE the already scoped artwork directory.
    None means the listing could not be read; it does not mean the directory
    contains no media.
    """
    entries=_listed(ftp,path)
    if entries is None:return None
    return {posixpath.basename(name.rstrip("/")) for raw in entries
            if (name:=str(raw)) and name not in (".","..")}


def installed_binary_matches(ftp,local_binary,remote_path=None,maximum=150*1024*1024):
    """Stream hashes read-only, with a hard byte bound; never copy PS5 binaries."""
    target=remote_path or f"/data/homebrew/{TITLE}/eboot.bin"
    local=Path(local_binary)
    if not local.is_file() or local.stat().st_size>maximum:
        return None
    expected=hashlib.sha256()
    with local.open("rb") as source:
        for block in iter(lambda:source.read(65536),b""):
            expected.update(block)
    observed=hashlib.sha256()
    total=0
    def read(block):
        nonlocal total
        total+=len(block)
        if total>maximum:raise ValueError("Installed binary exceeds safety bound")
        observed.update(block)
    try:
        ftp.retrbinary("RETR "+target,read,blocksize=65536)
    except (error_perm,OSError,ValueError):
        return None
    return total==local.stat().st_size and observed.digest()==expected.digest()


def diagnose_title_registration(ftp):
    """Read-only ShadowMountPlus discovery preflight, NEVER title registration."""
    path=f"/data/homebrew/{TITLE}/sce_sys/param.json"
    try:
        manifest=_bounded_retrieve(ftp,path,limit=64*1024)
    except (OSError,ValueError):
        manifest=None
    if manifest is None:
        print("Titre param.json : absent ou inaccessible (enregistrement inconnu)")
    else:
        try:
            title=json.loads(manifest)
            valid=(isinstance(title,dict) and title.get("titleId")==TITLE)
        except (ValueError,UnicodeDecodeError):
            valid=False
        print("Titre param.json cohérent :",valid)
        if not valid:
            print("Attention : ShadowMountPlus peut refuser un titre sans param.json valide.")
    # This scanner's default includes /data/homebrew, but an explicit
    # scanpath list replaces the defaults. Never assume a custom root also
    # includes its siblings, or change a third-party mount configuration.
    try:
        raw=_bounded_retrieve(ftp,"/data/shadowmount/config.ini",limit=128*1024)
    except (OSError,ValueError):
        raw=None
    if raw is None:
        print("ShadowMountPlus : config.ini absent/inaccessible ; inscription non vérifiable")
        return
    try:
        settings=raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        print("ShadowMountPlus : config.ini non décodable ; scanpath inconnu")
        return
    roots=[]
    for line in settings.splitlines():
        entry=line.strip()
        if not entry or entry.startswith(("#",";")) or "=" not in entry:
            continue
        key,value=entry.split("=",1)
        if key.strip().lower()=="scanpath":
            root=value.strip().rstrip("/")
            if root:roots.append(root)
    if not roots:
        print("ShadowMountPlus : chemins de scan par défaut (dont /data/homebrew)")
        return
    if "/data/homebrew" in roots:
        print("ShadowMountPlus : /data/homebrew présent dans scanpath")
    else:
        print("ATTENTION : scanpath personnalisé sans /data/homebrew ; "
              "NiakPS5 ne sera pas découvert à son emplacement actuel.")
    print("ShadowMountPlus : scanpath contrôlé, inscription effective encore inconnue")


def diagnose_appdb_registration(ftp):
    """Check title registration against a bounded, read-only app.db snapshot.

    A file in /data/homebrew is not proof of registration. Queries operate
    ONLY on a separate in-memory SQLite snapshot, never on the console DB.
    Unreadable, oversized, WAL-inconsistent or unfamiliar DBs stay UNKNOWN.
    """
    import sqlite3
    try:
        image=_bounded_retrieve(ftp,"/system_data/priv/mms/app.db",
                                limit=64*1024*1024)
    except (OSError,ValueError):
        image=None
    if not image or not image.startswith(b"SQLite format 3\x00"):
        print("Enregistrement app.db : inconnu (FTP inaccessible ou DB non exploitable)")
        return
    db=None
    try:
        db=sqlite3.connect(":memory:")
        db.deserialize(image)
        db.execute("PRAGMA query_only=ON")
        recognized=0
        for table in ("tbl_contentinfo","tbl_appbrowse","tbl_appinfo"):
            try:
                found=db.execute(
                    f"SELECT 1 FROM {table} WHERE titleId=? LIMIT 1",
                    (TITLE,)).fetchone()
                recognized+=1
                if found:
                    print("Enregistrement app.db : PPSA99386 trouvé "
                          f"(copie en lecture seule, {table})")
                    return
            except sqlite3.DatabaseError:
                continue
        if recognized:
            print("Enregistrement app.db : PPSA99386 absent de la copie reçue "
                  "(possiblement non enregistré ou instantané incomplet)")
        else:
            print("Enregistrement app.db : schéma inconnu ; résultat indéterminé")
    except (sqlite3.Error,AttributeError,MemoryError):
        print("Enregistrement app.db : copie illisible ; résultat indéterminé")
    finally:
        if db is not None:db.close()


def interpret_broker_log(report, clock=None):
    """History only. Does not assert a live process without a PING response."""
    import time
    if clock is None:clock=int(time.time())
    section=report[report.rfind("NiakPS5 optional autostart start"):]
    if "NiakPS5 optional autostart start" not in section:
        return ("non confirmée","aucun horodatage exploitable")
    records=section.splitlines()
    syscalls=[i for i,line in enumerate(records)
              if line.startswith("sceSystemServiceLaunchApp rc=")]
    if not syscalls:
        launch="non confirmée"
    else:
        last=syscalls[-1]
        syscall=records[last]
        subsequent=records[last+1:]
        if syscall.endswith("rc=0x00000000"):
            launch="succès HISTORIQUE (SystemService)"
        elif any(x.startswith("sceLncUtilLaunchApp accepted app id rc=")
                 for x in subsequent):
            launch="succès HISTORIQUE (LncUtil)"
        elif any(x.startswith("sceLncUtilLaunchApp refused rc=") or
                 x.startswith("sceLncUtilLaunchApp returned invalid app id rc=")
                 for x in subsequent):
            launch="échec historique (SystemService et LncUtil)"
        else:
            launch="échec historique (SystemService, repli non confirmé)"
    import re
    events=[(int(a),int(b)) for a,b in re.findall(
        r"(?m)^NiakPS5 broker heartbeat epoch=(\d+) pid=(\d+)\s*$",section)]
    if not events:
        heartbeat="aucun horodatage exploitable"
    else:
        stamp,pid=events[-1]
        age=clock-stamp
        if -60<=age<=300:
            heartbeat=f"activité récente dans le journal, PID {pid} (pas une preuve de processus vivant)"
        elif age>300:
            heartbeat=f"dernier battement ancien, PID {pid}"
        else:
            heartbeat="horloge PS5/Mac incohérente ; état inconnu"
    return launch,heartbeat


def diagnose(ftp,local_directory=None):
    """Read-only PS5 deployment report. Never edit system/app databases."""
    app=f"/data/homebrew/{TITLE}"
    files=_listed(ftp,app)
    assets=_listed(ftp,app+"/assets")
    covers=_listed(ftp,app+"/assets/niak-cases")
    installed_art=_remote_filenames(ftp,app+"/assets/niak-installed")
    templates=_listed(ftp,app+"/assets/niak-templates")
    payloads=_listed(ftp,"/data/pldmgr/payloads/niakps5")
    def known(state):
        return "accès refusé / inconnu" if state is None else str(state)
    def present(entries,name):
        # LIST may return basename-only, a relative name, or an absolute path.
        # It is a read-only diagnostic, not an installation integrity proof.
        return None if entries is None else name in {
            posixpath.basename(str(value).rstrip("/")) for value in entries}
    print("NiakPS5 — diagnostic local (aucun fichier modifié)")
    print("Titre eboot.bin :",known(present(files,"eboot.bin")))
    diagnose_title_registration(ftp)
    diagnose_appdb_registration(ftp)
    if local_directory is not None:
        comparison=installed_binary_matches(
            ftp,Path(local_directory)/"eboot.bin")
        print("Binaire identique au paquet local :",known(comparison))
        if comparison is False:
            print("Attention : le binaire PS5 est différent de celui du paquet ; "
                  "l'interface peut encore être une ancienne révision.")
    print("Index LaunchBox :",known(present(assets,"niak-launchbox-cases.tsv")))
    print("Métadonnées locales :",known(present(assets,"niak-local-titles.tsv")))
    print("Avatar copié :",known(None if assets is None else any(
        present(assets,name) for name in ("niak-profile.png","niak-profile.dds"))))
    if installed_art is None:
        print("Icônes/fonds en cache : accès inconnu / refusé")
    else:
        print("Icônes/fonds en cache :",
              sum(name.endswith("-icon.png") for name in installed_art),"icônes,",
              sum(name.endswith("-scene.png") for name in installed_art),"fonds")
    if templates is None: print("Gabarits 3D privés : accès inconnu / refusé")
    else:
        files={str(x).rsplit("/",1)[-1] for x in templates}
        print("Gabarits 3D privés :",len(files&TEMPLATE_NAMES),"/6")
    if covers is None: print("Jaquettes privées : accès refusé / inconnu")
    else:
        art={posixpath.basename(str(x).rstrip("/")) for x in covers}
        print("Jaquettes privées :",sum(name.endswith("-front.png") for name in art),
              "rectos,",sum(name.endswith("-back.png") for name in art),"versos,",
              sum(name.endswith("-spine.png") for name in art),"tranches")
        # Read-only, bounded per-title diagnostic: one global count is not
        # enough to explain blank PS4/PS5 cases on a real installation.
        scanned=_installed_title_ids(ftp,300)
        if scanned:
            empty_front=[ident for ident in scanned
                         if f"{ident}-front.png" not in art]
            empty_back=[ident for ident in scanned
                        if f"{ident}-back.png" not in art]
            empty_spine=[ident for ident in scanned
                         if f"{ident}-spine.png" not in art]
            print(f"Couverture des {len(scanned)} titres visibles : "
                  f"{len(scanned)-len(empty_front)} rectos, "
                  f"{len(scanned)-len(empty_back)} versos, "
                  f"{len(scanned)-len(empty_spine)} tranches.")
            if empty_front:
                print("Sans recto privé (30 premiers) :",", ".join(empty_front[:30]))
                print("Ces titres peuvent néanmoins afficher un boîtier reconstruit "
                      "depuis icon0/pic1 si ces fichiers sont accessibles.")
        else:
            print("Titres installés visibles : non vérifiables par FTP. "
                  "Ne pas déduire que la bibliothèque PS5 est vide.")
    print("Payload ELF :",known(present(payloads,"niakps5.elf")))
    if local_directory is not None:
        elf_match=installed_binary_matches(
            ftp,Path(local_directory)/"tools/niakps5/niakps5.elf",PAYLOAD,
            maximum=20*1024*1024)
        print("Payload PLDmgr identique au paquet :",known(elf_match))
        if elf_match is False:
            print("Attention : le payload est ancien. Le service Jouer "
                  "ne peut pas être considéré comme installé.")
    autoload=retrieve(ftp,AUTOLOAD)
    config=retrieve(ftp,CONFIG)
    configured=(autoload is not None and
                any(v.strip() in (PAYLOAD,AUTOLOAD_NAME) for v in
                    autoload.decode("utf8","replace").splitlines()))
    enabled=config is not None and "AUTOLOAD_ENABLED=1" in config.decode("utf8","replace").splitlines()
    print("PLDmgr chemin configuré :",configured if autoload is not None else "inconnu")
    print("PLDmgr AUTOLOAD_ENABLED :",enabled if config is not None else "inconnu")
    # Markers prove configuration only; not execution. Never call it "working"
    # unless the user's PS5 log records a successful service call.
    marker=_listed(ftp,"/data")
    print("Marqueur activation :",known(present(marker,"niakps5-autostart.enabled")))
    print("Marqueur désactivation :",known(present(marker,"niakps5-autostart.disable")))
    try: log=_bounded_retrieve(ftp,"/data/niakps5-autostart.log")
    except (OSError,ValueError): log=None
    if log:
        history,heartbeat=interpret_broker_log(log.decode("utf8","replace"))
        print("Dernière exécution PLDmgr :",history)
        print("Courtier ELF (journal) :",heartbeat)
    else:
        print("Dernière exécution PLDmgr : journal absent ou non lisible")
        print("Courtier ELF (journal) : activité inconnue")
    print("Un succès historique ne prouve pas le démarrage automatique actuel.")


# Six privately supplied, user-owned case overlay files.
TEMPLATE_NAMES={f"{platform}-{side}.png"
                for platform in ("ps4","ps5")
                for side in ("front","back","spine")}

def upload_case_templates(ftp,directory):
    """Send only recognized, bounded PNG templates to the owner's PS5."""
    folder=directory/"assets"/"niak-templates"
    if not folder.is_dir():return 0
    entries=list(folder.iterdir())
    for path in entries:
        if path.is_symlink() or not path.is_file() or path.name not in TEMPLATE_NAMES:
            raise ValueError("Unrecognized private template file")
    for path in entries:
        content=path.read_bytes()
        if not 33<=len(content)<=3*1024*1024 or content[:8]!=b"\x89PNG\r\n\x1a\n":
            raise ValueError("Invalid case template PNG")
        width=int.from_bytes(content[16:20],"big")
        height=int.from_bytes(content[20:24],"big")
        part=path.stem.split("-",1)[1]
        if part=="spine": valid=40<=width<=200 and 350<=height<=1600
        elif part=="front": valid=450<=width<=2000 and 60<=height<=400
        else: valid=450<=width<=1600 and 220<=height<=900
        if not valid or width*height>2500000:
            raise ValueError("Invalid case template proportions")
        upload(ftp,f"/data/homebrew/{TITLE}/assets/niak-templates/{path.name}",content)
    if entries:
        print(f"Boîtiers 3D : {len(entries)}/6 gabarits personnels envoyés. "
              "Relancer NiakPS5 pour recharger les textures.")
    return len(entries)


def validate_install_folder(directory, autoload):
    """Refuse incomplete or mismatched extracted titles BEFORE any FTP write."""
    if directory.name != TITLE or not directory.is_dir() or directory.is_symlink():
        raise ValueError("Expected extracted PPSA99386/ folder")
    for name in ("eboot.bin", "sce_module/libc.prx", "sce_sys/param.json"):
        target=directory/name
        if not target.is_file() or target.is_symlink() or not target.stat().st_size:
            raise ValueError(f"Required PS5 title file missing or empty: {name}")
    try:
        metadata=json.loads((directory/"sce_sys/param.json").read_text("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Malformed PS5 param.json") from exc
    if not isinstance(metadata,dict) or metadata.get("titleId")!=TITLE:
        raise ValueError("PS5 title ID does not match PPSA99386")
    for entry in directory.rglob("*"):
        if entry.is_symlink():
            raise ValueError("Installation directory must not contain symlinks")
        if entry.is_file() and entry.suffix.lower()==".zip":
            raise ValueError("Nested ZIP detected; extract only the single download")
    if autoload:
        elf=directory/"tools/niakps5/niakps5.elf"
        if not elf.is_file() or elf.is_symlink():
            raise ValueError("One-shot payload ELF missing")
        with elf.open("rb") as stream:
            if stream.read(4)!=b"\x7fELF":
                raise ValueError("Invalid one-shot ELF; no FTP changes made")
        sidecar=directory/"tools/niakps5/niakps5.elf.json"
        if not sidecar.is_file() or sidecar.is_symlink():
            raise ValueError("PLDmgr metadata is missing")
        try:
            info=json.loads(sidecar.read_text("utf-8"))
        except (UnicodeDecodeError, OSError, ValueError) as exc:
            raise ValueError("PLDmgr metadata is malformed") from exc
        import hashlib
        if not isinstance(info,dict) or info.get("filename")!=elf.name or (
            info.get("checksum")!=hashlib.sha256(elf.read_bytes()).hexdigest()
        ):
            raise ValueError("PLDmgr sidecar doesn't match the bundled ELF")


def install(ftp, directory, autoload, return_after_game=False, avatar_user_id=None, art_limit=150,
            preserve_autoload=False):
    # Preserve the user's already-working PLDmgr configuration when requested.
    # This mode still replaces the companion ELF and its checksum sidecar.
    validate_install_folder(directory, autoload or preserve_autoload)
    for local in sorted(directory.rglob("*")):
        if local.is_symlink():
            raise ValueError("Symlinks are not accepted")
        if local.is_file():
            relative = local.relative_to(directory).as_posix()
            if relative.startswith("assets/niak-templates/"):
                # Private template overlays are staged separately.
                continue
            if relative.startswith("tools/"):
                # The self-install helper reads these TWO packaged files from
                # /app0/tools/niakps5/. Never ship unrelated installer scripts
                # into the title or silently opt in with --no-autoload.
                payload_assets={"tools/niakps5/niakps5.elf",
                                "tools/niakps5/niakps5.elf.json"}
                if (relative not in payload_assets or
                    not (autoload or preserve_autoload)):
                    continue
            upload(ftp, f"/data/homebrew/{TITLE}/{relative}", local.read_bytes())
    copy_avatar_for_ftp(ftp,avatar_user_id)
    upload_case_templates(ftp,directory)
    upload_local_homebrew_names(ftp)
    stage_installed_artwork(ftp,art_limit)
    fetch_retail_covers(ftp,directory,art_limit)
    fetch_alternative_covers(ftp,directory,art_limit)
    if not autoload and not preserve_autoload:
        print("Titre installe sans modification du payload ou de PLDmgr.")
        return
    elf = directory / "tools/niakps5/niakps5.elf"
    # ELF identity verified before the first FTP write.
    if preserve_autoload:
        upload(ftp, PAYLOAD, elf.read_bytes())
        metadata=directory/"tools/niakps5/niakps5.elf.json"
        if metadata.is_file():
            upload(ftp, PAYLOAD_META, metadata.read_bytes())
        print("Titre + niakps5.elf mis à jour. autoload.txt, config et marqueurs conserves.")
        return

    # Preflight both PLDmgr files BEFORE writing payload, configuration or
    # markers. A malformed config must not leave half-enabled autoload.
    original = retrieve(ftp, AUTOLOAD)
    raw = retrieve(ftp, CONFIG)
    if original is not None and (len(original)>3500 or b"\0" in original):
        raise ValueError("Unexpected autoload.txt; left untouched")
    if raw is not None and (len(raw)>65536 or b"\0" in raw):
        raise ValueError("Unexpected PLDmgr config; left untouched")
    try:
        entries = (original or b"").decode("utf-8").splitlines()
        lines = (raw or b"").decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("Unexpected PLDmgr text encoding; left untouched") from exc
    # The user's PLDmgr uses slot basenames, not absolute paths. Preserve
    # every pre-existing line and payload ordering; move ours to the END.
    prior_keys=(PAYLOAD,AUTOLOAD_NAME)
    already_installed=any(line.strip() in prior_keys for line in entries)
    if already_installed:
        # Never rewrite or reorder a correct existing autoload.txt.
        body=original
    else:
        entries=[line for line in entries if line.strip() not in prior_keys]
        entries.append(AUTOLOAD_NAME)
        body = ("\n".join(entries).rstrip() + "\n").encode()
    if len(body)>4095:
        raise ValueError("Autoload file too large; no changes")

    if "AUTOLOAD_ENABLED=1" in lines:
        config_body=raw  # Keep existing working PLDmgr settings byte-for-byte.
    else:
        lines = [line for line in lines if not line.startswith("AUTOLOAD_ENABLED=")]
        lines.append("AUTOLOAD_ENABLED=1")
        config_body=("\n".join(lines)+"\n").encode()

    # Preserve FIRST-install backups across subsequent runs. Backing up an
    # already modified config would destroy the only useful rollback copy.
    if not already_installed:
        if original is not None and retrieve(ftp,AUTOLOAD+".niakps5.bak") is None:
            upload(ftp,AUTOLOAD+".niakps5.bak",original)
        if raw is not None and retrieve(ftp,CONFIG+".niakps5.bak") is None:
            upload(ftp,CONFIG+".niakps5.bak",raw)
    return_flag="/data/niakps5-return-after-game.enabled"
    if not return_after_game and retrieve(ftp,return_flag) is not None:
        # A failed opt-out must stop BEFORE the new payload/configuration is
        # written, rather than leaving a partially reconfigured installation.
        ftp.delete(return_flag)
    upload(ftp, PAYLOAD, elf.read_bytes())
    metadata=directory/"tools/niakps5/niakps5.elf.json"
    if metadata.is_file():
        upload(ftp, PAYLOAD_META, metadata.read_bytes())
    if original!=body:
        upload(ftp, AUTOLOAD, body)
    if raw!=config_body:
        upload(ftp, CONFIG, config_body)
    # Activate only once both the binary and the autoload configuration exist.
    upload(ftp, "/data/niakps5-autostart.enabled", b"")
    if return_after_game:
        upload(ftp, return_flag, b"")
    print("Autoload configure en derniere position. Desactiver via le fichier")
    print("/data/niakps5-autostart.disable ou retirer l'entree du Payload Manager.")

def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--host", required=True, help="Adresse IP de la PS5, reseau local uniquement")
    cli.add_argument("--port", type=int, default=2121)
    cli.add_argument("--user", default="anonymous")
    cli.add_argument("--avatar-user-id", default=None,
                     help="Specific current PS5 profile ID if multiple users exist")
    # One FTP installation command configures the one-shot autoload by default.
    # A simple folder copy cannot configure Payload Manager by itself.
    cli.add_argument("--autoload", dest="autoload", action="store_true", default=True,
                     help="Installer et activer le démarrage automatique (défaut)")
    cli.add_argument("--no-autoload", dest="autoload", action="store_false",
                     help="Transférer seulement le titre sans modifier Payload Manager")
    cli.add_argument("--preserve-autoload", action="store_true",
                     help="Installer le titre ET remplacer niakps5.elf, sans modifier la configuration PLDmgr")
    cli.add_argument("--status", action="store_true",
                     help="Vérifier les fichiers sur la PS5 sans rien modifier")
    cli.add_argument("--art-limit", type=int, default=150,
                     help="Limite des titres à enrichir avec les jaquettes (1–300)")
    cli.add_argument("--force-art", action="store_true",
                     help="Forcer le remplacement des scans déjà en cache (avec --refresh-art)")
    cli.add_argument("--refresh-art", action="store_true",
                     help="Rechercher les jaquettes des jeux installés sans toucher au titre ni à PLDmgr")
    cli.add_argument("--return-after-game", action="store_true",
                     help="Surveiller uniquement la fermeture d'un jeu, sans intercepter le bouton PS")
    args = cli.parse_args()
    if not 1<=args.art_limit<=300:
        cli.error("--art-limit doit être entre 1 et 300")
    if args.force_art and not args.refresh_art:
        cli.error("--force-art exige --refresh-art")
    if args.return_after_game and (not args.autoload or args.preserve_autoload) and not args.refresh_art and not args.status:
        cli.error("--return-after-game requires --autoload without --preserve-autoload")
    directory = Path(__file__).resolve().parent.parent
    password = "" if args.user == "anonymous" else getpass("Mot de passe FTP: ")
    with FTP() as ftp:
        ftp.connect(args.host, args.port, timeout=20)
        ftp.login(args.user, password)
        if args.status:
            diagnose(ftp,directory)
        elif args.refresh_art:
            upload_case_templates(ftp,directory)
            upload_local_homebrew_names(ftp)
            stage_installed_artwork(ftp,args.art_limit,force=args.force_art)
            fetch_retail_covers(ftp, directory, args.art_limit, force=args.force_art)
            # A forced LaunchBox repair must NOT overwrite its valid scans
            # with a community grid or another provider.
            fetch_alternative_covers(ftp, directory, args.art_limit)
        else:
            install(ftp, directory, args.autoload and not args.preserve_autoload,
                    args.return_after_game,args.avatar_user_id,args.art_limit,
                    preserve_autoload=args.preserve_autoload)

if __name__ == "__main__":
    main()
