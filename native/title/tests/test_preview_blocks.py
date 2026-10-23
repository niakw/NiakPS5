#!/usr/bin/env python3
"""Prove public preview contains six user-supplied console blocks, not QA art."""
from pathlib import Path
from io import BytesIO
import base64
import hashlib
import unittest
from zipfile import ZipFile

TITLE=Path(__file__).resolve().parents[1]
ROOT=TITLE.parent.parent
EXPECTED_SHA="cd3383fa7705ec19ebfbb5923d67d75c9c9c3fd2c290b91edd562c2792c0ecc4"
EXPECTED={f"{family}-{part}.webp" for family in ("ps4","ps5")
          for part in ("front","back","spine")}

class PreviewBlocksTests(unittest.TestCase):
    def test_user_supplied_blocks_are_available_to_every_ci_run(self):
        src=TITLE/"assets"/"preview-blocks"
        self.assertEqual([p.name for p in sorted(src.glob("*.b64"))],
                         [f"{i:02}.b64" for i in range(6)])
        contents="".join((src/f"{i:02}.b64").read_text("ascii") for i in range(6))
        raw=base64.b64decode(contents,validate=True)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),EXPECTED_SHA)
        with ZipFile(BytesIO(raw)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()),EXPECTED)
            for name in EXPECTED:
                content=archive.read(name)
                self.assertGreater(len(content),600)
                self.assertEqual(content[:4],b"RIFF")
                self.assertEqual(content[8:12],b"WEBP")

    def test_standard_artifact_requires_actual_blocks(self):
        host=(TITLE/"host_preview.py").read_text("utf-8")
        workflow=(ROOT/".github/workflows/native-title.yml").read_text("utf-8")
        validator=(TITLE/"validate_preview.py").read_text("utf-8")
        self.assertNotIn('family.upper()+"  /  QA HEADER"',host)
        self.assertNotIn('" / QA FOOTER"',host)
        self.assertIn("NIAK_CASE_ORIGINAL_BLOCKS",host)
        self.assertIn("00-fixed-elements-PS4-PS5.png",host)
        self.assertIn("Expected exactly 6 PNG captures",validator)
        self.assertNotIn("00-fixed-elements-PS4-PS5.png build/niak-preview/",workflow)
        self.assertIn("NIAK_CASE_TOUR=1",workflow)
        self.assertIn("NiakPS5-OpenGL-interface-preview",workflow)
        self.assertIn("NIAK_CASE_TEMPLATE_ASSETS",workflow)

if __name__=="__main__":
    unittest.main()
