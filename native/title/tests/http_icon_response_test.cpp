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
