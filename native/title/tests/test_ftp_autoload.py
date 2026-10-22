"""PS5 FTP autoload must be idempotent, reversible and preserve payload ordering."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"ftp_install.py"
spec=importlib.util.spec_from_file_location("niak_ftp_install",SCRIPT)
ftpmod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ftpmod)

class FakeFTP:
    def __init__(self,files=None):
        self.files=dict(files or {})
    def nlst(self,path):
        prefix=path.rstrip("/")+"/"
        return sorted({prefix+key[len(prefix):].split("/",1)[0]
                       for key in self.files if key.startswith(prefix)})
    def mkd(self,path):pass
    def storbinary(self,command,buf):
        assert command.startswith("STOR ")
        self.files[command[5:]]=buf.read()
    def retrbinary(self,command,callback):
        assert command.startswith("RETR ")
        path=command[5:]
        if path not in self.files:
            from ftplib import error_perm
            raise error_perm("550 not found")
        callback(self.files[path])
    def sendcmd(self,command):
        assert command.startswith("SITE CHMOD ")
        return "200 okay"

class AutoloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/"PPSA99386"
        (self.root/"sce_sys").mkdir(parents=True)
        (self.root/"sce_sys/param.json").write_bytes(b'{"titleId":"PPSA99386"}')
        (self.root/"eboot.bin").write_bytes(b"title binary")
        (self.root/"tools").mkdir()
        (self.root/"tools/niakps5.elf").write_bytes(b"\x7fELFps5 test")
    def tearDown(self):
        self.tmp.cleanup()
    def test_user_supplied_case_templates_are_private_and_checked(self):
        import struct
        import io
        from contextlib import redirect_stdout
        folder=self.root/"assets/niak-templates"
        folder.mkdir(parents=True)
        examples={"ps4-front":(949,136),"ps4-back":(647,362),
                  "ps4-spine":(72,800),"ps5-front":(1487,209),
                  "ps5-back":(1000,411),"ps5-spine":(85,1000)}
        for name,(width,height) in examples.items():
            # Enough PNG header bytes for the bounded transfer validator.
            (folder/(name+".png")).write_bytes(
                b"\x89PNG\r\n\x1a\n"+b"\x00"*8+
                struct.pack(">II",width,height)+b"\x00"*16)
        console=FakeFTP()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ftpmod.upload_case_templates(console,self.root),6)
        private="/data/homebrew/PPSA99386/assets/niak-templates/"
        self.assertEqual(sum(p.startswith(private) for p in console.files),6)
        self.assertNotIn(ftpmod.PAYLOAD,console.files)
        (folder/"ps5-spine.png").write_bytes(b"BAD")
        with self.assertRaises(ValueError):
            ftpmod.upload_case_templates(FakeFTP(),self.root)

    def test_no_autoload_does_not_touch_pldmgr(self):
        f=FakeFTP()
        ftpmod.install(f,self.root,False)
        self.assertIn("/data/homebrew/PPSA99386/eboot.bin",f.files)
        self.assertNotIn(ftpmod.AUTOLOAD,f.files)
        self.assertNotIn(ftpmod.PAYLOAD,f.files)
        self.assertNotIn("/data/niakps5-autostart.enabled",f.files)
    def test_order_backup_idempotence(self):
        initial=b"/data/pldmgr/payloads/kstuff/kstuff.elf\n!3000\n/data/pldmgr/payloads/shadow/shadow.elf\n"
        config=b"AUTOLOAD_ENABLED=0\nAUTOLOAD_DELAY=5\n"
        f=FakeFTP({ftpmod.AUTOLOAD:initial,ftpmod.CONFIG:config})
        ftpmod.install(f,self.root,True,True)
        final=f.files[ftpmod.AUTOLOAD].decode()
        self.assertTrue(final.startswith(initial.decode()))
        self.assertEqual(final.count(ftpmod.PAYLOAD),1)
        self.assertEqual(f.files[ftpmod.AUTOLOAD+".niakps5.bak"],initial)
        self.assertEqual(f.files[ftpmod.CONFIG+".niakps5.bak"],config)
        self.assertIn("AUTOLOAD_DELAY=5",f.files[ftpmod.CONFIG].decode())
        self.assertIn("AUTOLOAD_ENABLED=1",f.files[ftpmod.CONFIG].decode())
        self.assertIn("/data/niakps5-autostart.enabled",f.files)
        self.assertIn("/data/niakps5-return-after-game.enabled",f.files)
        ftpmod.install(f,self.root,True,False)
        self.assertEqual(f.files[ftpmod.AUTOLOAD].decode().count(ftpmod.PAYLOAD),1)

    def test_single_profile_avatar_is_locally_staged(self):
        user="0x12345678"
        source="/system_data/priv/cache/profile/"+user+"/avatar.png"
        sample=b"\x89PNG\r\n\x1a\n"+bytes(200)
        f=FakeFTP({source:sample})
        ftpmod.install(f,self.root,False)
        self.assertEqual(f.files["/data/homebrew/PPSA99386/assets/niak-profile.png"],sample)

    def test_multiple_profiles_are_not_guessed(self):
        root="/system_data/priv/cache/profile/"
        sample=b"\x89PNG\r\n\x1a\n"+bytes(200)
        f=FakeFTP({root+"0x11111111/avatar.png":sample,root+"0x22222222/avatar.png":sample})
        ftpmod.install(f,self.root,False)
        self.assertNotIn("/data/homebrew/PPSA99386/assets/niak-profile.png",f.files)
        ftpmod.install(f,self.root,False,avatar_user_id="0x22222222")
        self.assertEqual(f.files["/data/homebrew/PPSA99386/assets/niak-profile.png"],sample)

    def test_launchbox_installs_only_games_present_on_console(self):
        from unittest.mock import patch
        import io
        import urllib.request
        from pathlib import Path
        f=FakeFTP({"/user/app/PPSA34015/eboot.bin": b"x"})
        (self.root/"assets").mkdir()
        ids=("00000000-0000-0000-0000-000000000001.jpg",
             "00000000-0000-0000-0000-000000000002.jpg",
             "00000000-0000-0000-0000-000000000003.jpg")
        rows=("PPSA34015\\tRésumé réel\\tfr:"+ids[0]+
              "\\teu:"+ids[1]+"\\tfr:"+ids[2]+"\\t-\\t8\\n"+
              "PPSA01234\\tAbsent\\tfr:"+ids[0]+"\\t-\\t-\\t-\\t9\\n")
        (self.root/"assets/niak-launchbox-cases.tsv").write_text(rows.replace("\\t","\t").replace("\\n","\n"))
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,size):return b"JPEG fixture"
        with (patch.object(urllib.request,"urlopen",return_value=Response()),
              patch.object(ftpmod,"_decode_retail_image",return_value=b"compressed png")):
            count=ftpmod.fetch_retail_covers(f,self.root)
        self.assertEqual(count,3)
        self.assertIn("/data/homebrew/PPSA99386/assets/niak-cases/PPSA34015-spine.png",f.files)
        self.assertIn("/data/homebrew/PPSA99386/assets/niak-cases/PPSA34015-front.png",f.files)
        self.assertIn("/data/homebrew/PPSA99386/assets/niak-cases/PPSA34015-back.png",f.files)
        self.assertNotIn("/data/homebrew/PPSA99386/assets/niak-cases/PPSA01234-front.png",f.files)

    def test_refresh_art_is_isolated_from_payload_manager(self):
        # --refresh-art delegates only to the two read-only discovery /
        # private artwork staging helpers, not the app/Payload Manager installer.
        source=SCRIPT.read_text()
        self.assertIn('if args.refresh_art:',source)
        self.assertIn('action="store_true", default=True',source)
        self.assertIn("--no-autoload",source)
        self.assertIn("niakps5.elf",(SCRIPT.parent/"AUTOSTART.md").read_text())
        self.assertIn('fetch_retail_covers(ftp, directory, args.art_limit, force=args.force_art)',source)
        self.assertIn("--force-art",source)
        self.assertIn('indexed_matches',source)

    def test_category_from_verified_ps5_param(self):
        import json
        game="/data/homebrew/PPSA11111/sce_sys/param.json"
        app="/data/homebrew/PPSA22222/sce_sys/param.json"
        media="/user/app/NPXS50001/sce_sys/param.json"
        system="/system_ex/app/NPXS50002/sce_sys/param.json"
        f=FakeFTP({
            game:json.dumps({"titleName":"Test Game",
                             "applicationCategoryType":0}).encode(),
            app:json.dumps({"titleName":"Test App",
                            "applicationCategoryType":65536}).encode(),
            media:json.dumps({"titleName":"Test Streaming",
                              "applicationCategoryType":65792}).encode(),
            system:json.dumps({"titleName":"Built-in System Service",
                               "applicationCategoryType":0}).encode()
        })
        count=ftpmod.upload_local_homebrew_names(f)
        self.assertEqual(count,3)
        overlay=f.files["/data/homebrew/PPSA99386/assets/niak-local-titles.tsv"].decode()
        self.assertIn("PPSA11111\tTest Game\tJeu\t",overlay)
        self.assertIn("PPSA22222\tTest App\tApplication\t",overlay)
        self.assertIn("NPXS50001\tTest Streaming\tApplication\t",overlay)
        self.assertNotIn("NPXS50002",overlay)

    def test_read_only_status_never_changes_console(self):
        from contextlib import redirect_stdout
        from io import StringIO
        app="/data/homebrew/PPSA99386"
        log=b"NiakPS5 optional autostart start rc=0x00000000\n"
        log+=b"sceSystemServiceLaunchApp rc=0x00000000\n"
        original={app+"/eboot.bin":b"native",
                  "/data/niakps5-autostart.log":log,
                  ftpmod.AUTOLOAD:(ftpmod.PAYLOAD+"\n").encode(),
                  ftpmod.CONFIG:b"AUTOLOAD_ENABLED=1\n"}
        f=FakeFTP(original)
        out=StringIO()
        with redirect_stdout(out):
            ftpmod.diagnose(f)
        self.assertEqual(f.files,original)
        self.assertIn("succès HISTORIQUE",out.getvalue())
        self.assertIn("PLDmgr AUTOLOAD_ENABLED : True",out.getvalue())
        self.assertIn("installed_binary_matches",SCRIPT.read_text())

    def test_art_cache_handles_absolute_and_basename_ftp_listings(self):
        from unittest.mock import patch
        import urllib.request
        for mode in ("absolute","basename","relative"):
            with self.subTest(mode=mode):
                ident="PPSA34015"
                stored=f"/data/homebrew/{ftpmod.TITLE}/assets/niak-cases/{ident}-front.png"
                ftp=FakeFTP({stored:b"cached",
                             f"/user/app/{ident}/eboot.bin":b"game"})
                (self.root/"assets").mkdir(exist_ok=True)
                (self.root/"assets/niak-launchbox-cases.tsv").write_text(
                    ident+"\\t-\\tfr:00000000-0000-0000-0000-000000000001.jpg"
                    +"\\t-\\t-\\t-\\t4\\n")
                original=ftp.nlst
                def alternate_listing(path):
                    returned=original(path)
                    if path.endswith("/niak-cases"):
                        if mode=="basename":
                            return [entry.rsplit("/",1)[-1] for entry in returned]
                        if mode=="relative":
                            return ["niak-cases/"+entry.rsplit("/",1)[-1]
                                    for entry in returned]
                    return returned
                with (patch.object(ftp,"nlst",side_effect=alternate_listing),
                      patch.object(urllib.request,"urlopen") as net):
                    self.assertEqual(ftpmod.fetch_retail_covers(ftp,self.root),0)
                    net.assert_not_called()
                self.assertEqual(ftp.files[stored],b"cached")

    def test_art_cache_does_not_refetch_installed_front(self):
        from unittest.mock import patch
        import urllib.request
        id="PPSA34015"
        existing=f"/data/homebrew/{ftpmod.TITLE}/assets/niak-cases/{id}-front.png"
        f=FakeFTP({f"/user/app/{id}/eboot.bin":b"game",existing:b"image"})
        (self.root/"assets").mkdir(exist_ok=True)
        (self.root/"assets/niak-launchbox-cases.tsv").write_text(
            id+"\t-\tfr:00000000-0000-0000-0000-000000000001.jpg\t-\t-\t-\t4\n")
        with patch.object(urllib.request,"urlopen") as open_url:
            result=ftpmod.fetch_retail_covers(f,self.root)
        self.assertEqual(result,0)
        open_url.assert_not_called()
        self.assertEqual(f.files[existing],b"image")
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,length): return b"placeholder-image"
        with (patch.object(urllib.request,"urlopen",return_value=Response()),
              patch.object(ftpmod,"_decode_retail_image",return_value=b"repaired-png")):
            refreshed=ftpmod.fetch_retail_covers(f,self.root,force=True)
        self.assertEqual(refreshed,1)
        self.assertEqual(f.files[existing],b"repaired-png")

    def test_invalid_elf_refuses_changes(self):
        f=FakeFTP()
        (self.root/"tools/niakps5.elf").write_bytes(b"Not an ELF")
        with self.assertRaises(ValueError):
            ftpmod.install(f,self.root,True)
        self.assertNotIn(ftpmod.AUTOLOAD,f.files)
if __name__=="__main__":
    unittest.main()
