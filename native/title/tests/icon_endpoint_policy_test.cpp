#include "../icon_endpoint_policy.hpp"
#include <cassert>
int main() {
    const char *incomplete="HTTP/1.1 200 OK\r\nContent-Length: 99\r\n";
    assert(niak_icon_reply(
        reinterpret_cast<const unsigned char*>(incomplete),
        std::strlen(incomplete))==NiakIconReply::NeedMore);
    const char *okay="HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n";
    assert(niak_icon_reply(reinterpret_cast<const unsigned char*>(okay),
        std::strlen(okay))==NiakIconReply::Success);
    const char *missing="HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n";
    assert(niak_icon_reply(reinterpret_cast<const unsigned char*>(missing),
        std::strlen(missing))==NiakIconReply::OtherStatus);
    const char *bad="HTTP/1.1 20X OK\r\n\r\n";
    assert(niak_icon_reply(reinterpret_cast<const unsigned char*>(bad),
        std::strlen(bad))==NiakIconReply::Invalid);
    NiakIconEndpointPolicy policy;
    assert(policy.allowed(1));
    policy.transport_failed(100);
    assert(policy.allowed(100)); // One isolated error is not a circuit break.
    policy.responded();           // A legitimate 404 still proves API alive.
    policy.transport_failed(101);
    assert(policy.allowed(101));
    policy.transport_failed(102);
    assert(!policy.allowed(103));
    assert(!policy.allowed(10101));
    assert(policy.allowed(10102));
    policy.responded();
    assert(policy.allowed(105));
    policy.transport_failed(UINT64_MAX);
    policy.transport_failed(UINT64_MAX);
    assert(!policy.allowed(102));
    assert(policy.allowed(UINT64_MAX));
    return 0;
}
