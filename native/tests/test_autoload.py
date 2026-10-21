import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from autoload import apply, patched, BEGIN, END

BASE = "# existing important sequence\netaHEN.elf\n!1000\npldmgr.elf\n"

class AutoloadTests(unittest.TestCase):
    def test_enable_disable_is_reversible(self):
        result=patched(BASE, True)
        self.assertTrue(result.startswith(BASE))
        self.assertIn("niakps5_bootstrap.elf", result)
        self.assertEqual(patched(result, True), result)
        self.assertEqual(patched(result, False), BASE)
    def test_corrupted_markers_rejected(self):
        with self.assertRaises(ValueError):
            patched(BASE + BEGIN + "\n", True)
        with self.assertRaises(ValueError):
            patched(BASE + END + "\n", True)
    def test_no_write_before_confirmation_and_backup(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/"ps5_autoloader"
            folder.mkdir()
            cfg=folder/"autoload.txt"
            cfg.write_text(BASE)
            (folder/"niakps5_bootstrap.elf").write_bytes(b"example")
            with self.assertRaises(ValueError):
                apply(cfg,True,False,True)
            self.assertEqual(cfg.read_text(),BASE)
            preview=apply(cfg,True,True,False)
            self.assertIn("niakps5_bootstrap.elf",preview)
            self.assertEqual(cfg.read_text(),BASE)
            apply(cfg,True,True,True)
            self.assertEqual(cfg.read_text(),preview)
            apply(cfg,False,False,True)
            self.assertEqual(cfg.read_text(),BASE)
            self.assertEqual(len(list(folder.glob("autoload.txt.niakps5-backup-*"))),2)
    def test_rejects_other_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/"ps5_autoloader"
            folder.mkdir()
            source=folder/"autoload.txt"
            source.write_text(BASE)
            link=Path(root)/"autoload.txt"
            link.symlink_to(source)
            with self.assertRaises(ValueError):
                apply(link,False,False,True)
            with self.assertRaises(ValueError):
                apply(Path(root)/"preferences.txt",False,False,False)
if __name__=="__main__":
    unittest.main()
