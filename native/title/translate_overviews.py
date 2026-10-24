#!/usr/bin/env python3
"""Translate ONLY public LaunchBox game overviews, via the owner's DeepL API key.

No title IDs, console names, usernames or personal metadata are sent to DeepL.
This is an explicit, opt-in FTP enrichment; the key stays in the Mac's env.
"""
import hashlib
import json
import os
import re
import urllib.request

VALID_ID=re.compile(r"^(?:PPSA|CUSA)[0-9]{5}$")
def safe_overview(text):
    return " ".join(str(text).replace("\t"," ").replace("\r"," ").replace("\n"," ").split())[:900]

def eligible_rows(index,installed):
    result={}
    for line in index.decode("utf8","replace").splitlines():
        row=line.split("\t",2)
        if len(row)<3:continue
        ident,overview=row[:2]
        if ident in installed and VALID_ID.fullmatch(ident):
            overview=safe_overview(overview)
            if overview and overview!="-":result[ident]=overview
    return result

def translation_file(index,installed,key=None,fetch=None):
    """Return a UTF-8 TSV or None. Fail closed without valid API credentials."""
    key=key if key is not None else os.environ.get("NIAK_DEEPL_API_KEY","")
    if not key or not key.strip():return None
    rows=eligible_rows(index,installed)
    if not rows:return None
    endpoint=("https://api-free.deepl.com" if key.endswith(":fx")
              else "https://api.deepl.com")+"/v2/translate"
    call=fetch or urllib.request.urlopen
    result={}
    # DeepL supports <=50 separate texts per request, 128 KiB total.
    entries=sorted(rows.items())
    for offset in range(0,len(entries),25):
        part=entries[offset:offset+25]
        data=json.dumps({"text":[text for _,text in part],
                         "target_lang":"FR","preserve_formatting":True},
                        ensure_ascii=False).encode("utf8")
        req=urllib.request.Request(endpoint,data=data,method="POST",headers={
            "Authorization":"DeepL-Auth-Key "+key,
            "Content-Type":"application/json",
            "User-Agent":"NiakPS5-private-translation/1.0"})
        try:
            with call(req,timeout=25) as response:
                payload=response.read(64*1024+1)
            if len(payload)>64*1024:break
            translations=json.loads(payload).get("translations",[])
            if len(translations)!=len(part):break
            for (ident,source),item in zip(part,translations):
                if not isinstance(item,dict):continue
                fr=safe_overview(item.get("text",""))
                if not fr:continue
                digest=hashlib.sha256(source.encode("utf8")).hexdigest()
                result[ident]=(digest,fr)
        except (OSError,ValueError,KeyError,TypeError):
            break  # No retries that could bill twice.
    if not result:return None
    return "".join(f"{ident}\t{digest}\t{fr}\n"
                   for ident,(digest,fr) in sorted(result.items())).encode("utf8")
