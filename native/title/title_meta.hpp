#pragma once
#include <string>
struct NiakTitleMetadata {std::string name,genre,publisher,released;};
bool niak_title_metadata(const char *id, NiakTitleMetadata &out);
std::string niak_title_summary(const NiakTitleMetadata &v);
