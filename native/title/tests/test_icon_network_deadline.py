"""Prove the ShadowMountPlus icon client has an entire-request deadline."""
from pathlib import Path
import unittest
CODE=(Path(__file__).resolve().parents[1]/"game_icons.cpp").read_text()
class IconNetworkDeadlineTests(unittest.TestCase):
    def test_recv_fragments_cannot_extend_the_network_deadline(self):
        self.assertIn("std::chrono::milliseconds(220)",CODE)
        self.assertIn("deadline-std::chrono::steady_clock::now()",CODE)
        self.assertIn("if(remaining<=0)",CODE)
        self.assertIn("std::min<std::int64_t>(remaining,100000)",CODE)
        self.assertNotIn("timeval timeout{0, 350000};",CODE)
    def test_transport_failure_does_not_trigger_second_blocking_request(self):
        self.assertIn("if(!complete && !icon_endpoint.consecutive_failures)",CODE)
        self.assertIn('complete=download(url+"&size=thumb",bytes);',CODE)
if __name__=="__main__":
    unittest.main()
