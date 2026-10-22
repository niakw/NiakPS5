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

    def test_invalid_elf_refuses_changes(self):
        f=FakeFTP()
        (self.root/"tools/niakps5.elf").write_bytes(b"Not an ELF")
        with self.assertRaises(ValueError):
            ftpmod.install(f,self.root,True)
        self.assertNotIn(ftpmod.AUTOLOAD,f.files)
if __name__=="__main__":
    unittest.main()
