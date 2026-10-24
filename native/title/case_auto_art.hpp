// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Asynchronously fetch matching public LaunchBox artwork to NiakPS5's
// private sandbox. Never block the render thread or send the title ID.
void niak_queue_auto_case_art(const char *title_id,const char *side);

// Read-only download statistics; all errors remain visible when sandbox
// network access is denied. No user identifiers are exposed.
struct NiakArtDownloadStatus {
 unsigned indexed,queued,completed,network_failed,decode_failed,write_failed,unmatched;
};
NiakArtDownloadStatus niak_case_art_download_status();
