import importlib.util,io,tempfile,unittest
from pathlib import Path
from xml.etree import ElementTree as ET
MODULE=Path(__file__).parents[1]/"launchbox_index.py"
spec=importlib.util.spec_from_file_location("niak_index",MODULE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class TestRetailCases(unittest.TestCase):
 def test_language_platform_and_ambiguity(self):
  sources={("ps5","ea sports fc 27"):["PPSA34015"],
           ("ps4","ea sports fc 27"):["CUSA77777"]}
  xml=b'''<LaunchBox>
  <Game><DatabaseID>8</DatabaseID><Platform>Sony Playstation 5</Platform><Name>EA SPORTS FC 27</Name><Notes>Authentic &amp; real gameplay.</Notes></Game>
  <Game><DatabaseID>9</DatabaseID><Platform>Sony Playstation 4</Platform><Name>EA SPORTS FC 27</Name><Notes>PS4 edition</Notes></Game>
  <GameImage><DatabaseID>8</DatabaseID><Type>Box - Front</Type><Region>North America</Region><FileName>00000000-0000-0000-0000-000000000001.jpg</FileName></GameImage>
  <GameImage><DatabaseID>8</DatabaseID><Type>Box - Front</Type><Region>France</Region><FileName>00000000-0000-0000-0000-000000000002.jpg</FileName></GameImage>
  <GameImage><DatabaseID>8</DatabaseID><Type>Box - Back</Type><Region>Europe</Region><FileName>00000000-0000-0000-0000-000000000003.png</FileName></GameImage>
  <GameImage><DatabaseID>9</DatabaseID><Type>Box - Front</Type><Region>World</Region><FileName>00000000-0000-0000-0000-000000000004.jpg</FileName></GameImage>
  </LaunchBox>'''
  rows=mod.parse(io.BytesIO(xml),sources)
  self.assertEqual(len(rows),2)
  ps5=next(x for x in rows if x[0]=="PPSA34015")
  ps4=next(x for x in rows if x[0]=="CUSA77777")
  self.assertTrue(ps5[2].startswith("fr:00000000"))
  self.assertIn("Authentic & real",ps5[1])
  self.assertTrue(ps4[2].startswith("world:"))
  self.assertNotEqual(ps4[2],ps5[2])
  self.assertEqual(mod.normalize("EA SPORTS® FC 27"),"ea sports fc 27")
if __name__=="__main__":unittest.main()
