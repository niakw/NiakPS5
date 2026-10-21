#!/usr/bin/env python3
"""Simple source contract tests for the pinned GPU-native title staging scripts."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]

class NativeTitleTests(unittest.TestCase):
    def test_standalone_native_title(self):
        source = (ROOT / "title" / "build.sh").read_text()
        self.assertIn("PPSA99386", source)
        self.assertIn("2188642afbcc8d84d36149124f3d9e39dc1b1a05", source)
        self.assertIn("dist/$title/eboot.bin", source)
        self.assertIn("sce_module/libc.prx", source)
        self.assertNotIn("niakps5_bootstrap.elf", source)

    def test_real_catalog_only(self):
        source = (ROOT / "title" / "prepare.py").read_text()
        self.assertIn('niak_scan_games("/system_data/priv/mms/app.db"', source)
        self.assertIn("Bibliotheque indisponible", source)
        self.assertIn("shelves_.resize(1)", source)
        self.assertIn("sceSystemServiceLaunchApp", source)
        self.assertIn("niak-manrope.huifont", source)
        self.assertIn("niak-instrument-serif.huifont", source)
        self.assertIn("IDENTIFIANT DU TITRE", source)
        self.assertIn("CATALOGUE INACCESSIBLE", source)
        self.assertIn("Fake clock or rating remains", source)
        self.assertIn("concepts::make_aurora", source)
        self.assertNotIn("Lumen Drift", source)
        compile(source, "prepare.py", "exec")

if __name__ == "__main__":
    unittest.main()
