"""Guard the PS5 HTTP transport failover against regressions.

The device transports cannot run on the host. SDK compilation and hardware
validation are separate gates; these checks keep the routing policy explicit.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HttpFallbackPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = (ROOT / "daily_runtime.cpp").read_text(encoding="utf-8")
        cls.primary, cls.wrapper = cls.code.split(
            "// A sandboxed title can reject sceHttp TLS", 1
        )

    def test_primary_validates_exact_hosts_and_declines_redirects(self):
        self.assertIn("if(!feed&&!art&&!cases)", self.primary)
        self.assertIn('curl_easy_setopt(easy,CURLOPT_PROTOCOLS_STR,"https")', self.primary)
        self.assertIn("CURLOPT_SSL_VERIFYPEER,1L", self.primary)
        self.assertIn("CURLOPT_SSL_VERIFYHOST,2L", self.primary)
        self.assertIn("CURLOPT_FOLLOWLOCATION,0L", self.primary)
        self.assertIn("sceHttpSetAutoRedirect(tmpl,0)", self.primary)

    def test_fallback_only_for_transport_failures_of_same_selection(self):
        self.assertIn("bool get_system(", self.primary)
        self.assertRegex(self.wrapper,
            r"if\(!niak::payload_process_elevated && same_selection &&\s*"
            r"primary_failure<0 && primary_stage>=1 && primary_stage<=7\)")
        self.assertIn(
            "selection_epoch->load(std::memory_order_relaxed)==expected_epoch",
            self.wrapper)
        self.assertIn("return get_curl(url,limit,result,failure,stage,", self.wrapper)
        self.assertIn("if(failure)*failure=primary_failure;", self.wrapper)
        self.assertIn("if(stage)*stage=primary_stage;", self.wrapper)

    def test_no_unbounded_fallback_or_insecure_tls(self):
        self.assertNotIn("CURLOPT_SSL_VERIFYPEER,0L", self.code)
        self.assertNotIn("CURLOPT_SSL_VERIFYHOST,0L", self.code)
        self.assertIn("CURLOPT_TIMEOUT_MS,15000L", self.code)
        self.assertIn("CURLOPT_CONNECTTIMEOUT_MS,5000L", self.code)
        self.assertNotIn("CURLOPT_FOLLOWLOCATION,1L", self.code)


if __name__ == "__main__":
    unittest.main()
