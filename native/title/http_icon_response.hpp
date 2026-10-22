// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Bounded HTTP body framing for locally served PS5 game icons.
// Handles Content-Length, chunked responses, and close-delimited HTTP/1.0.
// Do not wait for EOF after a complete frame on a persistent connection.
#include <algorithm>
#include <cstddef>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

enum class NiakHttpState { NeedMore, Complete, Invalid };

inline NiakHttpState niak_http_icon_body(
    const std::vector<unsigned char> &wire,bool eof,std::size_t maximum,
    std::vector<unsigned char> &out) {
    constexpr std::size_t kMaxHeader=8192;
    if(wire.size()>maximum+kMaxHeader+256*1024)return NiakHttpState::Invalid;
    std::size_t header_end=0;
    const unsigned char separator[4]={'\r','\n','\r','\n'};
    for(std::size_t p=0;p+4<=wire.size() && p<kMaxHeader;++p) {
        if(std::memcmp(wire.data()+p,separator,4)==0) {
            header_end=p+4;break;
        }
    }
    if(!header_end)return wire.size()>kMaxHeader||eof?
        NiakHttpState::Invalid:NiakHttpState::NeedMore;
    if(header_end<16 || (std::memcmp(wire.data(),"HTTP/1.1 200",12)!=0 &&
                         std::memcmp(wire.data(),"HTTP/1.0 200",12)!=0) ||
                         (wire[12]!=' ' && wire[12]!='\r'))
        return NiakHttpState::Invalid;
    std::string header(reinterpret_cast<const char*>(wire.data()),header_end);
    if(header.find('\0')!=std::string::npos)return NiakHttpState::Invalid;
    auto trim=[](std::string value) {
        const auto a=value.find_first_not_of(" \t");
        if(a==std::string::npos)return std::string();
        const auto b=value.find_last_not_of(" \t");
        return value.substr(a,b-a+1);
    };
    auto lower=[](std::string value) {
        for(char &c:value)if(c>='A'&&c<='Z')c=char(c-'A'+'a');
        return value;
    };
    bool has_length=false,chunked=false,other_encoding=false;
    std::size_t length=0;
    std::size_t line=header.find("\r\n");
    if(line==std::string::npos)return NiakHttpState::Invalid;
    line+=2;
    while(line<header_end-2) {
        const auto end=header.find("\r\n",line);
        if(end==std::string::npos)return NiakHttpState::Invalid;
        if(end==line)break;
        const auto colon=header.find(':',line);
        if(colon==std::string::npos || colon>=end)return NiakHttpState::Invalid;
        const std::string key=lower(trim(header.substr(line,colon-line)));
        const std::string value=lower(trim(header.substr(colon+1,end-colon-1)));
        if(key=="content-length") {
            if(value.empty())return NiakHttpState::Invalid;
            std::size_t n=0;
            for(const char digit:value) {
                if(digit<'0'||digit>'9')return NiakHttpState::Invalid;
                const auto d=std::size_t(digit-'0');
                // Check before multiplication; oversized decimal strings
                // must not wrap back into a seemingly valid image size.
                if(d>maximum || n>(maximum-d)/10u)
                    return NiakHttpState::Invalid;
                n=n*10u+d;
            }
            if(has_length && n!=length)return NiakHttpState::Invalid;
            length=n;has_length=true;
        } else if(key=="transfer-encoding") {
            if(value.find("chunked")!=std::string::npos)chunked=true;
            else other_encoding=true;
        }
        line=end+2;
    }
    if(other_encoding || (chunked && has_length))return NiakHttpState::Invalid;
    if(chunked) {
        // Collect only (offset,size) pairs while the frame is incomplete.
        // Do not allocate/copy decoded image bytes at every TCP fragment.
        std::vector<std::pair<std::size_t,std::size_t>> spans;
        std::size_t decoded_size=0;
        std::size_t pos=header_end;
        for(;;) {
            const auto end=std::search(wire.begin()+pos,wire.end(),
                                       separator,separator+2);
            if(end==wire.end())return (wire.size()-pos>100||eof)?
                NiakHttpState::Invalid:NiakHttpState::NeedMore;
            const std::size_t end_at=std::size_t(end-wire.begin());
            if(end_at-pos>100)return NiakHttpState::Invalid;
            const std::string size_line(
                reinterpret_cast<const char*>(wire.data()+pos),end_at-pos);
            std::size_t n=0,digits=0;
            for(char c:size_line) {
                if(c==';')break; // optional chunk extension
                unsigned d=0;
                if(c>='0'&&c<='9')d=unsigned(c-'0');
                else if(c>='a'&&c<='f')d=unsigned(c-'a'+10);
                else if(c>='A'&&c<='F')d=unsigned(c-'A'+10);
                else return NiakHttpState::Invalid;
                if(++digits>8)return NiakHttpState::Invalid;
                n=n*16u+d;
            }
            if(!digits || n>maximum-decoded_size)return NiakHttpState::Invalid;
            pos=end_at+2;
            if(n==0) {
                // Consume bounded optional trailers, until a blank line.
                for(;;) {
                    const auto e=std::search(wire.begin()+pos,wire.end(),
                                              separator,separator+2);
                    if(e==wire.end())return eof?NiakHttpState::Invalid:
                                                NiakHttpState::NeedMore;
                    const std::size_t off=std::size_t(e-wire.begin());
                    if(off-pos>kMaxHeader)return NiakHttpState::Invalid;
                    if(off==pos) {
                        out.resize(decoded_size);
                        std::size_t copied=0;
                        for(const auto &span:spans) {
                            std::memcpy(out.data()+copied,
                                        wire.data()+span.first,span.second);
                            copied+=span.second;
                        }
                        return NiakHttpState::Complete;
                    }
                    pos=off+2;
                }
            }
            if(wire.size()-pos<n+2)return eof?NiakHttpState::Invalid:
                                                    NiakHttpState::NeedMore;
            if(wire[pos+n]!='\r'||wire[pos+n+1]!='\n')
                return NiakHttpState::Invalid;
            // Limit pathological tiny-chunk responses; bounded wire size
            // alone would still allow hundreds of thousands of allocations.
            if(spans.size()>=8192)return NiakHttpState::Invalid;
            spans.emplace_back(pos,n);
            decoded_size+=n;
            pos+=n+2;
        }
    }
    if(has_length) {
        if(wire.size()-header_end<length)return eof?NiakHttpState::Invalid:
                                                   NiakHttpState::NeedMore;
        out.assign(wire.begin()+header_end,wire.begin()+header_end+length);
        return NiakHttpState::Complete;
    }
    if(wire.size()-header_end>maximum)return NiakHttpState::Invalid;
    if(!eof)return NiakHttpState::NeedMore;
    out.assign(wire.begin()+header_end,wire.end());
    return NiakHttpState::Complete;
}
