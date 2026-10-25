"""CPU-only PS5 avatar preparation and foreground-account isolation."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PROFILE=(ROOT/"profile.cpp").read_text()
ICON=(ROOT/"game_icons.cpp").read_text()
HEADER=(ROOT/"profile.hpp").read_text()
STAGE=(ROOT/"prepare.py").read_text()

class ProfileWorkerTests(unittest.TestCase):
    def test_cpu_reader_never_uses_gpu_or_network(self):
        worker=PROFILE[PROFILE.index("bool prepare_dds_avatar("):
                       PROFILE.index("struct AvatarReadState {")]
        self.assertIn("niak_decode_avatar_dds(",worker)
        self.assertIn("niak_prepare_profile_png_file(",worker)
        self.assertIn('std::strcmp(marker+11,"png\\n")==0',worker)
        self.assertIn('std::strcmp(marker+11,"dds\\n")==0',worker)
        self.assertIn("/system_data/priv/cache/profile/0x%08X/%s",worker)
        self.assertNotIn("renderer.",worker)
        self.assertNotIn("create_texture",worker)
        self.assertNotIn("socket(",worker)

    def test_worker_drops_wrong_account_and_limits_buffer(self):
        worker=PROFILE[PROFILE.index("struct AvatarReadState {"):
                       PROFILE.index("} // namespace")]
        self.assertIn("state.wake.wait(lock,[&] {return state.pending;});",worker)
        self.assertIn("if(epoch!=state.generation || user!=state.selected_user)",worker)
        self.assertIn("state.completed_pixels=std::move(pixels)",worker)
        self.assertIn("std::thread([] {avatar_reader();}).detach();",worker)
        self.assertIn("if(state.pending || state.in_flight || state.completed)return;",worker)
        self.assertIn("state.completed_pixels.clear();",worker)

    def test_only_render_thread_uploads_and_accounts_match(self):
        poll=PROFILE[PROFILE.index("void niak_profile_poll_avatar("):
                     PROFILE.index("// Broker files may arrive AFTER startup.")]
        self.assertIn("current!=user",poll)
        self.assertLess(poll.index("current!=user"),poll.index("renderer.create_texture("))
        self.assertIn("pixels.size()!=std::size_t(w)*h*4u",poll)
        self.assertIn("renderer.destroy_texture(niak_user_avatar)",PROFILE)
        self.assertIn("niak_profile_poll_avatar",HEADER)
        self.assertIn("niak_profile_poll_avatar(renderer);",STAGE)

    def test_png_path_preparation_is_cpu_only(self):
        helper=ICON[ICON.index("bool niak_prepare_profile_png_file("):]
        self.assertIn("read_local_png(path,encoded)",helper)
        self.assertIn("decode_icon_thumbnail(encoded,pixels)",helper)
        self.assertNotIn("renderer.",helper)

if __name__=="__main__":
    unittest.main()
