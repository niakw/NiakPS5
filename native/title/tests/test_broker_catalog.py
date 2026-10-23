#!/usr/bin/env python3
"""End-to-end host test: sandboxed client reads only local title IDs."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=r'''
#include "niak/broker_catalog.hpp"
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <cassert>
#include <chrono>
#include <cstring>
#include <thread>
#include <unistd.h>
int main() {
    int server=socket(AF_INET,SOCK_STREAM,0);
    assert(server>=0);
    int yes=1;
    setsockopt(server,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));
    sockaddr_in addr{};
    addr.sin_family=AF_INET;
    addr.sin_port=htons(19187);
    addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    assert(bind(server,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))==0);
    assert(listen(server,2)==0);
    std::thread backend([&] {
        for(int round=0;round<2;++round) {
            int client=accept(server,nullptr,nullptr);
            assert(client>=0);
            char request[16]{};
            ssize_t n=recv(client,request,sizeof(request),0);
            assert(n==6 && std::memcmp(request,"GAMES\n",6)==0);
            if(round==0) {
                assert(send(client,"GAM",3,0)==3);
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
                const char *rest="ES\nPPSA12345\nCUSA54321\nEND\n";
                assert(send(client,rest,std::strlen(rest),0)==ssize_t(std::strlen(rest)));
            } else {
                assert(send(client,"DENIED\n",7,0)==7);
            }
            close(client);
        }
    });
    NiakGame items[4]{};
    assert(niak_scan_broker_games(items,4)==2);
    assert(std::strcmp(items[0].id,"PPSA12345")==0);
    assert(std::strcmp(items[1].id,"CUSA54321")==0);
    assert(std::strcmp(items[0].title,"PPSA12345")==0);
    assert(niak_scan_broker_games(items,4)==-1);
    backend.join();
    close(server);
    assert(niak_scan_broker_games(items,4)==-1);
    return 0;
}
'''

class BrokerTests(unittest.TestCase):
    def test_real_fragmented_catalogue_socket(self):
        compiler=shutil.which("g++")
        if not compiler:
            self.skipTest("host C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as name:
            base=Path(name)
            (base/"niak").mkdir()
            for path in ("broker_catalog.hpp","broker_snapshot.h","loopback_connect.h","socket_guard.h"):
                shutil.copyfile(ROOT/path,base/"niak"/path)
            shutil.copyfile(ROOT.parent/"catalog.h",base/"niak"/"catalog.h")
            (base/"server.cpp").write_text(SOURCE,encoding="utf-8")
            executable=base/"broker-test"
            subprocess.run(
                [compiler,"-std=c++20","-pthread","-Wall","-Wextra","-Werror",
                 "-I",str(base),str(ROOT/"broker_catalog.cpp"),
                 str(base/"server.cpp"),"-o",str(executable)],
                check=True,timeout=40,capture_output=True,text=True)
            subprocess.run([str(executable)],check=True,timeout=15,
                           capture_output=True,text=True)

if __name__=="__main__":
    unittest.main()
