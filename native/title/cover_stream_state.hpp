// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Pure scheduling: render-thread texture uploads remain elsewhere.
#include <cstddef>
#include <vector>
namespace niak {
class CoverStreamState {
public:
 static constexpr std::size_t invalid=static_cast<std::size_t>(-1);
 void reset(std::size_t count) {done_.assign(count,0); next_=0;remaining_=count;}
 std::size_t remaining() const {return remaining_;}
 std::size_t take(std::size_t preferred=invalid) {
   if(!remaining_)return invalid;
   if(preferred<done_.size()&&!done_[preferred]) {
     done_[preferred]=1;--remaining_;return preferred;
   }
   while(next_<done_.size()&&done_[next_])++next_;
   if(next_>=done_.size())return invalid;
   const auto current=next_++;
   done_[current]=1;--remaining_;return current;
 }
private:
 std::vector<unsigned char> done_;
 std::size_t next_=0,remaining_=0;
};
}
