#!/usr/bin/env python3
"""Purely synthetic installed-game fixture for host screenshot testing."""
from pathlib import Path
import sqlite3,struct,zlib,sys
root=Path(sys.argv[1]).resolve()
(root/"user"/"app").mkdir(parents=True,exist_ok=True)
(root/"user"/"appmeta").mkdir(parents=True,exist_ok=True)
def png(path,w,h,rgb):
    def ch(t,d):
        return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
    pixels=b"".join(b"\x00"+bytes(min(255,c+(y*26//h)+(x*32//w)) for x in range(w) for c in rgb) for y in range(h))
    path.write_bytes(b"\x89PNG\r\n\x1a\n"+ch(b"IHDR",struct.pack(">IIBBBBB",w,h,8,2,0,0,0))+ch(b"IDAT",zlib.compress(pixels,4))+ch(b"IEND",b""))
db=sqlite3.connect(root/"app.db")
db.execute("CREATE TABLE tbl_appbrowse(titleId TEXT,titleName TEXT)")
for tid,name,color in [
 ("PPSA12345","ASTRAL FRONTIER",(18,89,93)),
 ("PPSA23456","REQUIEM",(80,33,89)),
 ("PPSA34567","EXPEDITION",(35,65,112)),
 ("PPSA45678","DARK AGES",(105,42,35)),
 ("PPSA56789","WILDS",(49,90,67)),
 ("PPSA67890","NIGHTFALL",(78,54,102))
]:
 (root/"user"/"app"/tid).mkdir(exist_ok=True)
 meta=root/"user"/"appmeta"/tid
 meta.mkdir(exist_ok=True)
 png(meta/"icon0.png",180,200,color)
 png(meta/"pic1.png",640,400,color)
 db.execute("INSERT INTO tbl_appbrowse VALUES(?,?)",(tid,name))
db.commit();db.close()
print(root/"app.db")
