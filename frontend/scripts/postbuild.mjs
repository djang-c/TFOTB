// Runs after `vite build`: puts a tiny script at the very top of the built page shell (dist/client/_shell.html).
// It runs before the app starts, so it still works when one of the app's own scripts is refused (a free host that is
// busy or waking up answers 429) and the app never boots. A failed script or stylesheet under /assets/ reloads the
// page once, after a short pause, and never twice within 20 seconds. Same rule as reloadOnce in src/lib/retry.ts.
import { readFileSync, writeFileSync } from "node:fs";

const SHELL = new URL("../dist/client/_shell.html", import.meta.url);
const SCRIPT = `<script>(function(){var K="tfotb.chunk-reload";window.addEventListener("error",function(e){var t=e.target;if(!t||!t.tagName)return;var u=t.src||t.href||"";if(u.indexOf("/assets/")<0)return;try{var l=+sessionStorage.getItem(K)||0;if(Date.now()-l<20000)return;sessionStorage.setItem(K,String(Date.now()))}catch(x){return}setTimeout(function(){location.reload()},1200)},true)})();</script>`;

const html = readFileSync(SHELL, "utf8");
if (html.includes("tfotb.chunk-reload")) process.exit(0);
const at = html.indexOf("<head>");
if (at < 0)
  throw new Error("postbuild: no <head> in _shell.html, so the reload script was not added");
writeFileSync(SHELL, html.slice(0, at + 6) + SCRIPT + html.slice(at + 6));
console.log("[postbuild] added the reload-on-failed-script guard to _shell.html");
