#include "../http_icon_response.hpp"
#include <cassert>
#include <string>
#include <vector>
static std::vector<unsigned char> wire(const std::string &s) {
    return {s.begin(),s.end()};
}
int main() {
    constexpr std::size_t limit=4096;
    std::vector<unsigned char> out;
    const std::string fixed="HTTP/1.1 200 OK\r\nContent-Length: 6\r\n"
                            "Connection: keep-alive\r\n\r\nABCDEF";
    auto bytes=wire(fixed);
    assert(niak_http_icon_body(bytes,false,limit,out)==NiakHttpState::Complete);
    assert(std::string(out.begin(),out.end())=="ABCDEF");
    bytes=wire(fixed.substr(0,fixed.size()-2));
    assert(niak_http_icon_body(bytes,false,limit,out)==NiakHttpState::NeedMore);
    assert(niak_http_icon_body(bytes,true,limit,out)==NiakHttpState::Invalid);
    bytes=wire("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
               "3\r\nABC\r\n3\r\nDEF\r\n0\r\n\r\n");
    assert(niak_http_icon_body(bytes,false,limit,out)==NiakHttpState::Complete);
    assert(std::string(out.begin(),out.end())=="ABCDEF");
    // Reassembly across many received fragments must never publish an
    // incomplete PNG body, and reconstruct each byte exactly once.
    std::string chunks="HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n";
    std::string picture;
    for(unsigned block=0;block<64;++block) {
        const std::string piece(16384,char('A'+block%26));
        picture+=piece;
        chunks+="4000\r\n"+piece+"\r\n";
    }
    chunks+="0\r\n\r\n";
    std::vector<unsigned char> assembled;
    for(std::size_t cap=4096;cap<chunks.size();cap+=32768) {
        const auto incomplete=wire(chunks.substr(0,cap));
        assert(niak_http_icon_body(incomplete,false,2*1024*1024,assembled)
               ==NiakHttpState::NeedMore);
        assert(assembled.empty());
    }
    auto complete=wire(chunks);
    assert(niak_http_icon_body(complete,false,2*1024*1024,assembled)
           ==NiakHttpState::Complete);
    assert(std::string(assembled.begin(),assembled.end())==picture);
    bytes=wire("HTTP/1.0 200 OK\r\nContent-Type: image/png\r\n\r\nABCDEF");
    assert(niak_http_icon_body(bytes,false,limit,out)==NiakHttpState::NeedMore);
    assert(niak_http_icon_body(bytes,true,limit,out)==NiakHttpState::Complete);
    bytes=wire("HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n");
    assert(niak_http_icon_body(bytes,true,limit,out)==NiakHttpState::Invalid);
    bytes=wire("HTTP/1.1 200 OK\r\nContent-Length: 999999\r\n\r\n");
    assert(niak_http_icon_body(bytes,false,limit,out)==NiakHttpState::Invalid);
    bytes=wire("HTTP/1.1 200 OK\r\nContent-Length: 99999999999999999999999999999999\r\n\r\n");
    assert(niak_http_icon_body(bytes,false,limit,out)==NiakHttpState::Invalid);
    bytes=wire("HTTP/1.1 200X\r\nContent-Length: 2\r\n\r\nAB");
    assert(niak_http_icon_body(bytes,false,limit,out)==NiakHttpState::Invalid);
    bytes=wire("HTTP/1.1 200 OK\r\nContent-Length: 2\r\n"
               "Content-Length: 3\r\n\r\nABC");
    assert(niak_http_icon_body(bytes,false,limit,out)==NiakHttpState::Invalid);
    bytes=wire("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n"
               "Content-Length: 6\r\n\r\n6\r\nABCDEF\r\n0\r\n\r\n");
    assert(niak_http_icon_body(bytes,false,limit,out)==NiakHttpState::Invalid);
    return 0;
}
