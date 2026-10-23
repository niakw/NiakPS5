#!/usr/bin/env python3
"""Private OpenGL preview uses the actual six templates, never synthetic QA."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("niak_private_preview",
                                             ROOT/"private_preview.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PrivatePreviewTests(unittest.TestCase):
    def test_original_six_templates_injected_into_local_kit_only(self):
        images={}
        sizes={
            "ps4-front.png":(949,136),"ps5-front.png":(1487,209),
            "ps4-back.png":(647,362),"ps5-back.png":(1000,411),
            "ps4-spine.png":(72,800),"ps5-spine.png":(85,1000),
        }
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td)
            archive=temp/"private.zip"
            with ZipFile(archive,"w") as output:
                for name,size in sizes.items():
                    width,height=size
                    images[name]=(b"\x89PNG\r\n\x1a\n"+
                                  b"\0"*8+struct.pack(">II",width,height)+
                                  b"\0"*14)
                    output.writestr("PPSA99386/assets/niak-templates/"+name,
                                    images[name])
            kit=temp/"kit"
            target=module.stage_private_templates(kit,archive)
            self.assertEqual({p.name for p in target.glob("*.png")},set(images))
            for name,content in images.items():
                self.assertEqual((target/name).read_bytes(),content)
            self.assertFalse((temp/"PPSA99386").exists())
            with ZipFile(archive,"a") as output:
                output.writestr("PPSA99386/../../escape.png",b"invalid")
            with self.assertRaises(ValueError):
                module.stage_private_templates(kit,archive)

    def test_refuses_partial_user_supplied_assets(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            png=(b"\x89PNG\r\n\x1a\n"+b"\0"*8+
                 struct.pack(">II",949,136)+b"\0"*14)
            path=root/"partial.zip"
            with ZipFile(path,"w") as out:
                out.writestr("PPSA99386/assets/niak-templates/ps4-front.png",
                             png)
            with self.assertRaisesRegex(ValueError,"Six exact"):
                module.stage_private_templates(root/"kit",path)

    def test_host_only_and_no_github_asset_upload(self):
        source=(ROOT/"private_preview.py").read_text("utf-8")
        self.assertIn("NIAK_CASE_TEMPLATE_ASSETS",source)
        self.assertIn("niak-preview-private",source)
        self.assertIn("validate_preview.py",source)
        self.assertNotIn("git push",source)
        workflow=(ROOT.parent.parent/".github/workflows/native-title.yml").read_text("utf-8")
        self.assertIn("niak-preview-templates",workflow)
        self.assertNotIn("private_preview.py",workflow)

if __name__=="__main__":
    unittest.main()
