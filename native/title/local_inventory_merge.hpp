// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Merge two owner-local metadata overlays by exact installed title ID.
// This function NEVER establishes that a title is installed: catalogue
// consumers must join the merged data to independently verified live IDs.
#include "local_inventory.h"
#include <algorithm>
#include <cstring>
#include <vector>

inline int niak_merge_local_inventories(
    const char *packaged_path,const char *private_path,
    NiakGame *out,std::size_t cap,int *packaged_count=nullptr,
    int *private_count=nullptr) {
    if(!packaged_path || !private_path || !out || cap==0 ||
       cap>NIAKPS5_MAX_GAMES)return -1;
    const int bundled=niak_scan_local_inventory(packaged_path,out,cap);
    if(packaged_count)*packaged_count=bundled;
    std::vector<NiakGame> private_games(cap);
    const int local=niak_scan_local_inventory(
        private_path,private_games.data(),cap);
    if(private_count)*private_count=local;
    int merged=std::max(0,bundled);
    if(local>0)for(int i=0;i<local;++i) {
        const NiakGame &record=private_games[static_cast<std::size_t>(i)];
        int index=0;
        for(;index<merged;++index)
            if(std::strcmp(out[index].id,record.id)==0)break;
        if(index<merged)
            out[index]=record; // owner's latest overlay wins
        else if(static_cast<std::size_t>(merged)<cap)
            out[merged++]=record;
    }
    return merged;
}
