// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>

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
