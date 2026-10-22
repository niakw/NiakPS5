#include "../icon_endpoint_policy.hpp"
#include <cassert>
int main() {
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
