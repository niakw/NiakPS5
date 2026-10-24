"""The PS5 icon worker may perform HTTP; it must never upload GPU textures."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/"game_icons.cpp").read_text()
PATCH=(ROOT/"prepare.py").read_text()
HEADER=(ROOT/"game_icons.hpp").read_text()

class IconAsyncWorkerTests(unittest.TestCase):
    def test_ps5_loader_enqueues_without_network(self):
        loader=SOURCE[SOURCE.index("std::uint32_t niak_load_game_icon("):
                      SOURCE.index("std::uint32_t niak_take_downloaded_game_icon(")]
        ps5=loader[loader.index("#if defined(__PROSPERO__)"):
                    loader.index("#else")]
        self.assertIn("request_missing_icon(id)",ps5)
        self.assertNotIn("download(",ps5)
        self.assertNotIn("renderer.create_texture(",ps5)

    def test_only_reader_owns_http(self):
        worker=SOURCE[SOURCE.index("void icon_reader_worker() {"):
                      SOURCE.index("void request_missing_icon(")]
        self.assertIn("download(url,bytes)",worker)
        self.assertIn("state.wake.wait(",worker)
        self.assertIn("!state.completed && !state.queue.empty()",worker)
        self.assertIn("std::thread([] {icon_reader_worker();}).detach();",SOURCE)
        self.assertIn("state.seen.size()>=4096",SOURCE)
        self.assertNotIn("renderer.",worker)
        self.assertIn("state.completed_bytes=std::move(bytes);",worker)

    def test_renderer_consumes_and_replaces_fallback(self):
        self.assertIn("niak_take_downloaded_game_icon",HEADER)
        self.assertIn("return decode_upload(renderer,bytes);",SOURCE)
        self.assertIn("renderer.destroy_texture(handle);",PATCH)
        self.assertIn("if(it->cover)renderer.destroy_texture(it->cover);",PATCH)
        self.assertIn("it->cover_is_image=true;",PATCH)
        self.assertIn("catalog.refresh_pending_game_icons(renderer);",PATCH)
        self.assertIn("if(navigation_idle)",PATCH)

if __name__=="__main__":
    unittest.main()
