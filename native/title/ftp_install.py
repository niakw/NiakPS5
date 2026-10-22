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
from pathlib import Path
import posixpath
import re
import json

TITLE = "PPSA99386"
PAYLOAD = "/data/pldmgr/payloads/niakps5/niakps5.elf"
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

def _bounded_retrieve(ftp,path):
    out=BytesIO()
    def feed(block):
        if out.tell()+len(block)>MAX_AVATAR:
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
        upload(ftp,f"/data/homebrew/{TITLE}/assets/niak-profile{suffix}",blob)
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
    for root in roots:
      try: entries=ftp.nlst(root)
      except (error_perm,AttributeError,OSError):continue
      for dirname in entries[:300]:
        ident=posixpath.basename(dirname.rstrip("/"))
        if not re.fullmatch(r"(PPSA|CUSA)[0-9]{5}",ident):continue
        try: body=_bounded_retrieve(ftp,f"{root}/{ident}/sce_sys/param.json")
        except (OSError,ValueError):continue
        if not body or len(body)>65536:continue
        try: meta=json.loads(body)
        except (ValueError,UnicodeDecodeError):continue
        if not isinstance(meta,dict):continue
        # The shared parsing block continues below at this indentation.

        params=meta.get("localizedParameters") or {}
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
            if type(category) is int:
                if category==0:genre="Jeu"
                elif category in (65536,65792,66048):genre="Application"
            if title and "\t" not in title:
                records[ident]=(title,genre)
    if records:
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
            if re.fullmatch(r"(PPSA|CUSA)[0-9]{5}",ident):found.add(ident)
        if len(found)>=limit:break
    return sorted(found)[:limit]

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

def fetch_retail_covers(ftp, folder, maximum_titles=60):
    """Download LaunchBox regional scans directly to owner's PS5 via FTP.
    Build ZIP ships text index only; third-party scans never enter repository.
    """
    index=folder/"assets/niak-launchbox-cases.tsv"
    if not index.is_file():
        print("LaunchBox: index absent du paquet. Aucun téléchargement possible.")
        return 0
    installed=set(_installed_title_ids(ftp))
    if not installed:
        print("LaunchBox: aucun titre trouvé par FTP dans les dossiers autorisés.")
        return 0
    import urllib.request
    shipped=0
    indexed_matches=0
    attempted=0
    for line in index.read_text("utf8").splitlines():
        if not line or line.startswith("#"):continue
        columns=line.split("\t")
        if len(columns)<7 or columns[0] not in installed:continue
        ident=columns[0]
        indexed_matches+=1
        if indexed_matches>maximum_titles:break
        # Metadata fields: ID, description, front, back, spine, logo, sourceID.
        for side,field in (("front",2),("back",3),("spine",4),("logo",5)):
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
                    if not raw or len(raw)>5*1024*1024:continue
                    png=_decode_retail_image(raw,side)
                    if not png or len(png)>3*1024*1024:continue
                    upload(ftp,f"/data/homebrew/{TITLE}/assets/niak-cases/{ident}-{side}.png",png)
                    shipped+=1
                    break
                except (OSError,ValueError,TimeoutError,Exception) as exc:
                    # Keep icon/description fallbacks when LaunchBox is offline
                    # or a specific regional scan is malformed.
                    continue
    print(f"LaunchBox: {len(installed)} titres installés visibles par FTP, "
          f"{indexed_matches} correspondances exactes, {attempted} visuels tentés, "
          f"{shipped} fichiers transférés.")
    if not indexed_matches:
        print("LaunchBox: vérifier le nom/version du titre dans l'index; "
              "aucune jaquette ne peut être déduite d'un identifiant seul.")
    return shipped


def install(ftp, directory, autoload, return_after_game=False, avatar_user_id=None):
    if directory.name != TITLE or not (directory / "sce_sys/param.json").is_file():
        raise ValueError("Extract PPSA99386/ and run the installer inside that folder")
    for local in sorted(directory.rglob("*")):
        if local.is_symlink():
            raise ValueError("Symlinks are not accepted")
        if local.is_file():
            relative = local.relative_to(directory).as_posix()
            if relative.startswith("tools/"):
                continue
            upload(ftp, f"/data/homebrew/{TITLE}/{relative}", local.read_bytes())
    copy_avatar_for_ftp(ftp,avatar_user_id)
    upload_local_homebrew_names(ftp)
    fetch_retail_covers(ftp,directory)
    if not autoload:
        print("Titre installe. L'autoload n'est pas active sans --autoload.")
        return
    elf = directory / "tools/niakps5.elf"
    if not elf.is_file() or elf.read_bytes()[:4] != b"\x7fELF":
        raise ValueError("One-shot payload missing or not an ELF; refusing autoload changes")
    upload(ftp, PAYLOAD, elf.read_bytes())
    original = retrieve(ftp, AUTOLOAD)
    if original is not None:
        if len(original) > 3500 or b"\0" in original:
            raise ValueError("Unexpected autoload.txt; left untouched")
        upload(ftp, AUTOLOAD + ".niakps5.bak", original)
    entries = (original or b"").decode("utf-8").splitlines()
    # Absolute path accepted by modern pldmgr. Keep all existing payload order.
    if PAYLOAD not in [line.strip() for line in entries]:
        entries += ["!2000", PAYLOAD]
    body = ("\n".join(entries).rstrip() + "\n").encode()
    if len(body) > 4095:
        raise ValueError("Autoload file too large; no changes")
    upload(ftp, AUTOLOAD, body)
    # Explicit activation of the new entry without touching any other settings.
    raw = retrieve(ftp, CONFIG)
    if raw is not None:
        if len(raw) > 65536 or b"\0" in raw:
            raise ValueError("Unexpected config; do not change")
        upload(ftp, CONFIG + ".niakps5.bak", raw)
    lines = (raw or b"").decode("utf-8").splitlines()
    lines = [line for line in lines if not line.startswith("AUTOLOAD_ENABLED=")]
    lines.append("AUTOLOAD_ENABLED=1")
    upload(ftp, CONFIG, ("\n".join(lines)+"\n").encode())
    # Activate only once both the binary and the autoload configuration exist.
    upload(ftp, "/data/niakps5-autostart.enabled", b"")
    if return_after_game:
        upload(ftp, "/data/niakps5-return-after-game.enabled", b"")
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
    cli.add_argument("--refresh-art", action="store_true",
                     help="Rechercher les jaquettes des jeux installés sans toucher au titre ni à PLDmgr")
    cli.add_argument("--return-after-game", action="store_true",
                     help="Surveiller uniquement la fermeture d'un jeu, sans intercepter le bouton PS")
    args = cli.parse_args()
    if args.return_after_game and not args.autoload and not args.refresh_art:
        cli.error("--return-after-game requires --autoload")
    directory = Path(__file__).resolve().parent.parent
    password = "" if args.user == "anonymous" else getpass("Mot de passe FTP: ")
    with FTP() as ftp:
        ftp.connect(args.host, args.port, timeout=20)
        ftp.login(args.user, password)
        if args.refresh_art:
            upload_local_homebrew_names(ftp)
            fetch_retail_covers(ftp, directory)
        else:
            install(ftp, directory, args.autoload, args.return_after_game, args.avatar_user_id)

if __name__ == "__main__":
    main()
