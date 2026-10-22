import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("niak_cover_sources",ROOT/"cover_sources.py")
provider=importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)
spec2=importlib.util.spec_from_file_location("niak_ftp_for_providers",ROOT/"ftp_install.py")
ftp=importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(ftp)


class FakeFTP:
    def __init__(self,files=None):self.files=dict(files or {})
    def nlst(self,path):
        prefix=path.rstrip("/")+"/"
        return sorted({prefix+k[len(prefix):].split("/",1)[0]
                       for k in self.files if k.startswith(prefix)})
    def mkd(self,path):return None
    def sendcmd(self,command):return "200 OK"
    def storbinary(self,command,source):self.files[command[5:]]=source.read()
    def retrbinary(self,command,callback):
        path=command[5:]
        if path not in self.files:
            from ftplib import error_perm
            raise error_perm("550 not found")
        callback(self.files[path])


TGDB_URL="https://cdn.thegamesdb.net/images/original/"
def tgdb_response(second=False,wrong_platform=False):
    game={"id":421,"game_title":"Anno 1800 Console Edition",
          "platform":2 if wrong_platform else 1}
    matches=[game]
    if second:matches.append({"id":422,"game_title":game["game_title"],"platform":1})
    return {
        "data":{"games":matches},
        "include":{
            "platform":{"data":{"1":{"name":"Sony PlayStation 5"},
                                "2":{"name":"Sony PlayStation 4"}}},
            "boxart":{"data":{"421":[
                {"side":"front","filename":"boxart/front/421-1.jpg"},
                {"side":"back","filename":"boxart/back/421-1.jpg"}],
                "422":[{"side":"front","filename":"boxart/front/422-1.jpg"}]}}
        }
    }


class SourceTests(unittest.TestCase):
    def test_platform_title_and_edition_are_required(self):
        with patch.object(provider,"get_json",return_value=tgdb_response()):
            result=provider.tgdb_cover_urls("Anno 1800 Console Edition","ps5","test-key")
        self.assertEqual(result,{"front":TGDB_URL+"boxart/front/421-1.jpg",
                                 "back":TGDB_URL+"boxart/back/421-1.jpg"})
        with patch.object(provider,"get_json",return_value=tgdb_response(wrong_platform=True)):
            self.assertEqual(provider.tgdb_cover_urls("Anno 1800 Console Edition","ps5","test-key"),{})
        with patch.object(provider,"get_json",return_value=tgdb_response(second=True)):
            self.assertEqual(provider.tgdb_cover_urls("Anno 1800 Console Edition","ps5","test-key"),{})
        self.assertEqual(provider.name_variants("EA SPORTS FC 27"),("ea sports fc 27",))
        self.assertEqual(provider.name_variants("Elden Ring Ultimate Edition"),
                         ("elden ring ultimate edition",))

    def test_image_host_and_side_are_restricted(self):
        self.assertFalse(provider.trusted_image_url("http://cdn.thegamesdb.net/img.png"))
        self.assertFalse(provider.trusted_image_url("https://cdn.thegamesdb.net.evil.org/img.png"))
        self.assertFalse(provider.trusted_image_url("https://evil.org/x.jpg"))
        with patch.object(provider,"get_json",return_value={
            **tgdb_response(),
            "include":{
                **tgdb_response()["include"],
                "boxart":{"data":{"421":[
                    {"side":"front","filename":"../admin.png"},
                    {"side":"back","filename":"boxart/front/wrong.jpg"},
                    {"side":"front","filename":"boxart/front/421.png"}]}}
            }
        }):
            self.assertEqual(provider.tgdb_cover_urls("Anno 1800 Console Edition","ps5","key"),
                             {"front":TGDB_URL+"boxart/front/421.png"})

    def test_steamgriddb_is_front_only_and_unique_title(self):
        def fake(url,headers=None):
            if "/search/" in url:return {"data":[{"id":123,"name":"EA SPORTS FC 27","types":["game"]}]}
            return {"data":[
                {"url":"https://evil.test/p.jpg","score":999},
                {"url":"https://cdn2.steamgriddb.com/grid/a.png","score":8}]}
        with patch.object(provider,"get_json",side_effect=fake):
            self.assertEqual(
                provider.steamgriddb_portrait_url("EA SPORTS FC 27","private"),
                {"front":"https://cdn2.steamgriddb.com/grid/a.png"})
        with patch.object(provider,"get_json",return_value={"data":[
            {"id":123,"name":"EA SPORTS FC 27","types":["game"]},
            {"id":124,"name":"EA SPORTS FC 27","types":["game"]}]}):
            self.assertEqual(provider.steamgriddb_portrait_url("EA SPORTS FC 27","private"),{})

    def test_ftp_fallback_downloads_only_missing_sides(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/ftp.TITLE
            (folder/"assets").mkdir(parents=True)
            (folder/"assets/niak-ps-titles.tsv").write_text(
                "PPSA04716\tAnno 1800 Console Edition\t\t\t\n",encoding="utf8")
            fake=FakeFTP({"/user/app/PPSA04716/eboot.bin":b"game"})
            class Response:
                def __init__(self,url,body):self.url,self.body=url,body
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def geturl(self):return self.url
                def read(self,n):return self.body
            def query(request,timeout=12):
                url=request.full_url
                if url.startswith("https://api.thegamesdb.net"):
                    return Response(url,json.dumps(tgdb_response()).encode())
                if url.startswith(TGDB_URL):
                    return Response(url,b"fake JPG")
                raise AssertionError("Unexpected URL: "+url.split("?")[0])
            with (patch.dict(os.environ,{"NIAK_THEGAMESDB_KEY":"secret-test",
                                        "NIAK_STEAMGRIDDB_KEY":"configured-too"}),
                  patch("urllib.request.urlopen",side_effect=query),
                  patch.object(ftp,"_decode_retail_image",return_value=b"valid fixture")):
                count=ftp.fetch_alternative_covers(fake,folder)
            self.assertEqual(count,2)
            base=f"/data/homebrew/{ftp.TITLE}/assets/niak-cases/PPSA04716-"
            self.assertEqual(fake.files[base+"front.png"],b"valid fixture")
            self.assertEqual(fake.files[base+"back.png"],b"valid fixture")
            self.assertNotIn(base+"spine.png",fake.files)

    def test_no_keys_does_not_call_network_or_touch_console(self):
        fake=FakeFTP()
        with tempfile.TemporaryDirectory() as tmp:
            with (patch.dict(os.environ,{"NIAK_THEGAMESDB_KEY":"",
                                        "NIAK_STEAMGRIDDB_KEY":""}),
                  patch("urllib.request.urlopen") as network):
                self.assertEqual(ftp.fetch_alternative_covers(fake,Path(tmp)),0)
                network.assert_not_called()
        self.assertEqual(fake.files,{})


if __name__=="__main__":
    unittest.main()
