import {readFileSync,existsSync} from "node:fs";
import assert from "node:assert/strict";
const html=readFileSync("index.html","utf8");
const js=readFileSync("src/app.js","utf8");
const css=readFileSync("src/style.css","utf8");
const ids=[...js.matchAll(/\$\("([a-z][a-z0-9-]*)"\)/g)].map(x=>x[1]);
const notFound=[...new Set(ids)].filter(id=>!html.includes('id="'+id+'"'));
assert.deepEqual(notFound,[],"Missing expected DOM IDs");
for(const path of ["src/app.js","src/style.css","src/catalog.js","fonts/manrope.woff2","fonts/instrument-serif.woff2","fonts/OFL-Manrope.txt","fonts/OFL-InstrumentSerif.txt"]){
  assert.equal(existsSync(path),true,"Missing asset "+path);
}
assert.ok(css.includes("#91f5df"),"NiakTV mint accent missing");
assert.ok(html.includes('data-action="settings"'),"Settings not navigable");
console.log("NiakPS5 static UI assets: OK");
