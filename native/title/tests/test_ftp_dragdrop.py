#!/usr/bin/env python3
"""Single-folder FTP installation must not require CLI on the user's PS5."""
import importlib.util
from pathlib import Path
import hashlib
import json
import stat
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
module=ROOT/"pack_ftp_dragdrop.py"
spec=importlib.util.spec_from_file_location("niak_ftp_dragdrop",module)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FTPDropinTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.title=self.home/"PPSA99386"
        for filename,body in {
            "eboot.bin":b"ELF native title",
            "sce_module/libc.prx":b"runtime",
            "sce_sys/param.json":b'{"titleId":"PPSA99386"}',
            "tools/niakps5/niakps5.elf":b"\x7fELF" + b"payload",
            "assets/test.txt":b"visible",
        }.items():
            p=self.title/filename
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(body)
        payload=(self.title/"tools/niakps5/niakps5.elf").read_bytes()
        (self.title/"tools/niakps5/niakps5.elf.json").write_text(json.dumps(
            {"filename":"niakps5.elf","checksum":hashlib.sha256(payload).hexdigest()}))
    def test_one_data_folder_and_exact_two_payload_files(self):
        dest=self.home/"dropin"
        mod.stage(self.title,dest)
        app=dest/"data/homebrew/PPSA99386"
        slot=dest/"data/pldmgr/payloads/niakps5"
        self.assertEqual((app/"eboot.bin").read_bytes(),b"ELF native title")
        self.assertEqual((slot/"niakps5.elf").read_bytes(),
                         (app/"tools/niakps5/niakps5.elf").read_bytes())
        self.assertEqual((slot/"niakps5.elf.json").read_bytes(),
                         (app/"tools/niakps5/niakps5.elf.json").read_bytes())
        self.assertEqual([p.name for p in dest.iterdir()],["data"])
        self.assertFalse((dest/"data/pldmgr/autoload.txt").exists())
        self.assertFalse((dest/"data/pldmgr/pldmgr_config.txt").exists())
        self.assertEqual((slot/"niakps5.elf").stat().st_mode & 0o777,0o755)
    def test_no_nested_zips_in_transfer_folder(self):
        dest=self.home/"dropin"
        mod.stage(self.title,dest)
        self.assertEqual([p.name for p in dest.iterdir()],["data"])
        self.assertFalse(any(p.suffix.lower()==".zip" for p in dest.rglob("*")))
        self.assertFalse((dest/"data/pldmgr/autoload.txt").exists())

    def test_reject_corrupt_sidecar_before_copying(self):
        sidecar=self.title/"tools/niakps5/niakps5.elf.json"
        sidecar.write_text('{"filename":"niakps5.elf","checksum":"wrong"}')
        out=self.home/"dest"
        with self.assertRaisesRegex(ValueError,"checksum"):
            mod.stage(self.title,out)
        self.assertFalse(out.exists())
    def test_never_copy_user_autoload(self):
        (self.title/"autoload.txt").write_text("overwrite")
        with self.assertRaisesRegex(ValueError,"Never bundle"):
            mod.stage(self.title,self.home/"out")
    def test_never_accept_symlinked_console_assets(self):
        link=self.title/"assets/alias.png"
        link.symlink_to(self.title/"eboot.bin")
        with self.assertRaisesRegex(ValueError,"Symlinks forbidden"):
            mod.stage(self.title,self.home/"out")
if __name__=="__main__":
    unittest.main()
