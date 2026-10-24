#!/usr/bin/env python3
"""Fail-closed privacy audit of all tracked files in the CURRENT checkout.

Checks tracked text, path names, common API tokens, local account traces and
private credentials. No candidate secret value is printed. This is NOT a
complete audit of Git history, untracked files, past releases or image pixels.
"""
from pathlib import Path
import re
import subprocess

PATTERNS = {
    "GitHub/OpenAI/Slack-style token": re.compile(
        r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|"
        r"sk-[A-Za-z0-9_-]{24,}|xox[baprs]-[A-Za-z0-9-]{20,})\b"),
    "cloud access key": re.compile(
        r"\b(?:AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35})\b"),
    "private key block": re.compile(
        r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    "personal email": re.compile(
        r"\b[a-zA-Z0-9._%+-]+@"
        r"(?:gmail|outlook|hotmail|icloud|yahoo|protonmail)\.[A-Za-z]{2,}\b"),
    "personal machine path": re.compile(
        r"(?:/Users/[A-Za-z0-9_.-]+/|/home/(?!runner/|oai/)"
        r"[A-Za-z0-9_.-]+/|C:\\Users\\[A-Za-z0-9_.-]+\\)"),
    "private LAN address": re.compile(
        r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"),
    "embedded FTP credentials": re.compile(
        r"ftps?://[^/\s:@]{2,}:[^/\s@]{3,}@"),
    "HTTP Authorization credential": re.compile(
        r"(?im)^\s*Authorization\s*:\s*(?:Bearer|Basic)\s+"
        r"[A-Za-z0-9+/=_\-.]{18,}\s*$"),
}
BINARY = {".ttf", ".woff", ".woff2", ".png", ".jpg", ".jpeg",
          ".ico", ".zip", ".elf", ".webp", ".db", ".sqlite"}
PRIVATE_NAMES = {".env", "id_rsa", "id_ed25519", "credentials.json",
                 "token.txt", "auth.json"}
PRIVATE_SUFFIXES = {".p12", ".pfx", ".pem", ".key", ".har", ".pcap"}

tracked = subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0")
findings = []
scanned = 0
for raw in tracked:
    if not raw:
        continue
    relative = Path(raw.decode("utf-8", errors="replace"))
    path = Path.cwd() / relative
    if relative.name.lower() in PRIVATE_NAMES or relative.suffix.lower() in PRIVATE_SUFFIXES:
        findings.append(f"{relative}: suspicious tracked file name")
    if path.is_symlink():
        findings.append(f"{relative}: tracked symbolic link requires review")
        continue
    if relative.suffix.lower() in BINARY:
        continue
    try:
        data = path.read_text(encoding="utf-8")
    except UnicodeError:
        continue
    except OSError:
        findings.append(f"{relative}: cannot read tracked file")
        continue
    scanned += 1
    for name, regex in PATTERNS.items():
        for match in regex.finditer(data):
            line = data.count("\n", 0, match.start()) + 1
            findings.append(f"{relative}:{line}: possible {name}")

if findings:
    print("\n".join(findings))
    raise SystemExit(1)
print(f"Privacy scan: {len(tracked)-1} tracked entries, {scanned} text files; "
      "no configured confidential patterns detected. "
      "Git history and embedded images are outside this scan.")
