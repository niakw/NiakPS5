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
    cli.add_argument("--autoload", action="store_true", help="Activer le lancement apres jailbreak")
    cli.add_argument("--return-after-game", action="store_true",
                     help="Surveiller uniquement la fermeture d'un jeu, sans intercepter le bouton PS")
    args = cli.parse_args()
    if args.return_after_game and not args.autoload:
        cli.error("--return-after-game requires --autoload")
    directory = Path(__file__).resolve().parent.parent
    password = "" if args.user == "anonymous" else getpass("Mot de passe FTP: ")
    with FTP() as ftp:
        ftp.connect(args.host, args.port, timeout=20)
        ftp.login(args.user, password)
        install(ftp, directory, args.autoload, args.return_after_game, args.avatar_user_id)

if __name__ == "__main__":
    main()
