#!/usr/bin/env python3
"""Offline checks of the safe diagnostic, with an isolated fake PS5 filesystem."""
import os
import pathlib
import subprocess
import sys
import tempfile

def main():
    binary = sys.argv[1]
    with tempfile.TemporaryDirectory(prefix="niak-diag-") as temp:
        root = pathlib.Path(temp)
        (root / "data/niakps5/assets").mkdir(parents=True)
        env = {**os.environ, "NIAK_DIAG_ROOT": temp}
    
        def run(expected, message):
            result = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=8)
            log = (root / "data/niakps5-diagnostic.log").read_text()
            assert result.returncode == expected, result
            assert message in result.stdout, result.stdout
            assert message in log, log
            return log
    
        run(2, "UI absente")
        ui = root / "data/niakps5/niakps5_ui.elf"
        ui.write_bytes(b"not an ELF")
        run(2, "UI absente")
        ui.write_bytes(b"\x7fELF" + bytes(128))
        run(2, "polices absentes")
        for face in ("manrope.ttf", "instrument-serif.ttf"):
            (root / "data/niakps5/assets" / face).write_bytes(b"font")
        log = run(0, "PS Now/fakeapp absents")
        assert "ABSENT legacy PS Now" in log, log
        assert not (root / "system_ex").exists(), "diagnostic wrote protected folders"
        print("NiakPS5 preflight diagnostic: OK (safe, no system writes)")

if __name__ == '__main__':
    main()
