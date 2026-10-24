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
    def delete(self,path):
        from ftplib import error_perm
        if path not in self.files:
            raise error_perm("550 not found")
        del self.files[path]
        return "250 removed"

class AutoloadTests(unittest.TestCase):
    def test_private_launchbox_index_uses_actual_installed_name(self):
        from zipfile import ZipFile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            tools=root/"tools"
            tools.mkdir()
            (tools/"launchbox_index.py").write_text(
                (SCRIPT.parent/"launchbox_index.py").read_text())
            archive=root/"Metadata.zip"
            xml=b"""<LaunchBox>
             <Game><DatabaseID>427261</DatabaseID>
               <Platform>Sony Playstation 5</Platform>
               <Name>A Plague Tale: Innocence</Name>
               <Notes>True game synopsis.</Notes></Game>
             <GameImage><DatabaseID>427261</DatabaseID>
               <Type>Box - Front</Type>
               <FileName>00000000-0000-0000-0000-000000427261.png</FileName>
             </GameImage></LaunchBox>"""
            with ZipFile(archive,"w") as z:z.writestr("Metadata.xml",xml)
            f=FakeFTP({f"/data/homebrew/{ftpmod.TITLE}/assets/niak-local-titles.tsv":
                b"PPSA02387\tA Plague Tale: Innocence\tJeu\t\t\n",
                "/user/app/PPSA02387/sce_sys/param.json":b'{"titleId":"PPSA02387"}'})
            with patch.object(ftpmod,"__file__",str(tools/"ftp_install.py")):
                self.assertTrue(ftpmod.rebuild_installed_launchbox_index(
                    f,root,archive=archive))
            result=f.files[ftpmod.LAUNCHBOX_PRIVATE_INDEX]
            self.assertIn(b"True game synopsis",result)
            self.assertIn(b"PPSA02387",result)


    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/"PPSA99386"
        (self.root/"sce_sys").mkdir(parents=True)
        (self.root/"sce_sys/param.json").write_bytes(b'{"titleId":"PPSA99386"}')
        (self.root/"eboot.bin").write_bytes(b"title binary")
        (self.root/"sce_module").mkdir()
        (self.root/"sce_module/libc.prx").write_bytes(b"native runtime")
        (self.root/"tools/niakps5").mkdir(parents=True)
        payload=b"\x7fELFps5 test"
        (self.root/"tools/niakps5/niakps5.elf").write_bytes(payload)
        import hashlib
        import json
        (self.root/"tools/niakps5/niakps5.elf.json").write_text(
            json.dumps({"name":"NiakPS5","filename":"niakps5.elf",
                        "checksum":hashlib.sha256(payload).hexdigest()}))
    def tearDown(self):
        self.tmp.cleanup()
    def test_private_zip_templates_install_without_autoload_rewrite(self):
        import struct
        from zipfile import ZipFile
        from unittest.mock import patch
        overlay=Path(self.tmp.name)/"owner-templates.zip"
        sizes={"ps4-front.png":(949,136),"ps4-back.png":(647,362),
               "ps4-spine.png":(72,800),"ps5-front.png":(1487,209),
               "ps5-back.png":(1000,411),"ps5-spine.png":(85,1000)}
        with ZipFile(overlay,"w") as archive:
            archive.writestr("HOW_TO_INSTALL.txt","Private assets")
            for name,(w,h) in sizes.items():
                header=b"\x89PNG\r\n\x1a\n"+b"\0"*8+struct.pack(">II",w,h)+b"\0"*14
                archive.writestr("PPSA99386/assets/niak-templates/"+name,header)
        imgs=ftpmod.load_private_template_zip(overlay)
        self.assertEqual(set(imgs),set(sizes))
        original=b"ftpsrv.elf\nniakps5.elf\n"
        f=FakeFTP({ftpmod.AUTOLOAD:original})
        with patch.object(ftpmod,"fetch_retail_covers",return_value=0), \
             patch.object(ftpmod,"fetch_alternative_covers",return_value=0):
            ftpmod.install(f,self.root,False,preserve_autoload=True,
                           case_templates=overlay)
        self.assertEqual(f.files[ftpmod.AUTOLOAD],original)
        for name in sizes:
            remote=f"/data/homebrew/PPSA99386/assets/niak-templates/{name}"
            self.assertEqual(f.files[remote],imgs[name])
        with ZipFile(overlay,"a") as archive:
            archive.writestr("PPSA99386/../../untrusted.png",b"bad")
        with self.assertRaises(ValueError):
            ftpmod.load_private_template_zip(overlay)

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


    def test_installed_publisher_artwork_is_staged_privately_once(self):
        import io
        import struct
        import zlib
        from contextlib import redirect_stdout
        def png(w,h):
            def chunk(tag,data):
                return (struct.pack(">I",len(data))+tag+data+
                        struct.pack(">I",zlib.crc32(tag+data)&0xffffffff))
            pixels=b"".join(b"\0"+b"\x18\x28\x38\xff"*w for _ in range(h))
            return (b"\x89PNG\r\n\x1a\n"+
                    chunk(b"IHDR",struct.pack(">IIBBBBB",w,h,8,6,0,0,0))+
                    chunk(b"IDAT",zlib.compress(pixels))+
                    chunk(b"IEND",b""))
        title="PPSA01234"
        root=f"/user/app/{title}/sce_sys"
        console=FakeFTP({root+"/icon0.png":png(512,512),
                         root+"/pic1.png":png(640,360),
                         "/user/av_contents/photo/private.png":png(512,512)})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ftpmod.stage_installed_artwork(console,2),2)
            self.assertEqual(ftpmod.stage_installed_artwork(console,2),0)
        cached="/data/homebrew/PPSA99386/assets/niak-installed/"
        self.assertEqual(len([p for p in console.files if p.startswith(cached)]),2)
        self.assertTrue(console.files[cached+title+"-icon.png"].startswith(b"\x89PNG"))
        self.assertTrue(console.files[cached+title+"-scene.png"].startswith(b"\x89PNG"))
        native=(SCRIPT.parent/"game_icons.cpp").read_text()
        self.assertIn('"/app0/assets/niak-installed/%s-icon.png"',native)
        self.assertIn('"/app0/assets/niak-installed/%s-scene.png"',native)


    def test_only_verified_npxs_media_is_staged(self):
        import io
        from contextlib import redirect_stdout
        good="NPXS12345"
        bad="NPXS99999"
        # The cache discovery itself must be restricted to verified media
        # metadata, not just any directory matching an NPXS identifier.
        overlay=f"/data/homebrew/PPSA99386/assets/niak-local-titles.tsv"
        ftp=FakeFTP({overlay:(good+"\tLecteur vidéo\tApplication\t\t\n"+
                              bad+"\tService système\tAutre\t\t\n").encode()})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ftpmod._verified_media_ids(ftp),[good])
        src=(SCRIPT.parent/"game_icons.cpp").read_text()
        self.assertIn('std::strncmp(id,"NPXS",4)==0',src)
        self.assertIn('if(!niak_valid_title_id(id) && !media)return 0;',src)

    def test_installed_artwork_rejects_malformed_and_oversized_png(self):
        self.assertIsNone(ftpmod._prepare_installed_png(b"NOTPNG",False))
        header=(b"\x89PNG\r\n\x1a\n"+b"\x00"*8+
                (9000).to_bytes(4,"big")+(9000).to_bytes(4,"big")+b"\x00"*16)
        self.assertIsNone(ftpmod._prepare_installed_png(header,False))
        self.assertIsNone(ftpmod._prepare_installed_png(b"x"*(5*1024*1024+1),False))


    def test_diagnose_normalizes_basename_only_ftp_listings(self):
        from contextlib import redirect_stdout
        from io import StringIO
        class Basenames(FakeFTP):
            def nlst(self,path):
                return [value.rsplit("/",1)[-1] for value in super().nlst(path)]
        base="/data/homebrew/PPSA99386"
        files={base+"/eboot.bin":b"native",
               base+"/assets/niak-launchbox-cases.tsv":b"# index",
               base+"/assets/niak-local-titles.tsv":b"# local",
               base+"/assets/niak-profile.png":b"private avatar",
               ftpmod.PAYLOAD:b"payload",
               "/data/niakps5-autostart.enabled":b""}
        stream=StringIO()
        with redirect_stdout(stream):
            ftpmod.diagnose(Basenames(files))
        report=stream.getvalue()
        self.assertIn("Titre eboot.bin : True",report)
        self.assertIn("Index LaunchBox : True",report)
        self.assertIn("Métadonnées locales : True",report)
        self.assertIn("Avatar copié : True",report)
        self.assertIn("Payload ELF : True",report)
        self.assertIn("Marqueur activation : True",report)

    def test_empty_catalog_scan_clears_stale_private_overlay(self):
        path=f"/data/homebrew/{ftpmod.TITLE}/assets/niak-local-titles.tsv"
        old=b"NPXS12345\\tAncien media\\tApplication\\t\\t\\n"
        ftp=FakeFTP({path:old})
        count=ftpmod.upload_local_homebrew_names(ftp)
        self.assertEqual(count,0)
        self.assertEqual(ftp.files[path],b"")
        self.assertEqual(ftpmod._verified_media_ids(ftp),[])

    def test_denied_ftp_roots_preserve_last_verified_title_overlay(self):
        from ftplib import error_perm
        class InaccessibleTitles(FakeFTP):
            def nlst(self,path):
                if path in ("/data/homebrew","/user/app","/system_ex/app",
                            "/mnt/ext0/user/app","/mnt/ext1/user/app"):
                    raise error_perm("550 Permission denied")
                return super().nlst(path)
        private=f"/data/homebrew/{ftpmod.TITLE}/assets/niak-local-titles.tsv"
        old=b"PPSA00001\\tJeu deja connu\\tJeu\\t\\t\\n"
        console=InaccessibleTitles({private:old})
        self.assertEqual(ftpmod.upload_local_homebrew_names(console),0)
        self.assertEqual(console.files[private],old)

    def test_installed_metadata_rejects_inconsistent_title_identity(self):
        # The folder and an explicit titleId must represent the same title;
        # otherwise stale/copied param.json can mislabel a title in the UI.
        root="/user/app/PPSA12345/sce_sys/param.json"
        path=f"/data/homebrew/{ftpmod.TITLE}/assets/niak-local-titles.tsv"
        ftp=FakeFTP({root:b'{"titleId":"PPSA99999","titleName":"Wrong Game","applicationCategoryType":0}'})
        self.assertEqual(ftpmod.upload_local_homebrew_names(ftp),0)
        self.assertEqual(ftp.files[path],b"")

    def test_malformed_installed_metadata_cannot_abort_all_title_discovery(self):
        import json
        base="/user/app"
        valid="PPSA12345"
        malformed={
            "PPSA23456":{"titleId":"PPSA23456","titleName":"List params",
                         "localizedParameters":["not","an","object"],
                         "applicationCategoryType":0},
            "PPSA34567":{"titleId":{"spoofed":True},"titleName":"Wrong identity",
                         "applicationCategoryType":0},
            "PPSA45678":{"titleId":"PPSA45678",
                         "localizedParameters":True,
                         "applicationCategoryType":0},
        }
        files={f"{base}/{valid}/sce_sys/param.json":
               json.dumps({"titleId":valid,"titleName":"Jeu valide",
                           "applicationCategoryType":0}).encode()}
        for ident,meta in malformed.items():
            files[f"{base}/{ident}/sce_sys/param.json"]=json.dumps(meta).encode()
        ftp=FakeFTP(files)
        self.assertEqual(ftpmod.upload_local_homebrew_names(ftp),2)
        overlay=ftp.files[f"/data/homebrew/{ftpmod.TITLE}/assets/niak-local-titles.tsv"].decode()
        self.assertIn("PPSA12345\tJeu valide\tJeu",overlay)
        self.assertIn("PPSA23456\tList params\tJeu",overlay)
        self.assertNotIn("PPSA34567",overlay)

    def test_no_autoload_does_not_touch_pldmgr(self):
        f=FakeFTP()
        ftpmod.install(f,self.root,False)
        self.assertIn("/data/homebrew/PPSA99386/eboot.bin",f.files)
        self.assertNotIn(ftpmod.AUTOLOAD,f.files)
        self.assertNotIn(ftpmod.PAYLOAD,f.files)
        self.assertNotIn("/data/homebrew/PPSA99386/tools/niakps5/niakps5.elf",f.files)
        self.assertNotIn("/data/homebrew/PPSA99386/tools/niakps5/niakps5.elf.json",f.files)
        self.assertNotIn("/data/niakps5-autostart.enabled",f.files)
    def test_preserve_autoload_updates_payload_without_rewriting_configuration(self):
        class TrackingFTP(FakeFTP):
            def __init__(self,files):
                super().__init__(files)
                self.writes=[]
            def storbinary(self,command,buf):
                self.writes.append(command[5:])
                return super().storbinary(command,buf)
        autoload=b"ftpsrv.elf\nniakps5.elf\n"
        settings=b"AUTOLOAD_DELAY=10\nAUTOLOAD_ENABLED=1\n"
        f=TrackingFTP({ftpmod.AUTOLOAD:autoload,ftpmod.CONFIG:settings,
                       ftpmod.PAYLOAD:b"stale-payload"})
        ftpmod.install(f,self.root,False,preserve_autoload=True)
        self.assertEqual(f.files[ftpmod.PAYLOAD],
                         (self.root/"tools/niakps5/niakps5.elf").read_bytes())
        self.assertIn(ftpmod.PAYLOAD_META,f.writes)
        self.assertIn("/data/homebrew/PPSA99386/eboot.bin",f.writes)
        bundled="/data/homebrew/PPSA99386/tools/niakps5/niakps5.elf"
        self.assertEqual(f.files[bundled],
                         (self.root/"tools/niakps5/niakps5.elf").read_bytes())
        self.assertIn(bundled+".json",f.files)
        self.assertNotIn("/data/homebrew/PPSA99386/tools/ftp_install.py",f.files)
        for protected in (ftpmod.AUTOLOAD,ftpmod.CONFIG,
                          "/data/niakps5-autostart.enabled"):
            self.assertNotIn(protected,f.writes)
        self.assertEqual(f.files[ftpmod.AUTOLOAD],autoload)
        self.assertEqual(f.files[ftpmod.CONFIG],settings)

    def test_reinstall_preserves_existing_autoload_bytes_and_order(self):
        class TrackingFTP(FakeFTP):
            def __init__(self,files):
                super().__init__(files)
                self.writes=[]
            def storbinary(self,command,buf):
                self.writes.append(command[5:])
                return super().storbinary(command,buf)
        autoload=b"niakps5.elf\nother.elf\n"
        settings=b"AUTOLOAD_ENABLED=1\nAUTOLOAD_DELAY=7\n"
        f=TrackingFTP({ftpmod.AUTOLOAD:autoload,ftpmod.CONFIG:settings})
        ftpmod.install(f,self.root,True)
        self.assertEqual(f.files[ftpmod.AUTOLOAD],autoload)
        self.assertEqual(f.files[ftpmod.CONFIG],settings)
        self.assertNotIn(ftpmod.AUTOLOAD,f.writes)
        self.assertNotIn(ftpmod.CONFIG,f.writes)
        self.assertIn(ftpmod.PAYLOAD,f.writes)

    def test_order_backup_idempotence(self):
        initial=(b"nanoDNS_0.4.elf\nkstuff-lite_v1.11.elf\n"
                 b"ShadowMountPlus_1.7beta7.elf\nftpsrv_v0.21.1.elf\n"
                 b"BFpilot_v0.4.4.elf\n")
        config=b"AUTOLOAD_ENABLED=0\nAUTOLOAD_DELAY=5\n"
        f=FakeFTP({ftpmod.AUTOLOAD:initial,ftpmod.CONFIG:config})
        ftpmod.install(f,self.root,True,True)
        final=f.files[ftpmod.AUTOLOAD].decode()
        self.assertTrue(final.startswith(initial.decode()))
        self.assertTrue(final.endswith("BFpilot_v0.4.4.elf\nniakps5.elf\n"))
        self.assertEqual(final.count(ftpmod.AUTOLOAD_NAME),1)
        self.assertNotIn("!2000",final)
        self.assertIn(ftpmod.PAYLOAD_META,f.files)
        import hashlib
        import json
        sidecar=json.loads(f.files[ftpmod.PAYLOAD_META])
        self.assertEqual(sidecar["filename"],"niakps5.elf")
        self.assertEqual(sidecar["checksum"],hashlib.sha256(
            f.files[ftpmod.PAYLOAD]).hexdigest())
        self.assertEqual(f.files[ftpmod.AUTOLOAD+".niakps5.bak"],initial)
        self.assertEqual(f.files[ftpmod.CONFIG+".niakps5.bak"],config)
        self.assertIn("AUTOLOAD_DELAY=5",f.files[ftpmod.CONFIG].decode())
        self.assertIn("AUTOLOAD_ENABLED=1",f.files[ftpmod.CONFIG].decode())
        self.assertIn("/data/niakps5-autostart.enabled",f.files)
        self.assertIn("/data/niakps5-return-after-game.enabled",f.files)
        ftpmod.install(f,self.root,True,False)
        self.assertNotIn("/data/niakps5-return-after-game.enabled",f.files)
        self.assertIn("/data/niakps5-autostart.enabled",f.files)
        self.assertEqual(f.files[ftpmod.AUTOLOAD].decode().count(ftpmod.AUTOLOAD_NAME),1)
        # A repeat install must never replace the original pre-Niak backups.
        self.assertEqual(f.files[ftpmod.AUTOLOAD+".niakps5.bak"],initial)
        self.assertEqual(f.files[ftpmod.CONFIG+".niakps5.bak"],config)


    def test_invalid_pldmgr_config_never_partially_enables_autoload(self):
        existing=b"/data/pldmgr/payloads/shadow/shadow.elf\n"
        f=FakeFTP({ftpmod.AUTOLOAD:existing,
                   ftpmod.CONFIG:b"AUTOLOAD_ENABLED=0\0CORRUPT"})
        with self.assertRaises(ValueError):
            ftpmod.install(f,self.root,True)
        self.assertEqual(f.files[ftpmod.AUTOLOAD],existing)
        self.assertNotIn(ftpmod.PAYLOAD,f.files)
        self.assertNotIn(ftpmod.AUTOLOAD+".niakps5.bak",f.files)
        self.assertNotIn("/data/niakps5-autostart.enabled",f.files)

    def test_disabled_return_flag_remains_disabled_on_reinstall(self):
        f=FakeFTP()
        ftpmod.install(f,self.root,True,False)
        self.assertNotIn("/data/niakps5-return-after-game.enabled",f.files)
        ftpmod.install(f,self.root,True,True)
        self.assertIn("/data/niakps5-return-after-game.enabled",f.files)
        ftpmod.install(f,self.root,True,False)
        self.assertNotIn("/data/niakps5-return-after-game.enabled",f.files)

    def test_failed_return_flag_removal_cannot_silently_claim_opt_out(self):
        from ftplib import error_perm
        marker="/data/niakps5-return-after-game.enabled"
        class UndeletableFTP(FakeFTP):
            def delete(self,path):
                raise error_perm("550 permission denied")
        f=UndeletableFTP({marker:b""})
        with self.assertRaises(error_perm):
            ftpmod.install(f,self.root,True,False)
        self.assertIn(marker,f.files)
        self.assertNotIn(ftpmod.PAYLOAD,f.files)
        self.assertNotIn(ftpmod.AUTOLOAD,f.files)
        self.assertNotIn("/data/niakps5-autostart.enabled",f.files)

    def test_autoload_backup_is_never_replaced_if_it_preexists(self):
        initial=b"/data/pldmgr/payloads/shadow/shadow.elf\n"
        first_backup=b"ORIGINAL BEFORE NIAKPS5\n"
        first_config=b"AUTOLOAD_ENABLED=0\nAUTOLOAD_DELAY=3\n"
        current_config=b"AUTOLOAD_ENABLED=1\nAUTOLOAD_DELAY=5\n"
        f=FakeFTP({ftpmod.AUTOLOAD:initial,
                   ftpmod.CONFIG:current_config,
                   ftpmod.AUTOLOAD+".niakps5.bak":first_backup,
                   ftpmod.CONFIG+".niakps5.bak":first_config})
        ftpmod.install(f,self.root,True)
        self.assertEqual(f.files[ftpmod.AUTOLOAD+".niakps5.bak"],first_backup)
        self.assertEqual(f.files[ftpmod.CONFIG+".niakps5.bak"],first_config)

    def test_single_profile_avatar_is_locally_staged(self):
        user="0x12345678"
        source="/system_data/priv/cache/profile/"+user+"/avatar.png"
        sample=b"\x89PNG\r\n\x1a\n"+bytes(200)
        f=FakeFTP({source:sample})
        ftpmod.install(f,self.root,False)
        self.assertEqual(f.files["/data/homebrew/PPSA99386/assets/niak-profile.png"],sample)
        self.assertEqual(f.files["/data/homebrew/PPSA99386/assets/niak-profile-source.txt"],
                         b"0x12345678 png\n")

    def test_multiple_profiles_are_not_guessed(self):
        root="/system_data/priv/cache/profile/"
        sample=b"\x89PNG\r\n\x1a\n"+bytes(200)
        f=FakeFTP({root+"0x11111111/avatar.png":sample,root+"0x22222222/avatar.png":sample})
        ftpmod.install(f,self.root,False)
        self.assertNotIn("/data/homebrew/PPSA99386/assets/niak-profile.png",f.files)
        ftpmod.install(f,self.root,False,avatar_user_id="0x22222222")
        self.assertEqual(f.files["/data/homebrew/PPSA99386/assets/niak-profile.png"],sample)
        self.assertEqual(f.files["/data/homebrew/PPSA99386/assets/niak-profile-source.txt"],
                         b"0x22222222 png\n")

    def test_avatar_upload_failure_clears_previous_owner_before_image_update(self):
        from ftplib import error_perm
        source="/system_data/priv/cache/profile/0x12345678/avatar.png"
        marker="/data/homebrew/PPSA99386/assets/niak-profile-source.txt"
        destination="/data/homebrew/PPSA99386/assets/niak-profile.png"
        class BrokenFTP(FakeFTP):
            def storbinary(self,command,buf):
                if command=="STOR "+destination:
                    raise error_perm("550 write refused")
                return super().storbinary(command,buf)
        f=BrokenFTP({
            source:b"\x89PNG\r\n\x1a\n"+bytes(200),
            marker:b"0x87654321 png\n",
            destination:b"old-avatar",
        })
        with self.assertRaises(error_perm):
            ftpmod.copy_avatar_for_ftp(f)
        self.assertEqual(f.files[marker],b"")
        self.assertEqual(f.files[destination],b"old-avatar")

    def test_staged_dds_identifies_format_and_foreground_owner(self):
        user="0xA0B0C0D0"
        dds=b"DDS "+bytes(220)
        f=FakeFTP({"/system_data/priv/cache/profile/"+user+"/avatar128.dds":dds})
        ftpmod.install(f,self.root,False,avatar_user_id=user)
        root="/data/homebrew/PPSA99386/assets/"
        self.assertEqual(f.files[root+"niak-profile.dds"],dds)
        self.assertEqual(f.files[root+"niak-profile-source.txt"],b"0xA0B0C0D0 dds\n")
        native=(SCRIPT.parent/"profile.cpp").read_text()
        self.assertIn("const bool staged_dds=identified",native)
        self.assertIn("std::strncmp(marker,identity,10)",native)
        self.assertNotIn('niak_load_local_png(renderer, "/app0/assets/niak-profile.png")',native)

    def test_launchbox_reports_download_and_write_failures_without_secrets(self):
        from unittest.mock import patch
        from urllib.error import HTTPError
        from contextlib import redirect_stdout
        from io import StringIO
        import urllib.request
        ident="PPSA34015"
        artwork_id="00000000-0000-0000-0000-000000000001.jpg"
        (self.root/"assets").mkdir(exist_ok=True)
        (self.root/"assets/niak-launchbox-cases.tsv").write_text(
            ident+"\tOverview\tfr:"+artwork_id+"\t-\t-\t-\t42\n")
        ftp=FakeFTP({f"/user/app/{ident}/eboot.bin":b"installed"})
        output=StringIO()
        source="https://images.launchbox-app.com/"+artwork_id
        with (patch.object(urllib.request,"urlopen",
                           side_effect=HTTPError(source,403,"denied",None,None)),
              redirect_stdout(output)):
            self.assertEqual(ftpmod.fetch_retail_covers(ftp,self.root),0)
        report=output.getvalue()
        self.assertIn("HTTP [403: 1]",report)
        self.assertNotIn(artwork_id,report)
        self.assertIn("source distante restreinte",report)
        class Reply:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,n): return b"not an image"
        output=StringIO()
        with (patch.object(urllib.request,"urlopen",return_value=Reply()),
              patch.object(ftpmod,"_decode_retail_image",
                           side_effect=ValueError("malformed")),
              redirect_stdout(output)):
            self.assertEqual(ftpmod.fetch_retail_covers(ftp,self.root),0)
        self.assertIn("images rejetées=1",output.getvalue())
        output=StringIO()
        with (patch.object(urllib.request,"urlopen",return_value=Reply()),
              patch.object(ftpmod,"_decode_retail_image",
                           return_value=b"valid png fixture"),
              patch.object(ftpmod,"upload",side_effect=OSError("FTP 550")),
              redirect_stdout(output)):
            self.assertEqual(ftpmod.fetch_retail_covers(ftp,self.root),0)
        self.assertIn("FTP refusé=1",output.getvalue())

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

    def test_shadowmount_scanpath_and_title_metadata_diagnostic(self):
        from contextlib import redirect_stdout
        from io import StringIO
        manifest=b'{"titleId":"PPSA99386"}'
        param="/data/homebrew/PPSA99386/sce_sys/param.json"
        config="/data/shadowmount/config.ini"
        samples=[
            (b"# scanpath=/data/homebrew\nscanpath=/mnt/ext0/games\n",
             "ATTENTION : scanpath personnalisé sans /data/homebrew"),
            (b"scanpath=/mnt/ext0/games\nscanpath=/data/homebrew/\n",
             "/data/homebrew présent dans scanpath"),
            (b"scan_interval_seconds=15\n; scanpath=/mnt/ext0\n",
             "chemins de scan par défaut"),
        ]
        for content,expected in samples:
            with self.subTest(content=content):
                files={param:manifest,config:content}
                f=FakeFTP(files)
                out=StringIO()
                with redirect_stdout(out):
                    ftpmod.diagnose_title_registration(f)
                self.assertEqual(f.files,files)
                self.assertIn("Titre param.json cohérent : True",out.getvalue())
                self.assertIn(expected,out.getvalue())
        wrong=FakeFTP({param:b'{"titleId":"PPSA00000"}'})
        out=StringIO()
        with redirect_stdout(out):
            ftpmod.diagnose_title_registration(wrong)
        self.assertIn("Titre param.json cohérent : False",out.getvalue())
        self.assertIn("inscription non vérifiable",out.getvalue())

    def test_read_only_app_db_registration_evidence(self):
        import sqlite3
        from io import StringIO
        from contextlib import redirect_stdout
        location="/system_data/priv/mms/app.db"
        db=sqlite3.connect(":memory:")
        db.execute("CREATE TABLE tbl_contentinfo(titleId TEXT, titleName TEXT)")
        db.execute("INSERT INTO tbl_contentinfo VALUES (?,?)",
                   (ftpmod.TITLE,"NiakPS5"))
        image=db.serialize()
        db.close()
        for blob,expected in [
            (image,"PPSA99386 trouvé"),
            (b"invalid","inconnu"),
        ]:
            with self.subTest(expected=expected):
                ftp=FakeFTP({location:blob})
                previous=ftp.files.copy()
                output=StringIO()
                with redirect_stdout(output):
                    ftpmod.diagnose_appdb_registration(ftp)
                self.assertEqual(ftp.files,previous)
                self.assertIn(expected,output.getvalue())
        db=sqlite3.connect(":memory:")
        db.execute("CREATE TABLE tbl_contentinfo(titleId TEXT)")
        missing=db.serialize()
        db.close()
        ftp=FakeFTP({location:missing})
        output=StringIO()
        with redirect_stdout(output):
            ftpmod.diagnose_appdb_registration(ftp)
        self.assertIn("absent de la copie reçue",output.getvalue())
        self.assertEqual(ftp.files,{location:missing})

    def test_log_separates_lnc_success_from_stale_process(self):
        last="NiakPS5 optional autostart start rc=0x00000000\n"
        sys="sceSystemServiceLaunchApp rc=0x80940005\n"
        accepted="sceLncUtilLaunchApp accepted app id rc=0x0000ABCD\n"
        refused="sceLncUtilLaunchApp refused rc=0x80940031\n"
        from_lnc=last+sys+accepted
        observed,heartbeat=ftpmod.interpret_broker_log(from_lnc,clock=1000)
        self.assertIn("succès HISTORIQUE (LncUtil)",observed)
        self.assertIn("aucun horodatage",heartbeat)
        self.assertIn("échec historique",ftpmod.interpret_broker_log(
            last+sys+refused,clock=1000)[0])
        self.assertIn("échec historique",ftpmod.interpret_broker_log(
            last+sys,clock=1000)[0])
        recent=last+sys+accepted+"NiakPS5 broker heartbeat epoch=900 pid=12345\n"
        observed,heartbeat=ftpmod.interpret_broker_log(recent,clock=1000)
        self.assertIn("succès HISTORIQUE (LncUtil)",observed)
        self.assertIn("activité récente",heartbeat)
        self.assertIn("PID 12345",heartbeat)
        self.assertIn("dernier battement ancien",
                      ftpmod.interpret_broker_log(recent,clock=1900)[1])
        after=last+sys+accepted+sys+refused
        self.assertIn("échec historique",ftpmod.interpret_broker_log(
            after,clock=1000)[0])
        self.assertEqual("non confirmée",
                         ftpmod.interpret_broker_log("arbitrary text")[0])

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

    def test_status_reports_missing_art_per_installed_title_read_only(self):
        import io
        from contextlib import redirect_stdout
        game="/user/app/PPSA34015/eboot.bin"
        art=f"/data/homebrew/{ftpmod.TITLE}/assets/niak-cases/PPSA34015-front.png"
        files={game:b"game",art:b"cached"}
        ftp=FakeFTP(files)
        output=io.StringIO()
        with redirect_stdout(output):
            ftpmod.diagnose(ftp)
        self.assertEqual(ftp.files,files)
        report=output.getvalue()
        self.assertIn("Couverture des 1 titres visibles : 1 rectos, 0 versos, 0 tranches.",report)
        self.assertNotIn(ftpmod.TITLE,ftpmod._installed_title_ids(ftp,300))
        self.assertNotIn("Sans recto privé",report)

    def test_art_cache_handles_absolute_and_basename_ftp_listings(self):
        from unittest.mock import patch
        import urllib.request
        for mode in ("absolute","basename","relative"):
            with self.subTest(mode=mode):
                ident="PPSA34015"
                stored=f"/data/homebrew/{ftpmod.TITLE}/assets/niak-cases/{ident}-front.png"
                ftp=FakeFTP({stored:b"cached",
                             f"/user/app/{ident}/eboot.bin":b"game",
                             ftpmod.CASE_CACHE_SOURCES:(
                        ident+"\tfront\t00000000-0000-0000-0000-000000000001.jpg\n").encode(),})
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
                      patch.object(ftpmod,"_cache_hit",return_value=True),
                      patch.object(urllib.request,"urlopen") as net):
                    self.assertEqual(ftpmod.fetch_retail_covers(ftp,self.root),0)
                    net.assert_not_called()
                self.assertEqual(ftp.files[stored],b"cached")

    def test_art_cache_does_not_refetch_installed_front(self):
        from unittest.mock import patch
        import urllib.request
        id="PPSA34015"
        existing=f"/data/homebrew/{ftpmod.TITLE}/assets/niak-cases/{id}-front.png"
        f=FakeFTP({f"/user/app/{id}/eboot.bin":b"game",existing:b"image",
                   ftpmod.CASE_CACHE_SOURCES:
                   (id+"\tfront\t00000000-0000-0000-0000-000000000001.jpg\n").encode()})
        (self.root/"assets").mkdir(exist_ok=True)
        (self.root/"assets/niak-launchbox-cases.tsv").write_text(
            id+"\t-\tfr:00000000-0000-0000-0000-000000000001.jpg\t-\t-\t-\t4\n")
        with (patch.object(urllib.request,"urlopen") as open_url,
              patch.object(ftpmod,"_cache_hit",return_value=True)):
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

    def test_stale_cached_art_requires_redownload_and_rewrites_provenance(self):
        from unittest.mock import patch
        import urllib.request
        ident="PPSA34015"
        image="00000000-0000-0000-0000-000000000002.jpg"
        old="00000000-0000-0000-0000-000000000001.jpg"
        (self.root/"assets").mkdir(exist_ok=True)
        (self.root/"assets/niak-launchbox-cases.tsv").write_text(
            f"{ident}\t-\tfr:{image}\t-\t-\t-\t8\n")
        asset=f"/data/homebrew/{ftpmod.TITLE}/assets/niak-cases/{ident}-front.png"
        f=FakeFTP({f"/user/app/{ident}/eboot.bin":b"present",
                   asset:b"old",
                   ftpmod.CASE_CACHE_SOURCES:
                       f"{ident}\tfront\t{old}\n".encode()})
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b"new source"
        with (patch.object(urllib.request,"urlopen",return_value=Response()),
              patch.object(ftpmod,"_decode_retail_image",return_value=b"new png")):
            self.assertEqual(ftpmod.fetch_retail_covers(f,self.root),1)
        self.assertEqual(f.files[asset],b"new png")
        self.assertIn(image.encode(),f.files[ftpmod.CASE_CACHE_SOURCES])
        self.assertNotIn(old.encode(),f.files[ftpmod.CASE_CACHE_SOURCES])

    def test_install_preflight_is_atomic_on_invalid_local_package(self):
        meta=self.root/"sce_sys/param.json"
        for bad in (b'{bad-json',b'{"titleId":"PPSA00001"}',b'{"titleId":null}'):
            meta.write_bytes(bad)
            f=FakeFTP()
            with self.assertRaises(ValueError):
                ftpmod.install(f,self.root,False)
            self.assertEqual(f.files,{})
        meta.write_bytes(b'{"titleId":"PPSA99386"}')
        runtime=self.root/"sce_module/libc.prx"
        runtime.unlink()
        f=FakeFTP()
        with self.assertRaises(ValueError):
            ftpmod.install(f,self.root,False)
        self.assertEqual(f.files,{})
        runtime.write_bytes(b"native runtime")
        assets=self.root/"assets"
        assets.mkdir(exist_ok=True)
        (assets/"nested.zip").write_bytes(b"nested")
        f=FakeFTP()
        with self.assertRaises(ValueError):
            ftpmod.install(f,self.root,False)
        self.assertEqual(f.files,{})

    def test_invalid_elf_refuses_changes(self):
        f=FakeFTP()
        (self.root/"tools/niakps5/niakps5.elf").write_bytes(b"Not an ELF")
        with self.assertRaises(ValueError):
            ftpmod.install(f,self.root,True)
        self.assertNotIn(ftpmod.AUTOLOAD,f.files)
        self.assertEqual(f.files,{})
if __name__=="__main__":
    unittest.main()
