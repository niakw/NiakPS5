#include "../cover_stream_state.hpp"
#include <cassert>
int main() {
 niak::CoverStreamState s;
 s.reset(6);
 assert(s.remaining()==6);
 assert(s.take()==0);
 assert(s.take(5)==5);
 assert(s.take(5)==1);
 assert(s.take(3)==3);
 assert(s.take()==2);
 assert(s.take()==4);
 assert(s.remaining()==0);
 assert(s.take(0)==niak::CoverStreamState::invalid);
 s.reset(2);
 assert(s.take(9)==0);
 assert(s.take(1)==1);
 s.reset(0);
 assert(s.take()==niak::CoverStreamState::invalid);
 return 0;
}
