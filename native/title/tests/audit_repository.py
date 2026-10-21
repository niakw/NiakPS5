#!/usr/bin/env python3
"""Basic fail-closed current-tree privacy scan; not a Git-history scrub."""
import re
import subprocess
from pathlib import Path

patterns = {
    "secret token": re.compile(r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{20,})\b"),
    "email address": re.compile(r"\b[a-zA-Z0-9._%+-]+@(?:gmail|outlook|hotmail|icloud|yahoo)\.[A-Za-z]{2,}\b"),
    "local user path": re.compile(r"(?:/Users/[A-Za-z0-9_-]+/|/home/[A-Za-z0-9_-]+/|C:\\Users\\[A-Za-z0-9_-]+\\)"),
    "private LAN address": re.compile(r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"),
}
ignore = {".ttf", ".woff", ".woff2", ".png", ".jpg", ".jpeg", ".ico", ".zip", ".elf"}
paths = subprocess.check_output(["git","ls-files","-z"]).split(b"\0")
errors = []
count = 0
for raw in paths:
    if not raw:
        continue
    path = Path(raw.decode("utf-8"))
    if path.suffix.lower() in ignore:
        continue
    try:
        content = path.read_text("utf-8")
    except UnicodeError:
        continue
    count += 1
    for label, matcher in patterns.items():
        for match in matcher.finditer(content):
            # Never print the candidate value itself.
            line = content.count("\n",0,match.start())+1
            errors.append(f"{path}:{line} possible {label}")
if errors:
    print("\n".join(errors))
    raise SystemExit(1)
print(f"Privacy scan: {count} text files, no configured sensitive patterns detected.")
