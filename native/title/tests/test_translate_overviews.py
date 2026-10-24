"""FR descriptions: never invent translation, send only public text, keep source."""
import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"translate_overviews.py"
spec=importlib.util.spec_from_file_location("niak_translate",SCRIPT)
translation=importlib.util.module_from_spec(spec);spec.loader.exec_module(translation)

class TranslationTests(unittest.TestCase):
    def test_no_key_keeps_untranslated_launchbox_text(self):
        source=b"PPSA02387\tA richly imagined historical adventure.\tfront\n"
        self.assertIsNone(translation.translation_file(
            source,{"PPSA02387"},key=""))
        self.assertEqual(len(translation.eligible_rows(source,{"PPSA02387"})),1)

    def test_private_deepl_translation_does_not_submit_title_id(self):
        source=(b"PPSA02387\tA compelling story about two siblings.\tart\n"
                b"CUSA12345\tA missing game.\tart\n")
        queries=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,size):
                return json.dumps({"translations":[{"text":"Une histoire de famille."}]}).encode()
        def fetch(req,timeout):
            payload=json.loads(req.data)
            self.assertEqual(req.full_url,"https://api-free.deepl.com/v2/translate")
            self.assertEqual(payload["target_lang"],"FR")
            self.assertEqual(payload["text"],["A compelling story about two siblings."])
            self.assertNotIn("PPSA02387",str(payload))
            queries.append(req)
            return Response()
        output=translation.translation_file(
            source,{"PPSA02387"},key="secret:fx",fetch=fetch)
        self.assertIn(b"PPSA02387\t",output)
        self.assertIn("Une histoire de famille.".encode(),output)
        self.assertNotIn(b"secret",output)
        self.assertNotIn(b"CUSA12345",output)
        self.assertEqual(len(queries),1)

if __name__=="__main__":
    unittest.main()
