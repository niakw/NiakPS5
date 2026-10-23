// SPDX-License-Identifier: GPL-3.0-or-later
#include "../case_back_media.hpp"
#include <cassert>
int main() {
  auto empty=niak_select_back_media({});
  assert(!empty.first.texture && !empty.second.texture);
  auto repeated=niak_select_back_media({{11u,1.7f},{11u,1.7f},{0u,1.f}});
  assert(repeated.first.texture==11u && !repeated.second.texture);
  auto unique=niak_select_back_media({{17u,1.77f},{17u,1.77f},
                                     {22u,1.6f},{22u,1.6f},{33u,1.f}});
  assert(unique.first.texture==17u && unique.second.texture==22u);
  return 0;
}
