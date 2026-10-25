#pragma once
#include <string>
struct NiakTitleMetadata {std::string name,genre,publisher,released,category;};
// Call on the catalogue owner thread before rebuilding visible title data.
void niak_invalidate_title_metadata();
bool niak_title_metadata(const char *id, NiakTitleMetadata &out);
std::string niak_title_summary(const NiakTitleMetadata &v);
std::string niak_title_overview(const char *title_id);
