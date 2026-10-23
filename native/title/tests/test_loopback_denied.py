#!/usr/bin/env python3
"""Native sandbox regression: denied FIONBIO must not hide a live local broker."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=r"""
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <sys/ioctl.h>
/* Simulate the PS5's EPERM/EACCES on the network FIONBIO ioctl, leaving
 * the freshly allocated socket in its original blocking mode. */
static int niak_denied_ioctl(int fd,unsigned long request,...) {
    (void)fd;(void)request;errno=EACCES;return -1;
}
#define ioctl niak_denied_ioctl
#include "niak/loopback_connect.h"
#undef ioctl
#include <assert.h>
#include <fcntl.h>
#include <unistd.h>

int main(void) {
    int listener=socket(AF_INET,SOCK_STREAM,0);
    assert(listener>=0);
    struct sockaddr_in address={0};
    address.sin_family=AF_INET;
    address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    assert(bind(listener,(struct sockaddr *)&address,sizeof(address))==0);
    assert(listen(listener,1)==0);
    socklen_t size=sizeof(address);
    assert(getsockname(listener,(struct sockaddr *)&address,&size)==0);
    int client=socket(AF_INET,SOCK_STREAM,0);
    assert(client>=0);
    int stage=0;
    assert(niak_connect_bounded_ex(client,
            (const struct sockaddr *)&address,sizeof(address),150,&stage)==0);
    assert(stage==3);
    assert((fcntl(client,F_GETFL,0)&O_NONBLOCK)==0);
    int accepted=accept(listener,NULL,NULL);
    assert(accepted>=0);
    close(accepted);close(client);
    // No network access beyond 127.0.0.1 on the ioctl-denied path.
    struct sockaddr_in forbidden=address;
    forbidden.sin_addr.s_addr=htonl(0x08080808U);
    client=socket(AF_INET,SOCK_STREAM,0);
    assert(client>=0);
    assert(niak_connect_bounded_ex(client,
            (const struct sockaddr *)&forbidden,sizeof(forbidden),150,&stage)==-1);
    assert(errno==EACCES);
    assert(stage==2);
    close(client);
    close(listener);
    return 0;
}
"""

class DeniedIoctlTests(unittest.TestCase):
    def test_denied_nonblocking_ioctl_falls_back_only_for_loopback(self):
        cc=shutil.which("cc")
        if not cc:self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"niak").mkdir()
            shutil.copy2(ROOT/"loopback_connect.h",root/"niak"/"loopback_connect.h")
            (root/"sandbox.c").write_text(SOURCE,encoding="utf-8")
            exe=root/"sandbox-test"
            result=subprocess.run(
                [cc,"-std=c11","-Wall","-Wextra","-Werror",
                 "-I",str(root),str(root/"sandbox.c"),"-o",str(exe)],
                capture_output=True,text=True,timeout=25)
            self.assertEqual(result.returncode,0,result.stderr)
            subprocess.run([str(exe)],check=True,capture_output=True,
                           text=True,timeout=10)

if __name__=="__main__":
    unittest.main()
