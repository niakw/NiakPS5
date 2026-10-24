import importlib.util,io,tempfile,unittest
from pathlib import Path
from xml.etree import ElementTree as ET
MODULE=Path(__file__).parents[1]/"launchbox_index.py"
spec=importlib.util.spec_from_file_location("niak_index",MODULE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class TestRetailCases(unittest.TestCase):
 def test_real_launchbox_overview_field_is_preferred(self):
  xml=b'''<LaunchBox>
    <Game><DatabaseID>427261</DatabaseID>
      <Platform>Sony Playstation 5</Platform>
      <Name>A Plague Tale: Innocence</Name>
      <Overview>Follow two siblings. Escape danger. Protect each other. Fourth is removed.</Overview>
      <Notes>Incorrect application-only field.</Notes>
    </Game>
    <GameImage><DatabaseID>427261</DatabaseID><Type>Box - Front</Type>
      <FileName>742c24d1-1bee-4baf-8ca7-70b28613cefc.png</FileName>
    </GameImage>
  </LaunchBox>'''
  rows=mod.parse(io.BytesIO(xml),{("ps5","a plague tale innocence"):["PPSA02387"]})
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0][1],"Follow two siblings. Escape danger. Protect each other.")
  self.assertNotIn("Incorrect",rows[0][1])


 def test_overview_keeps_only_three_source_sentences(self):
  original="One. Two! Three? Four. Five."
  self.assertEqual(mod.clean_overview(original),"One. Two! Three?")
  self.assertLessEqual(len(mod.clean_overview("Sentence. "*200)),360)

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

 def test_console_edition_matches_base_when_no_exact_front(self):
  source={( "ps5","anno 1800") :["PPSA00001"],
          ( "ps5","anno 1800 console edition"):["PPSA00002"]}
  xml=b'''<LaunchBox>
  <Game><DatabaseID>21</DatabaseID><Platform>Sony Playstation 5</Platform>
    <Name>Anno 1800 Console Edition</Name></Game>
  <Game><DatabaseID>22</DatabaseID><Platform>Sony Playstation 5</Platform>
    <Name>Anno 1800</Name></Game>
  <GameImage><DatabaseID>21</DatabaseID><Type>Box - Front</Type>
    <Region>Europe</Region><FileName>00000000-0000-0000-0000-000000000021.jpg</FileName></GameImage>
  </LaunchBox>'''
  rows=mod.parse(io.BytesIO(xml),source)
  self.assertEqual(len(rows),2)
  self.assertTrue(all(row[2].startswith("eu:") for row in rows))
  self.assertEqual(mod.safe_titles("EA SPORTS FC 27"),("ea sports fc 27",))
  self.assertEqual(mod.safe_titles("Anno 1800 Console Edition"),
                   ("anno 1800 console edition","anno 1800"))
  self.assertEqual(mod.safe_titles("Elden Ring Deluxe Edition"),
                   ("elden ring deluxe edition",))

 def test_console_edition_installed_matches_plain_title_cover(self):
  sources={("ps5","anno 1800 console edition"):["PPSA04716"]}
  xml=b'''<LaunchBox>
   <Game><DatabaseID>22</DatabaseID><Platform>Sony Playstation 5</Platform>
     <Name>Anno 1800</Name></Game>
   <GameImage><DatabaseID>22</DatabaseID><Type>Box - Front</Type>
     <Region>Europe</Region><FileName>00000000-0000-0000-0000-000000000022.png</FileName></GameImage>
  </LaunchBox>'''
  result=mod.parse(io.BytesIO(xml),sources)
  self.assertEqual(len(result),1)
  self.assertEqual(result[0][0],"PPSA04716")
  self.assertTrue(result[0][2].startswith("eu:"))

 def test_images_and_alternate_names_can_precede_game_records(self):
  target={("ps5","le titre local"):["PPSA34567"]}
  xml=b'''<LaunchBox>
    <GameImage><DatabaseID>51</DatabaseID><Type>Box - Back</Type>
      <Region>Europe</Region><FileName>00000000-0000-0000-0000-000000000051.jpg</FileName>
    </GameImage>
    <GameAlternateName><DatabaseID>51</DatabaseID>
      <AlternateName>Le Titre Local</AlternateName></GameAlternateName>
    <GameImage><DatabaseID>51</DatabaseID><Type>Box - Front</Type>
      <Region>France</Region><FileName>00000000-0000-0000-0000-000000000052.png</FileName>
    </GameImage>
    <Game><DatabaseID>51</DatabaseID><Platform>Sony Playstation 5</Platform>
      <Name>Original International Title</Name></Game>
    <Game><DatabaseID>52</DatabaseID><Platform>Sony Playstation 4</Platform>
      <Name>Le Titre Local</Name></Game>
    <GameImage><DatabaseID>52</DatabaseID><Type>Box - Front</Type>
      <FileName>00000000-0000-0000-0000-000000000053.png</FileName></GameImage>
  </LaunchBox>'''
  rows=mod.parse(io.BytesIO(xml),target)
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0][0],"PPSA34567")
  self.assertTrue(rows[0][2].startswith("fr:00000000"))
  self.assertTrue(rows[0][3].startswith("eu:00000000"))
  self.assertEqual(rows[0][4],"-")
  self.assertEqual(rows[0][-1],"51")

 def test_back_uses_fanart_plus_gameplay_and_game_title_separately(self):
  installed={("ps5","sample game"):["PPSA12345"]}
  xml=b"""<LaunchBox>
   <Game><DatabaseID>100</DatabaseID><Platform>Sony Playstation 5</Platform>
   <Name>Sample Game</Name></Game>
   <GameImage><DatabaseID>100</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000001.jpg</FileName></GameImage>
   <GameImage><DatabaseID>100</DatabaseID><Type>Fanart - Background</Type>
    <FileName>00000000-0000-0000-0000-000000000002.jpg</FileName></GameImage>
   <GameImage><DatabaseID>100</DatabaseID><Type>Screenshot - Gameplay</Type>
    <FileName>00000000-0000-0000-0000-000000000003.jpg</FileName></GameImage>
   <GameImage><DatabaseID>100</DatabaseID><Type>Screenshot - Gameplay</Type>
    <FileName>00000000-0000-0000-0000-000000000004.jpg</FileName></GameImage>
   <GameImage><DatabaseID>100</DatabaseID><Type>Screenshot - Game Title</Type>
    <FileName>00000000-0000-0000-0000-000000000005.jpg</FileName></GameImage>
   </LaunchBox>"""
  stats={}
  row=mod.parse(io.BytesIO(xml),installed,stats)[0]
  self.assertEqual(stats["hero"],1)
  self.assertEqual(stats["gameplay"],2)
  self.assertEqual(stats["game_title"],1)
  self.assertIn("000000000002",row[6])  # Fanart is not discarded
  self.assertIn("000000000003",row[7])  # Gameplay
  self.assertIn("000000000005",row[8])  # Title screen, not second gameplay
  self.assertNotIn("000000000004",row[8])
  self.assertEqual(len({row[6],row[7],row[8]}),3)

 def test_fanart_and_two_distinct_gameplay_screenshots(self):
  identifiers={("ps5","the forest"):["PPSA55667"]}
  xml=b'''<LaunchBox>
  <Game><DatabaseID>600</DatabaseID><Platform>Sony Playstation 5</Platform>
    <Name>The Forest</Name><Notes>Explore.</Notes></Game>
  <GameImage><DatabaseID>600</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000001.png</FileName></GameImage>
  <GameImage><DatabaseID>600</DatabaseID><Type>Fanart - Background</Type>
    <FileName>00000000-0000-0000-0000-000000000002.png</FileName></GameImage>
  <GameImage><DatabaseID>600</DatabaseID><Type>Screenshot - Gameplay</Type>
    <FileName>00000000-0000-0000-0000-000000000002.png</FileName></GameImage>
  <GameImage><DatabaseID>600</DatabaseID><Type>Screenshot - Gameplay</Type>
    <FileName>00000000-0000-0000-0000-000000000003.png</FileName></GameImage>
  <GameImage><DatabaseID>600</DatabaseID><Type>Screenshot - Game Title</Type>
    <FileName>00000000-0000-0000-0000-000000000004.png</FileName></GameImage>
  </LaunchBox>'''
  rows=mod.parse(io.BytesIO(xml),identifiers)
  self.assertEqual(len(rows),1)
  self.assertEqual(len(rows[0]),10)
  self.assertIn("000000000002",rows[0][6])
  self.assertIn("000000000003",rows[0][7])
  self.assertIn("000000000004",rows[0][8])
  self.assertNotIn("000000000002",rows[0][7]+rows[0][8])
  self.assertEqual(rows[0][-1],"600")

 def test_fanart_box_front_is_a_valid_console_edition_fallback(self):
  entries={("ps5","anno 1800 console edition"):["PPSA04716"]}
  xml=b'''<LaunchBox>
   <Game><DatabaseID>440530</DatabaseID><Platform>Sony Playstation 5</Platform>
     <Name>Anno 1800 Console Edition</Name></Game>
   <GameImage><DatabaseID>440530</DatabaseID><Type>Fanart - Box - Front</Type>
     <FileName>00000000-0000-0000-0000-000000440530.png</FileName></GameImage>
   </LaunchBox>'''
  result=mod.parse(io.BytesIO(xml),entries)
  self.assertEqual(len(result),1)
  self.assertIn("440530",result[0][2])

 def test_ps5_front_ps4_back_and_pc_fanart_without_repeating_images(self):
  entries={("ps5","a plague tale innocence"):["PPSA02387"],
           ("ps5","anno 1800 console edition"):["PPSA04716"]}
  xml=b'''<LaunchBox>
  <Game><DatabaseID>427261</DatabaseID><Platform>Sony Playstation 5</Platform>
    <Name>A Plague Tale: Innocence</Name><Notes>PS5 synopsis.</Notes></Game>
  <Game><DatabaseID>123435</DatabaseID><Platform>Sony Playstation 4</Platform>
    <Name>A Plague Tale: Innocence</Name></Game>
  <Game><DatabaseID>440530</DatabaseID><Platform>Sony Playstation 5</Platform>
    <Name>Anno 1800 Console Edition</Name></Game>
  <Game><DatabaseID>115148</DatabaseID><Platform>Windows</Platform>
    <Name>Anno 1800</Name><Notes>PC description.</Notes></Game>
  <GameImage><DatabaseID>427261</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000427261.jpg</FileName></GameImage>
  <GameImage><DatabaseID>123435</DatabaseID><Type>Box - Back</Type>
    <FileName>00000000-0000-0000-0000-000000123435.jpg</FileName></GameImage>
  <GameImage><DatabaseID>440530</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000440530.jpg</FileName></GameImage>
  <GameImage><DatabaseID>115148</DatabaseID><Type>Fanart - Background</Type>
    <FileName>00000000-0000-0000-0000-000000115148.jpg</FileName></GameImage>
  <GameImage><DatabaseID>115148</DatabaseID><Type>Screenshot - Gameplay</Type>
    <FileName>00000000-0000-0000-0000-000000115149.jpg</FileName></GameImage>
  </LaunchBox>'''
  rows=mod.parse(io.BytesIO(xml),entries)
  innocence=next(row for row in rows if row[0]=="PPSA02387")
  anno=next(row for row in rows if row[0]=="PPSA04716")
  self.assertIn("427261",innocence[2])
  self.assertIn("123435",innocence[3])
  self.assertIn("440530",anno[2])
  self.assertIn("115148",anno[6])
  self.assertIn("115149",anno[7])
  self.assertEqual(anno[8],"-")
  self.assertIn("PC description",anno[1])

 def test_pc_only_scenery_without_pc_retail_front_on_ps4_and_ps5(self):
  xml=b"""<LaunchBox>
   <Game><DatabaseID>501</DatabaseID><Platform>Windows</Platform>
    <Name>The Adventure</Name><Overview>PC game description.</Overview></Game>
   <GameImage><DatabaseID>501</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000501.jpg</FileName></GameImage>
   <GameImage><DatabaseID>501</DatabaseID><Type>Box - Back</Type>
    <FileName>00000000-0000-0000-0000-000000000502.jpg</FileName></GameImage>
   <GameImage><DatabaseID>501</DatabaseID><Type>Fanart - Background</Type>
    <FileName>00000000-0000-0000-0000-000000000503.jpg</FileName></GameImage>
   <GameImage><DatabaseID>501</DatabaseID><Type>Screenshot - Gameplay</Type>
    <FileName>00000000-0000-0000-0000-000000000504.jpg</FileName></GameImage>
   <GameImage><DatabaseID>501</DatabaseID><Type>Screenshot - Game Title</Type>
    <FileName>00000000-0000-0000-0000-000000000505.jpg</FileName></GameImage>
  </LaunchBox>"""
  for platform,title in (("ps4","CUSA54321"),("ps5","PPSA54321")):
   with self.subTest(platform=platform):
    rows=mod.parse(io.BytesIO(xml),{(platform,"the adventure"):[title]})
    self.assertEqual(len(rows),1)
    row=rows[0]
    self.assertEqual(row[0],title)
    self.assertEqual(row[1],"PC game description.")
    self.assertEqual(row[2:5],("-","-","-"))  # never Windows retail scans
    self.assertIn("000000000503",row[6])
    self.assertIn("000000000504",row[7])
    self.assertIn("000000000505",row[8])

 def test_console_box_front_wins_over_both_pc_box_and_fanart_box(self):
  xml=b"""<LaunchBox>
   <Game><DatabaseID>600</DatabaseID><Platform>Sony Playstation 5</Platform>
    <Name>Example Title</Name></Game>
   <Game><DatabaseID>601</DatabaseID><Platform>Windows</Platform>
    <Name>Example Title</Name></Game>
   <GameImage><DatabaseID>600</DatabaseID><Type>Fanart - Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000600.jpg</FileName></GameImage>
   <GameImage><DatabaseID>600</DatabaseID><Type>Box - Front</Type>
    <Region>France</Region>
    <FileName>00000000-0000-0000-0000-000000000602.jpg</FileName></GameImage>
   <GameImage><DatabaseID>601</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000601.jpg</FileName></GameImage>
   <GameImage><DatabaseID>601</DatabaseID><Type>Fanart - Background</Type>
    <FileName>00000000-0000-0000-0000-000000000603.jpg</FileName></GameImage>
   <GameImage><DatabaseID>601</DatabaseID><Type>Screenshot - Gameplay</Type>
    <FileName>00000000-0000-0000-0000-000000000604.jpg</FileName></GameImage>
  </LaunchBox>"""
  row=mod.parse(io.BytesIO(xml),{("ps5","example title"):["PPSA45678"]})[0]
  self.assertIn("000000000602",row[2])  # genuine Sony Box - Front
  self.assertNotIn("000000000600",row[2])
  self.assertNotIn("000000000601",row[2])
  self.assertIn("000000000603",row[6])  # PC fanart fills scenery
  self.assertIn("000000000604",row[7])  # PC gameplay fills screenshot

 def test_console_to_pc_fanart_failover_priority(self):
  xml=b"""<LaunchBox>
   <Game><DatabaseID>600</DatabaseID><Platform>Sony Playstation 5</Platform>
    <Name>Example Title</Name></Game>
   <Game><DatabaseID>602</DatabaseID><Platform>Sony Playstation 4</Platform>
    <Name>Example Title</Name></Game>
   <Game><DatabaseID>601</DatabaseID><Platform>Windows</Platform>
    <Name>Example Title</Name></Game>
   <GameImage><DatabaseID>600</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000600.jpg</FileName></GameImage>
   <GameImage><DatabaseID>600</DatabaseID><Type>Fanart - Background</Type>
    <FileName>00000000-0000-0000-0000-000000000603.jpg</FileName></GameImage>
   <GameImage><DatabaseID>602</DatabaseID><Type>Fanart - Background</Type>
    <FileName>00000000-0000-0000-0000-000000000604.jpg</FileName></GameImage>
   <GameImage><DatabaseID>601</DatabaseID><Type>Fanart - Background</Type>
    <FileName>00000000-0000-0000-0000-000000000605.jpg</FileName></GameImage>
   <GameImage><DatabaseID>601</DatabaseID><Type>Screenshot - Game Title</Type>
    <FileName>00000000-0000-0000-0000-000000000606.jpg</FileName></GameImage>
  </LaunchBox>"""
  row=mod.parse(io.BytesIO(xml),{("ps5","example title"):["PPSA45678"]})[0]
  self.assertEqual([x.split(":")[1].split(".")[0][-3:] for x in row[6].split(";")][:3],
                   ["603","604","605"])
  self.assertIn("000000000600",row[2])
  self.assertIn("000000000606",row[7])  # PC title shot if gameplay missing

 def test_missing_console_capture_can_retry_matching_pc_capture(self):
  xml=b"""<LaunchBox>
   <Game><DatabaseID>600</DatabaseID><Platform>Sony Playstation 5</Platform>
    <Name>Example Title</Name></Game>
   <Game><DatabaseID>601</DatabaseID><Platform>Windows</Platform>
    <Name>Example Title</Name></Game>
   <GameImage><DatabaseID>600</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000600.jpg</FileName></GameImage>
   <GameImage><DatabaseID>600</DatabaseID><Type>Screenshot - Gameplay</Type>
    <FileName>00000000-0000-0000-0000-000000000610.jpg</FileName></GameImage>
   <GameImage><DatabaseID>600</DatabaseID><Type>Screenshot - Game Title</Type>
    <FileName>00000000-0000-0000-0000-000000000620.jpg</FileName></GameImage>
   <GameImage><DatabaseID>601</DatabaseID><Type>Screenshot - Gameplay</Type>
    <FileName>00000000-0000-0000-0000-000000000611.jpg</FileName></GameImage>
   <GameImage><DatabaseID>601</DatabaseID><Type>Screenshot - Game Title</Type>
    <FileName>00000000-0000-0000-0000-000000000621.jpg</FileName></GameImage>
  </LaunchBox>"""
  row=mod.parse(io.BytesIO(xml),{("ps5","example title"):["PPSA45678"]})[0]
  self.assertEqual([x.split(":",1)[1][-7:] for x in row[7].split(";")][:2],
                   ["610.jpg","611.jpg"])
  self.assertEqual([x.split(":",1)[1][-7:] for x in row[8].split(";")][:2],
                   ["620.jpg","621.jpg"])
  self.assertEqual(len(set(row[7].split(";")) & set(row[8].split(";"))),0)
  self.assertIn("000000000600",row[2])

 def test_box_back_ps5_then_ps4_then_pc_and_front_stays_ps5(self):
  xml=b"""<LaunchBox>
   <Game><DatabaseID>810</DatabaseID><Platform>Sony Playstation 5</Platform><Name>Priority Game</Name></Game>
   <Game><DatabaseID>811</DatabaseID><Platform>Sony Playstation 4</Platform><Name>Priority Game</Name></Game>
   <Game><DatabaseID>812</DatabaseID><Platform>Windows</Platform><Name>Priority Game</Name></Game>
   <GameImage><DatabaseID>810</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000810.jpg</FileName></GameImage>
   <GameImage><DatabaseID>811</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000811.jpg</FileName></GameImage>
   <GameImage><DatabaseID>812</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000812.jpg</FileName></GameImage>
   <GameImage><DatabaseID>810</DatabaseID><Type>Box - Back</Type>
    <FileName>00000000-0000-0000-0000-000000000820.jpg</FileName></GameImage>
   <GameImage><DatabaseID>811</DatabaseID><Type>Box - Back</Type>
    <FileName>00000000-0000-0000-0000-000000000821.jpg</FileName></GameImage>
   <GameImage><DatabaseID>812</DatabaseID><Type>Box - Back</Type>
    <FileName>00000000-0000-0000-0000-000000000822.jpg</FileName></GameImage>
  </LaunchBox>"""
  rows=mod.parse(io.BytesIO(xml),{("ps5","priority game"):["PPSA12345"],
                                    ("ps4","priority game"):["CUSA12345"]})
  for row in rows:
   self.assertEqual([x.split(":")[1][-7:] for x in row[3].split(";")][:3],
                    ["820.jpg","821.jpg","822.jpg"])
  ps5=next(row for row in rows if row[0]=="PPSA12345")
  ps4=next(row for row in rows if row[0]=="CUSA12345")
  self.assertIn("000000000810",ps5[2])
  self.assertNotIn("000000000812",ps5[2])
  self.assertIn("000000000811",ps4[2])
  self.assertNotIn("000000000812",ps4[2])

 def test_box_back_pc_last_resort_even_without_console_entry(self):
  xml=b"""<LaunchBox>
   <Game><DatabaseID>812</DatabaseID><Platform>Windows</Platform><Name>Priority Game</Name></Game>
   <GameImage><DatabaseID>812</DatabaseID><Type>Box - Back</Type>
    <FileName>00000000-0000-0000-0000-000000000822.jpg</FileName></GameImage>
   <GameImage><DatabaseID>812</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000812.jpg</FileName></GameImage>
  </LaunchBox>"""
  row=mod.parse(io.BytesIO(xml),{("ps5","priority game"):["PPSA12345"]})[0]
  self.assertEqual(row[2],"-")
  self.assertEqual(row[3],"other:00000000-0000-0000-0000-000000000822.jpg")
  self.assertEqual(row[4],"-")

 def test_box_back_pc_last_when_ps5_and_ps4_missing(self):
  xml=b"""<LaunchBox>
   <Game><DatabaseID>810</DatabaseID><Platform>Sony Playstation 5</Platform><Name>Priority Game</Name></Game>
   <Game><DatabaseID>811</DatabaseID><Platform>Sony Playstation 4</Platform><Name>Priority Game</Name></Game>
   <Game><DatabaseID>812</DatabaseID><Platform>Windows</Platform><Name>Priority Game</Name></Game>
   <GameImage><DatabaseID>810</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000810.jpg</FileName></GameImage>
   <GameImage><DatabaseID>812</DatabaseID><Type>Box - Back</Type>
    <FileName>00000000-0000-0000-0000-000000000822.jpg</FileName></GameImage>
  </LaunchBox>"""
  row=mod.parse(io.BytesIO(xml),{("ps5","priority game"):["PPSA12345"]})[0]
  self.assertIn("000000000810",row[2])
  self.assertIn("000000000822",row[3])
  self.assertNotIn("000000000822",row[2])

 def test_ambiguous_pc_name_cannot_supply_console_art(self):
  xml=b"""<LaunchBox>
   <Game><DatabaseID>601</DatabaseID><Platform>Windows</Platform>
    <Name>Example Title</Name></Game>
   <Game><DatabaseID>602</DatabaseID><Platform>Windows</Platform>
    <Name>Example Title</Name></Game>
   <GameImage><DatabaseID>601</DatabaseID><Type>Fanart - Background</Type>
    <FileName>00000000-0000-0000-0000-000000000601.jpg</FileName></GameImage>
  </LaunchBox>"""
  self.assertEqual(mod.parse(io.BytesIO(xml),
                    {("ps5","example title"):["PPSA45678"]}),[])

 def test_ambiguous_edition_is_never_assigned_at_random(self):
  source={("ps5","my game"):["PPSA00003"]}
  xml=b'''<LaunchBox>
  <Game><DatabaseID>30</DatabaseID><Platform>Sony Playstation 5</Platform>
    <Name>My Game Console Edition</Name></Game>
  <Game><DatabaseID>31</DatabaseID><Platform>Sony Playstation 5</Platform>
    <Name>My Game PS5 Edition</Name></Game>
  <GameImage><DatabaseID>30</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000030.png</FileName></GameImage>
  <GameImage><DatabaseID>31</DatabaseID><Type>Box - Front</Type>
    <FileName>00000000-0000-0000-0000-000000000031.png</FileName></GameImage>
  </LaunchBox>'''
  self.assertEqual(mod.parse(io.BytesIO(xml),source),[])
if __name__=="__main__":unittest.main()
