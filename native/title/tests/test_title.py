#!/usr/bin/env python3
"""Simple source contract tests for the pinned GPU-native title staging scripts."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]

class NativeTitleTests(unittest.TestCase):
    def test_autostart_is_explicit_and_reversible(self):
        source = (ROOT / "title" / "autostart.c").read_text()
        self.assertIn("niakps5-autostart.enabled", source)
        self.assertIn("niakps5-autostart.disable", source)
        self.assertIn("sceSystemServiceLaunchApp", source)
        self.assertIn("GetAppIdOfRunningBigApp", source)
        self.assertNotIn("ptrace(", source)
        self.assertNotIn("mount(", source)

    def test_exact_ftp_package(self):
        import tempfile
        import json
        import sys
        import zipfile
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "PPSA99386"
            for path in ("eboot.bin", "sce_module/libc.prx", "sce_sys/param.json"):
                target=base / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({"titleId":"PPSA99386"}) if
                                  path.endswith("param.json") else "nonempty")
            (base / "assets").mkdir()
            package=Path(temp) / "PPSA99386.zip"
            subprocess.run([sys.executable, str(ROOT / "title" / "pack_ftp.py"),
                            "--folder", str(base), "--output", str(package)], check=True)
            with zipfile.ZipFile(package) as z:
                self.assertIsNone(z.testzip())
                self.assertEqual([n.split("/")[0] for n in z.namelist()],
                                 ["PPSA99386"] * len(z.namelist()))
                self.assertFalse(any(n.endswith(".zip") for n in z.namelist()))
                self.assertEqual((z.getinfo("PPSA99386/eboot.bin").external_attr >> 16) & 0o777, 0o755)
                self.assertEqual((z.getinfo("PPSA99386/sce_module/libc.prx").external_attr >> 16) & 0o777, 0o644)
            (base / "assets/inner.zip").write_text("forbidden")
            with self.assertRaises(subprocess.CalledProcessError):
                subprocess.run([sys.executable, str(ROOT / "title" / "pack_ftp.py"),
                                "--folder", str(base), "--output", str(package)],
                               check=True, capture_output=True)

    def test_standalone_native_title(self):
        source = (ROOT / "title" / "build.sh").read_text()
        self.assertIn("PPSA99386", source)
        self.assertIn("2188642afbcc8d84d36149124f3d9e39dc1b1a05", source)
        self.assertIn("dist/$title/eboot.bin", source)
        self.assertIn("sce_module/libc.prx", source)
        self.assertNotIn("niakps5_bootstrap.elf", source)

    def test_daily_wallpaper_pipeline(self):
        source = (ROOT / "title" / "fetch_daily_games.py").read_text()
        native = (ROOT / "title" / "daily_backdrop.cpp").read_text()
        compile(source, "fetch_daily_games.py", "exec")
        self.assertIn("Steam Store API", source)
        self.assertIn("path_full", source)
        self.assertIn("niak_daily_backdrop", native)
        self.assertIn("std::localtime", native)

    def test_real_top_navigation(self):
        from pathlib import Path
        code = (ROOT / "title" / "patch_home.py").read_text()
        compile(code, "patch_home.py", "exec")
        for token in ("update_tabs", "update_page", "draw_aux_page",
                      "context_.settings_changed = true", "Profil non lie"):
            self.assertIn(token, code)

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
