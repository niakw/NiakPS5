#!/usr/bin/env python3
"""Host regression: an accepted LncUtil fallback is not a failed launch."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
TEST=r"""
#include "niak/launch_log_status.h"
#include <assert.h>
int main(void) {
    const char *fail="NiakPS5 optional autostart start rc=0x00000000\n"
        "UserService initialize rc=0x00000000\n"
        "sceSystemServiceLaunchApp rc=0x80940005\n";
    assert(niak_last_launch_result(fail)==NIAK_LAUNCH_LOG_SYSTEM_FAILED);
    const char *ok="NiakPS5 optional autostart start rc=0x00000000\n"
        "sceSystemServiceLaunchApp rc=0x80940005\n"
        "sceLncUtilLaunchApp accepted app id rc=0x00007777\n";
    assert(niak_last_launch_result(ok)==NIAK_LAUNCH_LOG_LNC_OK);
    const char *still_fail="NiakPS5 optional autostart start rc=0x00000000\n"
        "sceSystemServiceLaunchApp rc=0x80940005\n"
        "sceLncUtilLaunchApp refused rc=0x80940031\n";
    assert(niak_last_launch_result(still_fail)==NIAK_LAUNCH_LOG_LNC_FAILED);
    const char *invalid="NiakPS5 optional autostart start rc=0x00000000\n"
        "sceSystemServiceLaunchApp rc=0x80940005\n"
        "sceLncUtilLaunchApp returned invalid app id rc=0x00000000\n";
    assert(niak_last_launch_result(invalid)==NIAK_LAUNCH_LOG_LNC_FAILED);
    const char *after="NiakPS5 optional autostart start rc=0x00000000\n"
        "sceSystemServiceLaunchApp rc=0x80940005\n"
        "sceLncUtilLaunchApp accepted app id rc=0x00007777\n"
        "sceSystemServiceLaunchApp rc=0x80940005\n";
    assert(niak_last_launch_result(after)==NIAK_LAUNCH_LOG_SYSTEM_FAILED);
    const char *system="NiakPS5 optional autostart start rc=0x00000000\n"
        "sceSystemServiceLaunchApp rc=0x00000000\n";
    assert(niak_last_launch_result(system)==NIAK_LAUNCH_LOG_SYSTEM_OK);
    assert(niak_last_launch_result("abc")==NIAK_LAUNCH_LOG_NO_PAYLOAD);
    return 0;
}
"""
class LogTests(unittest.TestCase):
    def test_latest_attempt_and_fallback(self):
        cc=shutil.which("cc")
        if not cc:self.skipTest("No C compiler")
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            (path/"niak").mkdir()
            shutil.copyfile(ROOT/"launch_log_status.h",path/"niak/launch_log_status.h")
            (path/"main.c").write_text(TEST,encoding="utf8")
            subprocess.run([cc,"-std=c11","-Wall","-Wextra","-Werror",
                            "-I",str(path),str(path/"main.c"),"-o",str(path/"run")],
                            check=True,capture_output=True,text=True)
            subprocess.run([str(path/"run")],check=True,capture_output=True,text=True)
if __name__=="__main__":
    unittest.main()
