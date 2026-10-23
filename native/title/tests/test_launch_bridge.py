#!/usr/bin/env python3
"""Exercise the real PS5 launch bridge protocol against a fragmented TCP server."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SERVER= r'''
#include <arpa/inet.h>
#include <cassert>
#include <chrono>
#include <cstring>
#include <sys/socket.h>
#include <thread>
#include <unistd.h>
#include "niak/launch_bridge.hpp"

static void send_parts(int fd,const char *first,const char *second) {
    assert(::send(fd,first,std::strlen(first),0)==ssize_t(std::strlen(first)));
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    assert(::send(fd,second,std::strlen(second),0)==ssize_t(std::strlen(second)));
}
int main() {
    const int server=::socket(AF_INET,SOCK_STREAM,0);
    assert(server>=0);
    int yes=1;::setsockopt(server,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));
    sockaddr_in local{};
    local.sin_family=AF_INET;local.sin_port=htons(19187);
    local.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    assert(::bind(server,reinterpret_cast<sockaddr*>(&local),sizeof(local))==0);
    assert(::listen(server,4)==0);
    std::thread worker([&]() {
        for(int i=0;i<5;++i) {
            int client=::accept(server,nullptr,nullptr);
            assert(client>=0);
            char buffer[40]{};
            const ssize_t count=::recv(client,buffer,sizeof(buffer),0);
            assert(count>0);
            if(i==0) {
                assert(std::strncmp(buffer,"PING\n",5)==0);
                send_parts(client,"PO","NG\n");
            } else if(i==1) {
                assert(std::strncmp(buffer,"STATUS\n",7)==0);
                send_parts(client,"PID 0000","400A\n");
            } else if(i==4) {
                assert(std::strncmp(buffer,"PING\n",5)==0);
                // A dead broker accepted the socket but never replied.
                std::this_thread::sleep_for(std::chrono::milliseconds(300));
            } else {
                assert(std::strncmp(buffer,"LAUNCH PPSA12345\n",17)==0);
                if(i==2)send_parts(client,"RC 0000","0000\n");
                else assert(::send(client,"RC 0",4,0)==4);
            }
            ::close(client);
        }
    });
    assert(niak_launch_registered_title("BAD")==-3);
    assert(niak_launch_broker_ready());
    assert(niak_launch_broker_pid()==0x400Au);
    const auto cached_start=std::chrono::steady_clock::now();
    for(int i=0;i<40;++i)assert(niak_launch_broker_ready());
    const auto cached_ms=std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now()-cached_start).count();
    assert(cached_ms<100); // No extra PING sockets while rendering Settings.
    assert(niak_launch_registered_title("PPSA12345")==0);
    assert(niak_launch_registered_title("PPSA12345")==-2);
    std::this_thread::sleep_for(std::chrono::milliseconds(1050));
    const auto before=std::chrono::steady_clock::now();
    assert(!niak_launch_broker_ready());
    assert(!niak_launch_broker_ready()); // cached failed health check
    const auto milliseconds=std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now()-before).count();
    assert(milliseconds<220);
    worker.join();
    ::close(server);
    const auto offline=std::chrono::steady_clock::now();
    assert(niak_launch_registered_title("PPSA12345")==-2);
    const auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now()-offline).count();
    assert(elapsed<300);
    return 0;
}
'''

class LaunchBridgeTests(unittest.TestCase):
    def test_real_fragmented_broker_messages(self):
        compiler=shutil.which("g++")
        if not compiler:
            self.skipTest("host g++ unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            (work/"niak").mkdir()
            shutil.copyfile(ROOT/"launch_bridge.hpp",work/"niak"/"launch_bridge.hpp")
            shutil.copyfile(ROOT/"socket_guard.h",work/"niak"/"socket_guard.h")
            shutil.copyfile(ROOT/"loopback_connect.h",work/"niak"/"loopback_connect.h")
            (work/"server.cpp").write_text(SERVER,encoding="utf8")
            binary=work/"launch-bridge-test"
            subprocess.run([
                compiler,"-std=c++20","-pthread","-Wall","-Wextra","-Werror",
                "-I",str(work),str(ROOT/"launch_bridge.cpp"),
                str(work/"server.cpp"),"-o",str(binary)],check=True,
                capture_output=True,text=True,timeout=50)
            subprocess.run([str(binary)],check=True,capture_output=True,
                           text=True,timeout=15)

if __name__=="__main__":
    unittest.main()
