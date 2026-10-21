// SPDX-License-Identifier: GPL-3.0-or-later
// The example games are editorial demo entries, NOT an installed PS5 library.
export const DEMO_GAMES = Object.freeze([
  {id:"pragmata",title:"PRAGMATA",year:2026,released:"2026-04-16",genre:"Action · Science-fiction",description:"Une aventure lunaire où l'humain et l'androïde avancent ensemble face à une IA hostile.",steamId:3357650},
  {id:"requiem",title:"Resident Evil Requiem",year:2026,released:"2026-02-27",genre:"Survival horror · Action",description:"Un nouveau chapitre de l'horreur. Les secrets du passé remontent à la surface.",steamId:3764200},
  {id:"expedition33",title:"Clair Obscur: Expedition 33",year:2025,released:"2025-04-24",genre:"RPG · Aventure",description:"Une expédition au-delà de l'impossible, dans un univers inspiré de la Belle Époque.",steamId:1903340},
  {id:"doom",title:"DOOM: The Dark Ages",year:2025,released:"2025-05-14",genre:"Action · FPS",description:"Le Slayer revient dans une guerre médiévale spectaculaire contre l'Enfer.",steamId:3017860},
  {id:"kcd2",title:"Kingdom Come: Deliverance II",year:2025,released:"2025-02-04",genre:"RPG · Monde ouvert",description:"Une aventure médiévale au cœur d'un royaume vivant.",steamId:1771300},
  {id:"wilds",title:"Monster Hunter Wilds",year:2025,released:"2025-02-28",genre:"Action · Coopération",description:"Explorez les Terres interdites et découvrez un écosystème en constante évolution.",steamId:2246340}
]);
export const PALETTES = ["mint","violet","blue","graphite"];
export const BACKGROUNDS = ["game","gradient","solid"];
const SAFE_ART = /^(https:\/\/(?:cdn\.cloudflare\.steamstatic\.com|shared\.fastly\.steamstatic\.com)\/steam\/apps\/\d+\/[a-z0-9_.-]+\.(?:jpg|png|webp)|\/art\/[a-zA-Z0-9_.-]+\.(?:jpg|png|webp))$/;
export function safeArtwork(url) {
  return typeof url === "string" && SAFE_ART.test(url) ? url : "";
}
export function coverOf(game) {
  return safeArtwork(game.cover) || (Number.isSafeInteger(game.steamId) && game.steamId > 0 ? "https://cdn.cloudflare.steamstatic.com/steam/apps/" + game.steamId + "/library_600x900.jpg" : "");
}
export function heroOf(game) {
  return safeArtwork(game.hero) || (Number.isSafeInteger(game.steamId) && game.steamId > 0 ? "https://cdn.cloudflare.steamstatic.com/steam/apps/" + game.steamId + "/library_hero.jpg" : "");
}
export function releasedGames(games, date = new Date()) {
  const today = [date.getFullYear(), String(date.getMonth()+1).padStart(2,"0"), String(date.getDate()).padStart(2,"0")].join("-");
  return games.filter(g => /^\d{4}-\d\d-\d\d$/.test(g.released || "") && g.released <= today).slice().sort((a,b) => b.released.localeCompare(a.released));
}
export function dailyFeature(games, date = new Date(), daily = true) {
  const candidates = releasedGames(games,date);
  if (!candidates.length) return null;
  const cutoff = new Date(date.getFullYear()-1,date.getMonth(),date.getDate());
  const recent = releasedGames(candidates, date).filter(g => g.released >= [cutoff.getFullYear(),String(cutoff.getMonth()+1).padStart(2,"0"),String(cutoff.getDate()).padStart(2,"0")].join("-"));
  const eligible = recent.length ? recent : candidates;
  if (!daily) return eligible[0];
  const day = Math.floor(Date.UTC(date.getFullYear(),date.getMonth(),date.getDate())/86400000);
  return eligible[day % eligible.length];
}
export function normalizeLibrary(input) {
  if (!Array.isArray(input)) return [];
  const seen = new Set();
  return input.slice(0,150).filter(item => item && typeof item === "object").map(item => ({
    id: String(item.id || "").slice(0,100),
    title: String(item.title || "").slice(0,150),
    description: String(item.description || "").slice(0,280),
    genre: String(item.genre || "Jeu PS5").slice(0,90),
    year: Number.isInteger(item.year) && item.year > 1990 && item.year < 2100 ? item.year : null,
    released: /^\d{4}-\d{2}-\d{2}$/.test(item.released || "") ? item.released : "",
    steamId: Number.isSafeInteger(item.steamId) && item.steamId > 0 ? item.steamId : null,
    cover: safeArtwork(item.cover),
    hero: safeArtwork(item.hero),
    installed: Boolean(item.installed),
    progress: Number.isFinite(item.progress) ? Math.min(100,Math.max(0,item.progress)) : null
  })).filter(item => {
    if (!item.id || !item.title || seen.has(item.id)) return false;
    seen.add(item.id);return true;
  });
}