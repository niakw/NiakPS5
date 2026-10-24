#!/usr/bin/env python3
"""Normalize source-attributed French game summaries for any PS4/PS5 ID.

Public sources are referenced, never scraped at runtime on the console.
Input supports ordinary UTF-8 TSV (and legacy literal \\t separators).
The output is an atomic, canonical, bounded offline index.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re

ID=re.compile(r"(?:CUSA|PPSA)[0-9]{5}\Z")
ALLOWED=("https://www.jeuxvideo.com/","https://www.playstation.com/fr-fr/")
MAX_SOURCE_SIZE=8*1024*1024
MAX_ENTRIES=12000
MAX_SUMMARY=600

def normalized_rows(data: str) -> list[tuple[str,str,str]]:
    result={}
    for line_no,line in enumerate(data.splitlines(),1):
        if not line.strip() or line.startswith("#"):
            continue
        if "\t" not in line and "\\t" in line:
            line=line.replace("\\t","\t")
        parts=line.split("\t")
        if len(parts)!=3:
            raise ValueError(f"line {line_no}: expected 3 TSV fields")
        title,url,summary=(part.strip() for part in parts)
        summary=" ".join(summary.split())
        if not ID.fullmatch(title):
            raise ValueError(f"line {line_no}: invalid PS4/PS5 title ID")
        if not url.startswith(ALLOWED) or any(x in url for x in ("\x00"," ","\t","#")):
            raise ValueError(f"line {line_no}: unapproved French source URL")
        if not summary or len(summary)>MAX_SUMMARY or any(ord(c)<32 for c in summary):
            raise ValueError(f"line {line_no}: invalid description")
        previous=result.get(title)
        if previous is not None and previous!=(url,summary):
            raise ValueError(f"line {line_no}: conflicting records for title ID")
        result[title]=(url,summary)
        if len(result)>MAX_ENTRIES:
            raise ValueError("too many sourced game descriptions")
    return [(title,*result[title]) for title in sorted(result)]

def generate(src: Path,destination: Path) -> int:
    if src.stat().st_size>MAX_SOURCE_SIZE:
        raise ValueError("French editorial index exceeds size limit")
    data=src.read_text(encoding="utf-8-sig")
    rows=normalized_rows(data)
    body="".join("\t".join(row)+"\n" for row in rows)
    destination.parent.mkdir(parents=True,exist_ok=True)
    temp=destination.with_name(destination.name+".tmp")
    temp.write_text(body,encoding="utf-8")
    temp.replace(destination)
    return len(rows)

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    print("Valid French sourced game descriptions:",generate(args.input,args.output))
if __name__=="__main__":
    main()
