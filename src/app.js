// SPDX-License-Identifier: GPL-3.0-or-later
import {DEMO_GAMES,PALETTES,BACKGROUNDS,coverOf,heroOf,dailyFeature,normalizeLibrary} from "./catalog.js";
const $ = id => document.getElementById(id);
const state = {games:DEMO_GAMES.map(g=>({...g,installed:false})),realLibrary:false,selectedId:null,panel:null,previousFocus:null,sceneId:0,settings:readSettings()};
let toastHandle,sceneTimer,activeImage="b",frameButtonEdges=new Set(),lastGamepadMove=0;
function readSettings() {
  let parsed={};try{parsed=JSON.parse(localStorage.getItem("niakps5.settings") || "{}") || {}}catch{}
  return {palette:PALETTES.includes(parsed.palette)?parsed.palette:"mint",background:BACKGROUNDS.includes(parsed.background)?parsed.background:"game",daily:parsed.daily!==false,performance:parsed.performance===true};
}
function saveSettings() {try{localStorage.setItem("niakps5.settings",JSON.stringify(state.settings))}catch{} applySettings()}
function applySettings() {
  document.body.dataset.palette=state.settings.palette;document.body.dataset.background=state.settings.background;
  document.body.classList.toggle("performance",state.settings.performance);
  $("wallpaper-credit").textContent=state.settings.background==="game" ? "Fond · " + (currentGame()?.title || "Jeu du moment") + " · visuels Steam" : (state.settings.background==="solid"?"Fond uni":"Fond dégradé") + " · NiakPS5";
  if(state.settings.performance || state.settings.background!=="game"){$("scene-a").classList.remove("is-active");$("scene-b").classList.remove("is-active")}
  else updateScene(currentGame());
  document.querySelectorAll("[data-setting]").forEach(btn=>{
    const group=btn.dataset.setting,value=btn.dataset.value;
    btn.setAttribute("aria-pressed",String(group==="daily"||group==="performance" ? state.settings[group]=== (value==="true") : state.settings[group]===value));
  });
}
function currentGame() {return state.games.find(g=>g.id===state.selectedId) || dailyFeature(state.games,new Date(),state.settings.daily) || state.games[0] || null}
function el(name,cls,txt) {const node=document.createElement(name);if(cls)node.className=cls;if(txt!==undefined)node.textContent=txt;return node}
function icon(name) {
  const paths={
    game:'<path d="M10 9h12c4 0 6 5 6 11 0 6-4 5-8 0h-8c-4 5-8 6-8 0 0-6 2-11 6-11zM8 14h8M12 10v8M23 13h.01M20 17h.01"/>',
    back:'<path d="m19 12-7 7-7-7 7-7"/>'
  };
  const span=el("span");span.innerHTML='<svg viewBox="0 0 32 32" aria-hidden="true">'+(paths[name]||paths.game)+'</svg>';return span.firstElementChild;
}
function renderRail() {
  const rail=$("game-rail");rail.replaceChildren();
  if(!state.games.length){const p=el("p","drawer-note","Aucun jeu détecté. Le catalogue d'exemple est remplacé dès qu'une bibliothèque réelle est fournie.");rail.append(p);$("library-label").textContent="Bibliothèque vide";$("session-summary").textContent="Aucun jeu transmis par l'hôte console.";return}
  state.games.forEach(game=>{
    const card=el("button","game-card");card.type="button";card.dataset.action="select-game";card.dataset.id=game.id;card.dataset.navigate="";card.dataset.installed=String(Boolean(game.installed));
    card.setAttribute("aria-label",game.title+(game.installed?" · installé":" · aperçu"));
    const fb=el("div","card-fallback");fb.append(icon("game"));card.append(fb);
    const src=coverOf(game);
    if(src&&!state.settings.performance){const img=el("img","game-cover");img.src=src;img.alt="";img.loading="lazy";img.decoding="async";img.addEventListener("error",()=>img.classList.add("is-broken"));card.append(img)}
    const shade=el("div","game-card-shade");card.append(shade);
    const content=el("div","game-card-content");content.append(el("span","game-card-title",game.title),el("span","game-card-meta",game.installed?"INSTALLÉ · PS5":"PS5 · "+(game.year||"JEU")));card.append(content);
    card.addEventListener("focus",()=>showGame(game.id));
    card.addEventListener("mouseenter",()=>{if(!state.panel)showGame(game.id)});
    rail.append(card);
  });
  $("library-label").textContent=state.realLibrary ? state.games.length+" jeu(x) de votre bibliothèque" : "Sélection de démonstration · 2025–2026";
  $("session-summary").textContent=state.realLibrary?"Votre bibliothèque est connectée. Choisissez un jeu pour continuer.":"Une interface sans publicité, avec une bibliothèque de démonstration.";
}
function showGame(id) {
  if(id && !state.games.some(g=>g.id===id))return;
  state.selectedId=id||null;
  const game=currentGame();if(!game){$("feature-title").textContent="Votre bibliothèque vous attend.";$("feature-subtitle").textContent="Aucun jeu n'a encore été fourni par la console.";$("feature-tag").textContent="VOTRE ESPACE";$("feature-year").textContent="";$("feature-genre").textContent="Bibliothèque";$("feature-status").textContent="Aucun jeu";$("primary-label").textContent="Aucun jeu à lancer";$("feature-primary").disabled=true;return}
  $("feature-primary").disabled=false;
  $("feature-title").textContent=game.title;
  $("feature-subtitle").textContent=game.description || "Votre prochain jeu commence ici.";
  $("feature-tag").textContent=game.installed?"DANS MA BIBLIOTHÈQUE":"JEU DU MOMENT";
  $("feature-year").textContent=game.year || "";
  $("feature-genre").textContent=game.genre;
  $("feature-status").textContent=game.installed?"Installé":"À découvrir";
  $("primary-label").textContent=game.installed?"Lancer le jeu":"Découvrir le jeu";
  $("feature-primary").dataset.action=game.installed?"launch":"details";
  $("wallpaper-credit").textContent=state.settings.background==="game"?"Fond · "+game.title+" · visuels Steam":(state.settings.background==="solid"?"Fond uni":"Fond dégradé")+" · NiakPS5";
  clearTimeout(sceneTimer);sceneTimer=setTimeout(()=>updateScene(game),110);
}
function updateScene(game) {
  if(!game || state.settings.performance || state.settings.background!=="game")return;
  const src=heroOf(game);if(!src)return;
  const id=++state.sceneId;
  const target=$("scene-"+activeImage);
  if(target.dataset.source===src && target.classList.contains("is-active"))return;
  target.onload=()=>{if(id!==state.sceneId)return;const other=$("scene-"+(activeImage==="a"?"b":"a"));other.classList.remove("is-active");target.classList.add("is-active");activeImage=activeImage==="a"?"b":"a"};
  target.onerror=()=>{target.classList.remove("is-active");target.onload=null};
  target.dataset.source=src;target.src=src;
}
function clock() {
  const now=new Date();
  $("clock").textContent=now.toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"});
  $("date").textContent=now.toLocaleDateString("fr-FR",{weekday:"short",day:"numeric",month:"long"});
}
function toast(message) {clearTimeout(toastHandle);$("toast").textContent=message;$("toast").hidden=false;toastHandle=setTimeout(()=>{$("toast").hidden=true},3200)}
function callBridge(action,id) {
  const bridge=window.NiakPS5Bridge;
  if(!bridge || typeof bridge[action]!=="function"){toast("Fonction console indisponible dans l'aperçu web.");return}
  try {Promise.resolve(bridge[action](id)).catch(()=>toast("Action non disponible sur cette console."))}
  catch {toast("Action non disponible sur cette console.")}
}
function selectedGameDetails() {
  const game=currentGame();if(!game)return;
  openPanel("details",game);
}
function openPanel(kind,game) {
  if(!$("search-overlay").hidden)closeSearch();
  state.previousFocus=document.activeElement;
  state.panel=kind;
  $("panel-overlay").hidden=false;
  const content=$("drawer-content");content.replaceChildren();
  $("drawer-title").textContent=kind==="settings"?"Réglages":kind==="library"?"Bibliothèque":"Le jeu";
  if(kind==="settings"){
    content.append(el("p","drawer-note","Retrouvez la direction artistique de NiakTV, adaptée à la navigation sur PS5."));
    content.append(el("h3","drawer-group","Palette"));
    const palettes=el("div","choice-row");
    [["mint","Menthe"],["violet","Violet"],["blue","Bleu"],["graphite","Graphite"]].forEach(([v,label])=>palettes.append(settingButton("palette",v,label)));content.append(palettes);
    content.append(el("h3","drawer-group","Fond d'écran"));
    const backgrounds=el("div","choice-row");
    [["game","Jeux récents"],["gradient","Dégradé"],["solid","Uni"]].forEach(([v,label])=>backgrounds.append(settingButton("background",v,label)));content.append(backgrounds);
    content.append(el("h3","drawer-group","Expérience"));
    content.append(toggleButton("daily","Jeu différent chaque jour","Jeu du jour choisi parmi les sorties du catalogue."),toggleButton("performance","Mode performance","Désactiver les images et les transitions pour alléger l'interface."));
    content.append(el("h3","drawer-group","Console"));
    content.append(el("p","drawer-note","Cette version est un frontend web. Elle ne remplace pas l'accueil système PS5 et n'accède pas aux jeux, captures, amis ou notifications sans adaptateur natif."));
  } else if(kind==="library") {
    content.append(el("p","drawer-note",state.realLibrary?"Jeux transmis par la console.":"Sélection illustrative — aucun jeu installé n'est détecté."));
    if(!state.games.length)content.append(el("p","drawer-note","Votre bibliothèque est vide."));
    state.games.forEach(item=>{const entry=el("button","search-result",item.title);entry.type="button";entry.dataset.action="library-select";entry.dataset.id=item.id;entry.dataset.navigate="";entry.append(el("span","",item.installed?"INSTALLÉ":"APERÇU"));content.append(entry)});
  } else if(game) {
    const image=heroOf(game);if(image){const img=el("img","detail-art");img.alt="";img.src=image;img.addEventListener("error",()=>img.remove());content.append(img)}
    content.append(el("h3","detail-title",game.title),el("p","detail-meta",["PS5",game.genre,game.year||""].filter(Boolean).join(" · ")),el("p","drawer-note",game.description||""));
    content.append(el("h3","drawer-group",game.installed?"Dans votre bibliothèque":"Jeu à découvrir"));
    content.append(el("p","drawer-note",game.installed?"Si l'hôte PS5 expose launchGame, vous pourrez lancer ce titre.":"Ce jeu figure dans la sélection illustrative. Il n'est pas déclaré installé sur votre PS5."));
    const btn=el("button","choice",game.installed?"Lancer le jeu":"Fermer la fiche");btn.dataset.action=game.installed?"launch":"close";btn.dataset.navigate="";content.append(btn);
  }
  applySettings();
  requestAnimationFrame(()=>focusElement($("panel-overlay").querySelector("[data-navigate]")));
}
function settingButton(group,value,label) {const b=el("button","choice",label);b.type="button";b.dataset.action="setting";b.dataset.setting=group;b.dataset.value=value;b.dataset.navigate="";return b}
function toggleButton(group,label,note) {
  const block=el("div");const b=el("button","setting-line");b.type="button";b.dataset.action="toggle";b.dataset.setting=group;b.dataset.navigate="";
  b.append(el("span","",label),el("small","",state.settings[group]?"Activé":"Désactivé"));block.append(b,el("p","drawer-note",note));return block;
}
function closePanel() {state.panel=null;$("panel-overlay").hidden=true;focusElement(state.previousFocus)}
function openSearch() {if(state.panel)closePanel();state.previousFocus=document.activeElement;$("search-overlay").hidden=false;updateSearch("");requestAnimationFrame(()=>$("game-search").focus())}
function closeSearch() {$("search-overlay").hidden=true;$("game-search").value="";focusElement(state.previousFocus)}
function updateSearch(term) {
  const found=state.games.filter(g=>g.title.toLocaleLowerCase("fr").includes(term.toLocaleLowerCase("fr").trim())).slice(0,12);
  const results=$("search-results");results.replaceChildren();
  if(!found.length){results.append(el("p","drawer-note","Aucun jeu correspondant."));return}
  found.forEach(g=>{const b=el("button","search-result",g.title);b.dataset.action="search-result";b.dataset.id=g.id;b.dataset.navigate="";b.append(el("span","",g.installed?"INSTALLÉ":"APERÇU"));results.append(b)});
}
function focusElement(node) {
  if(!node || !node.isConnected)return;
  document.querySelectorAll(".is-focused").forEach(n=>n.classList.remove("is-focused"));
  node.classList.add("is-focused");node.focus({preventScroll:true});
  const rail=node.closest(".game-rail");if(rail){const a=node.getBoundingClientRect(),r=rail.getBoundingClientRect();if(a.left<r.left)rail.scrollLeft-=r.left-a.left+8;if(a.right>r.right)rail.scrollLeft+=a.right-r.right+8}
}
document.addEventListener("focusin",e=>{
  document.querySelectorAll(".is-focused").forEach(n=>n.classList.remove("is-focused"));
  if(e.target.matches("button"))e.target.classList.add("is-focused");
});
function navigables(){
  const root=state.panel?$("panel-overlay"):!$("search-overlay").hidden?$("search-overlay"):$("app-root")||document.querySelector(".shell");
  return [...root.querySelectorAll("[data-navigate]")].filter(n=>!n.disabled&&n.getClientRects().length>0);
}
function navigate(direction) {
  const items=navigables();let from=document.activeElement;if(!items.includes(from)){focusElement(items[0]);return}
  const a=from.getBoundingClientRect(),ax=a.left+a.width/2,ay=a.top+a.height/2;
  const matches=items.filter(b=>b!==from).map(b=>{
    const r=b.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,dx=x-ax,dy=y-ay;
    const primary=direction==="left"?-dx:direction==="right"?dx:direction==="up"?-dy:dy;
    const secondary=(direction==="left"||direction==="right")?Math.abs(dy):Math.abs(dx);
    return {b,primary,secondary,score:primary+secondary*2.5};
  }).filter(x=>x.primary>8).sort((a,b)=>a.score-b.score);
  if(matches.length)focusElement(matches[0].b);
}
function focusGame(id){const card=[...$("game-rail").querySelectorAll("[data-id]")].find(node=>node.dataset.id===id);if(card)focusElement(card)}
function firstGame() {const card=$("game-rail").querySelector("[data-navigate]");if(card)focusElement(card);else toast("Bibliothèque vide.")}
function activate(action,id,button) {
  if(action==="settings"){openPanel("settings");return}
  if(action==="close"){closePanel();return}
  if(action==="search"){openSearch();return}
  if(action==="search-close"){closeSearch();return}
  if(action==="search-result"){closeSearch();showGame(id);focusGame(id);return}
  if(action==="library-select"){closePanel();showGame(id);focusGame(id);return}
  if(action==="setting"&&button){state.settings[button.dataset.setting]=button.dataset.value;saveSettings();return}
  if(action==="toggle"&&button){const key=button.dataset.setting;state.settings[key]=!state.settings[key];button.querySelector("small").textContent=state.settings[key]?"Activé":"Désactivé";saveSettings();if(key==="performance")renderRail();if(key==="daily"){state.selectedId=null;showGame(null)}return}
  if(action==="select-game"){showGame(id);selectedGameDetails();return}
  if(action==="details"){selectedGameDetails();return}
  if(action==="launch"){const game=currentGame();if(game?.installed)callBridge("launchGame",game.id);else selectedGameDetails();return}
  if(action==="all-games"){openPanel("library");return}
  if(action==="library"){firstGame();return}
  if(action==="games"){focusElement(document.querySelector(".nav-tab.active"));return}
  if(action==="media"){toast("Section Multimédia en préparation.");return}
  if(["captures","downloads","friends","notifications","profile"].includes(action)){callBridge(action);return}
}
document.addEventListener("click",e=>{const btn=e.target.closest("button[data-action]");if(btn)activate(btn.dataset.action,btn.dataset.id,btn)});
$("game-search").addEventListener("input",e=>updateSearch(e.target.value));
document.addEventListener("keydown",event=>{
  const typing=event.target.matches("input");
  if(event.key==="Escape"||event.key==="Backspace"&&!typing){event.preventDefault();back();return}
  if(typing)return;
  if(["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(event.key)){event.preventDefault();navigate(event.key.replace("Arrow","").toLowerCase());return}
  if((event.key==="Enter"||event.key===" ")&&!event.repeat){event.preventDefault();const target=document.activeElement;if(target?.matches("button"))target.click();return}
  if(event.key.toLowerCase()==="t"){event.preventDefault();openPanel("settings")}
});
function back(){
  if(!$("search-overlay").hidden){closeSearch();return}
  if(state.panel){closePanel();return}
  focusElement($("feature-primary"));
}
function gamepadAction(name) {
  if(name==="up"||name==="down"||name==="left"||name==="right"){navigate(name);return}
  if(name==="accept"){const target=document.activeElement;if(target?.matches("button"))target.click();else if(target?.matches("input"))target.focus();return}
  if(name==="back"){back();return}
  if(name==="settings"){openPanel("settings");return}
  if(name==="library"){if(!state.panel)firstGame();return}
}
function pollGamepad(time){
  const pads=navigator.getGamepads?navigator.getGamepads():[];
  const pad=[...pads].find(Boolean);
  if(pad){
    const mapping={0:"accept",1:"back",2:"library",3:"settings",12:"up",13:"down",14:"left",15:"right"};
    const now=new Set();Object.entries(mapping).forEach(([index,name])=>{if(pad.buttons[index]?.pressed)now.add(name)});
    if(Math.abs(pad.axes[0]||0)>.6)now.add(pad.axes[0]<0?"left":"right");
    if(Math.abs(pad.axes[1]||0)>.6)now.add(pad.axes[1]<0?"up":"down");
    for(const name of now){if(!frameButtonEdges.has(name)||(["up","down","left","right"].includes(name)&&time-lastGamepadMove>220)){gamepadAction(name);lastGamepadMove=time}}
    frameButtonEdges=now;
  }else frameButtonEdges=new Set();
  requestAnimationFrame(pollGamepad);
}
window.NiakPS5=Object.freeze({
  // Inject installed games from a native, explicitly authorized PS5 host.
  setLibrary(games){state.games=normalizeLibrary(games);state.realLibrary=true;state.selectedId=null;renderRail();showGame(null);return state.games.length},
  resetDemo(){state.games=DEMO_GAMES.map(g=>({...g,installed:false}));state.realLibrary=false;state.selectedId=null;renderRail();showGame(null)},
  setPalette(value){if(PALETTES.includes(value)){state.settings.palette=value;saveSettings()}},
  refresh(){clock();showGame(state.selectedId)}
});
renderRail();clock();setInterval(clock,30000);applySettings();showGame(null);
requestAnimationFrame(()=>{focusElement($("feature-primary"));requestAnimationFrame(pollGamepad)});
