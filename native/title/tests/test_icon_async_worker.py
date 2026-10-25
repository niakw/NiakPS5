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
        self.assertIn("decode_icon_thumbnail(bytes,pixels)",worker)
        self.assertIn("state.completed_pixels=std::move(pixels);",worker)
        self.assertIn("state.seen.erase(id);",worker)
        self.assertIn("state.seen.erase(id);",SOURCE[SOURCE.index("std::uint32_t niak_take_downloaded_game_icon("):])

    def test_network_worker_releases_raw_images_before_gpu_upload(self):
        worker=SOURCE[SOURCE.index("void icon_reader_worker() {"):
                      SOURCE.index("void request_missing_icon(")]
        self.assertIn("std::vector<unsigned char> pixels;",worker)
        self.assertIn("if(!complete || !decode_icon_thumbnail(bytes,pixels))",worker)
        self.assertIn("state.completed_pixels=std::move(pixels);",worker)
        self.assertIn("one 256x256 RGBA buffer: 256 KiB",SOURCE)
        self.assertNotIn("completed_bytes",SOURCE)
        self.assertIn("return renderer.create_texture(kTarget,kTarget,pixels.data());",SOURCE)
        self.assertIn("return renderer.create_texture(kTarget,kTarget,bytes.data());",SOURCE)

    def test_renderer_consumes_and_replaces_fallback(self):
        self.assertIn("niak_take_downloaded_game_icon",HEADER)
        self.assertIn("return renderer.create_texture(kTarget,kTarget,bytes.data());",SOURCE)
        poll=SOURCE[SOURCE.index("std::uint32_t niak_take_downloaded_game_icon("):
                    SOURCE.index("std::uint32_t niak_load_game_background(")]
        self.assertNotIn("decode_upload(",poll)
        self.assertNotIn("decode_icon_thumbnail(",poll)
        self.assertIn("if(bytes.size()!=std::size_t(kTarget)*kTarget*4u)return 0;",poll)
        self.assertIn("scaled=std::move(rgba);",SOURCE)
        self.assertIn("if(!decode_icon_thumbnail(image,pixels))return 0;",SOURCE)
        self.assertIn("renderer.destroy_texture(handle);",PATCH)
        self.assertIn("if(it->cover)renderer.destroy_texture(it->cover);",PATCH)
        self.assertIn("it->cover_is_image=true;",PATCH)
        self.assertIn("catalog.refresh_pending_game_icons(renderer);",PATCH)
        self.assertIn("#include <cstring>",PATCH)
        self.assertIn("if(navigation_idle)",PATCH)
        self.assertIn("void niak_request_missing_game_icon(const char *title_id);",HEADER)
        self.assertIn("request_missing_icon(id);",SOURCE)
        self.assertIn("void Catalog::retry_missing_game_icons()",PATCH)
        self.assertIn("catalog.retry_missing_game_icons();",PATCH)
        self.assertIn("if(navigation_idle && frames>0 && frames%600u==0)",PATCH)
        self.assertIn("icon_retry_cursor_=(index+1)%items_.size();",PATCH)
        self.assertIn("icon_retry_cursor_=0;",PATCH)

if __name__=="__main__":
    unittest.main()
