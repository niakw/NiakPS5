import test from "node:test";
import assert from "node:assert/strict";
import {DEMO_GAMES,coverOf,heroOf,releasedGames,dailyFeature,normalizeLibrary,safeArtwork} from "../src/catalog.js";
test("releasedGames excludes future releases and keeps newest first",()=>{
  const games=[{released:"2027-01-01",id:"future"},{released:"2026-02-27",id:"a"},{released:"2025-10-01",id:"b"}];
  assert.deepEqual(releasedGames(games,new Date(2026,9,21)).map(g=>g.id),["a","b"]);
});
test("daily feature is deterministic and only uses released entries",()=>{
  const date=new Date(2026,9,21);
  const a=dailyFeature(DEMO_GAMES,date,true);
  assert.deepEqual(a,dailyFeature(DEMO_GAMES,date,true));
  assert.ok(a.released<="2026-10-21");
  assert.equal(dailyFeature(DEMO_GAMES,date,false).id,"pragmata");
});
test("library normalization rejects duplicate ids and unsafe remote artwork",()=>{
  const result=normalizeLibrary([{id:"good",title:"Jeu",installed:1,cover:"javascript:alert(1)",progress:999},{id:"good",title:"Duplicat"},{title:"Sans ID"}]);
  assert.equal(result.length,1);assert.equal(result[0].cover,"");assert.equal(result[0].progress,100);assert.equal(result[0].installed,true);
});
test("only allow explicit art hosts or same-origin assets",()=>{
  assert.equal(safeArtwork("https://evil.example/hero.jpg"),"");
  assert.equal(safeArtwork("https://cdn.cloudflare.steamstatic.com/steam/apps/3357650/library_hero.jpg").includes("3357650"),true);
  assert.equal(safeArtwork("/art/cover.webp"),"/art/cover.webp");
});
test("Steam IDs produce consistent card and hero assets",()=>{
  assert.ok(coverOf(DEMO_GAMES[0]).includes("library_capsule.jpg"));
  assert.ok(heroOf(DEMO_GAMES[0]).includes("library_hero.jpg"));
});

test("the daily game prefers releases within the last twelve months",()=>{
  const date=new Date(2026,9,21);
  for(let d=20;d<30;d++){
    const selected=dailyFeature(DEMO_GAMES,new Date(2026,9,d),true);
    assert.ok(selected.released>="2025-10-20");
  }
});

test("hashed publisher artwork works without opening arbitrary domains",()=>{
  assert.ok(DEMO_GAMES.every(g=>safeArtwork(g.cover)&&safeArtwork(g.hero)));
  assert.equal(safeArtwork("https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1/../../secret.jpg"),"");
});
