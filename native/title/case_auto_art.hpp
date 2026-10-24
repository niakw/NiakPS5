// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <array>
// Asynchronously fetch matching public LaunchBox artwork to NiakPS5's
// private sandbox. Never block the render thread or send the title ID.
// Only a change of focused game may request remote assets. Null or an
// application clears pending work; never download for the entire shelf.
void niak_select_case_art(const char *title_id);
// Lower-level queue function: requires the ID to still be selected.
void niak_queue_auto_case_art(const char *title_id,const char *side);

// Read-only download statistics; all errors remain visible when sandbox
// network access is denied. No user identifiers are exposed.
struct NiakArtDownloadStatus {
 unsigned indexed,queued,completed,network_failed,decode_failed,write_failed,unmatched;
 int last_network_error;
 unsigned requests,exhausted;
 int last_network_stage;
 // Per-side completion epochs let the renderer replace ONLY textures that
 // have changed, including promotion from cached PC/PS4 to a PS5 box back.
 std::array<unsigned,7> sides_completed{};
};
NiakArtDownloadStatus niak_case_art_download_status();
