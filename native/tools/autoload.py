#!/usr/bin/env python3
"""Reversible NiakPS5 autoloader block editor. Runs on a mounted/staged folder, never the PS5 remotely."""
from __future__ import annotations
import argparse
import os
import pathlib
import shutil
import tempfile
from datetime import datetime, timezone

BEGIN = "# BEGIN NIAKPS5 - generated; use this tool to disable"
END = "# END NIAKPS5"
BLOCK = f"{BEGIN}\n!5000\nniakps5_bootstrap.elf\n{END}\n"


def patched(original: str, enabled: bool) -> str:
    """Only add or remove our own unique block. Never reorder existing payloads."""
    lines = original.splitlines(keepends=True)
    output: list[str] = []
    inside = False
    seen = False
    for line in lines:
        text = line.rstrip("\r\n")
        if text == BEGIN:
            if inside or seen:
                raise ValueError("Duplicated or nested NiakPS5 markers: file unchanged")
            inside = True
            seen = True
            continue
        if text == END:
            if not inside:
                raise ValueError("Orphan NiakPS5 end marker: file unchanged")
            inside = False
            continue
        if not inside:
            output.append(line)
    if inside:
        raise ValueError("Unclosed NiakPS5 marker: file unchanged")
    data = "".join(output)
    if enabled:
        if data and not data.endswith("\n"):
            data += "\n"
        data += BLOCK
    return data


def apply(config: pathlib.Path, enabled: bool, confirmed_manual_launch: bool, commit: bool) -> str:
    if config.name != "autoload.txt" or config.parent.name != "ps5_autoloader":
        raise ValueError("Only a ps5_autoloader/autoload.txt file is permitted")
    if config.is_symlink() or config.parent.is_symlink():
        raise ValueError("Symbolic links are refused")
    if enabled:
        if not confirmed_manual_launch:
            raise ValueError("Enable requires --confirmed-manual-launch; first validate on the console")
        loader = config.parent / "niakps5_bootstrap.elf"
        if not loader.is_file() or loader.is_symlink():
            raise ValueError("Missing niakps5_bootstrap.elf beside autoload.txt")
    original = config.read_text(encoding="utf-8") if config.exists() else ""
    updated = patched(original, enabled)
    if updated == original or not commit:
        return updated
    # Copy old config before modification; create a unique timestamped backup.
    if config.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        shutil.copy2(config, config.with_name("autoload.txt.niakps5-backup-" + ts))
    fd, temporary = tempfile.mkstemp(prefix=".autoload.niakps5-", dir=config.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, config)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely add/remove an optional NiakPS5 bootstrap autostart block")
    parser.add_argument("config", type=pathlib.Path, help="Path to mounted ps5_autoloader/autoload.txt")
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--enable", action="store_true")
    options.add_argument("--disable", action="store_true")
    parser.add_argument("--confirmed-manual-launch", action="store_true",
                        help="Confirm that the bootstrap, game launches and Circle fallback were tested on PS5")
    parser.add_argument("--apply", action="store_true", help="Write with timestamped backup; default is preview only")
    args = parser.parse_args()
    try:
        contents = apply(args.config, args.enable, args.confirmed_manual_launch, args.apply)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(("Updated" if args.apply else "Preview, no file written") + ": " + str(args.config))
    print("----- autoload.txt -----")
    print(contents, end="" if contents.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
