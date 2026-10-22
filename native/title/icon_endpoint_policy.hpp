// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>

// Classify a complete HTTP response header WITHOUT reading the body.
// Receiving just "HTTP/1.1 200 OK" is not proof that a stalled server
// can actually deliver an icon, but a complete 404 is a valid reply.
enum class NiakIconReply { NeedMore, Success, OtherStatus, Invalid };
inline NiakIconReply niak_icon_reply(const unsigned char *data,
                                    std::size_t size) {
    if(!data || size<16)return NiakIconReply::NeedMore;
    if(std::memcmp(data,"HTTP/1.1 ",9)!=0 &&
       std::memcmp(data,"HTTP/1.0 ",9)!=0)
        return NiakIconReply::Invalid;
    if(data[9]<'0'||data[9]>'9'||data[10]<'0'||data[10]>'9'||
       data[11]<'0'||data[11]>'9'||data[12]!=' ')
        return NiakIconReply::Invalid;
    const std::size_t cap=size<8192?size:8192;
    bool complete=false;
    for(std::size_t p=0;p+4<=cap;++p) {
        if(data[p]=='\r'&&data[p+1]=='\n'&&
           data[p+2]=='\r'&&data[p+3]=='\n') {
            complete=true;break;
        }
    }
    if(!complete)return size>8192?NiakIconReply::Invalid:
                                   NiakIconReply::NeedMore;
    return std::memcmp(data+9,"200",3)==0?NiakIconReply::Success:
                                            NiakIconReply::OtherStatus;
}

// Transport failures are endpoint-wide; HTTP 404 for one game's art is not.
// Back off only after two consecutive socket/timeouts, and retry on a
// monotonic clock without permanently blacklisting the local service.
struct NiakIconEndpointPolicy {
    unsigned consecutive_failures=0;
    std::uint64_t retry_after_ms=0;
    bool allowed(std::uint64_t now_ms) const {
        return now_ms >= retry_after_ms;
    }
    void responded() {
        consecutive_failures=0;
        retry_after_ms=0;
    }
    void transport_failed(std::uint64_t now_ms) {
        if(consecutive_failures<2)++consecutive_failures;
        if(consecutive_failures>=2) {
            // Saturating addition is unnecessary for a real monotonic clock,
            // but prevents wrap from re-enabling an endpoint on bad inputs.
            constexpr std::uint64_t limit=UINT64_MAX-10000u;
            retry_after_ms=now_ms>=limit?UINT64_MAX:now_ms+10000u;
        }
    }
};
