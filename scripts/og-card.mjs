// The link preview: draws the 1200x630 card at docs/assets/brand/og-card.png, dark first.
// The words come from the built front page (its h1 and the line under it), so the card never says something the site doesn't.
// The headline's size steps down until the line under it clears the hazard band.
//
// Run, after `python scripts/build_site.py` (it reads docs/index.html), from anywhere:
//   node scripts/og-card.mjs
// Needs Node 22+ (global fetch and WebSocket) and Google Chrome. Set CHROME_PATH to use another Chrome or Chromium.
import { spawn } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const DOCS = fileURLToPath(new URL("../docs", import.meta.url));
const CHROME_DEFAULT = process.platform === "win32" ? "C:/Program Files/Google/Chrome/Application/chrome.exe"
  : process.platform === "darwin" ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" : "google-chrome";
const chrome = process.env.CHROME_PATH || CHROME_DEFAULT;
const front = readFileSync(join(DOCS, "index.html"), "utf8");
const h1 = [...front.match(/<h1 id="h">(.*?)<\/h1>/)[1].matchAll(/<span>(.*?)<\/span>/g)].map((m) => m[1]);
const sub = front.match(/<p class="sub">(.*?)<\/p>/)[1];
if (h1.length !== 2 || !sub) throw new Error("og-card: the front page's headline or promise moved");
const icon = "data:image/png;base64," + readFileSync(join(DOCS, "assets/brand/topping-out-icon-512.png")).toString("base64");

const html = `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@800;900&family=Martian+Mono:wght@700&family=Public+Sans:wght@500&display=block" rel="stylesheet">
<style>
html,body{margin:0;width:1200px;height:630px;overflow:hidden;background:#101316;color:#E7EAE5}
.c{position:relative;width:1200px;height:630px;box-sizing:border-box;padding:56px 72px 0}
.haz{position:absolute;left:0;right:0;bottom:0;height:26px;background:repeating-linear-gradient(-45deg,#101316 0 22px,#FBB401 22px 44px)}
.top{display:flex;align-items:center;gap:22px}
.top img{width:104px;height:104px}
.wm{font:900 56px/1 "Big Shoulders Display",sans-serif;text-transform:uppercase;letter-spacing:.01em}
.wm b{color:#FBB401}
h1{margin:34px 0 0;font:900 104px/.94 "Big Shoulders Display",sans-serif;text-transform:uppercase;letter-spacing:-.005em}
h1 span{display:block}h1 span+span{color:#FBB401}
p{margin:24px 0 0;max-width:1040px;font:500 26px/1.35 "Public Sans",sans-serif;color:#C9CEC8}
.url{position:absolute;right:72px;top:80px;font:700 22px/1 "Martian Mono",monospace;letter-spacing:.06em;color:#8A938D}
</style></head><body><div class="c">
<div class="top"><img src="${icon}" alt=""><div class="wm">Topping <b>Out</b></div></div>
<div class="url">toppingout.dev</div>
<h1><span>${h1[0]}</span><span>${h1[1]}</span></h1>
<p>${sub}</p>
<div class="haz"></div></div></body></html>`;

const port = 9400 + Math.floor(Math.random() * 90);
const proc = spawn(chrome, ["--headless=new", "--disable-gpu", `--remote-debugging-port=${port}`, "--user-data-dir=" + join(tmpdir(), "og-" + port), "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let t; for (let i = 0; i < 50 && !t; i++) { await sleep(200); try { t = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((x) => x.type === "page"); } catch {} }
if (!t) { proc.kill(); throw new Error(`og-card: Chrome did not start (${chrome}); set CHROME_PATH`); }
const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const wait = {}; ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && wait[m.id]) { wait[m.id](m); delete wait[m.id]; } });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; wait[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
await send("Emulation.setDeviceMetricsOverride", { width: 1200, height: 630, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: "data:text/html;base64," + Buffer.from(html).toString("base64") });
await sleep(1500);
await send("Runtime.evaluate", { expression: "document.fonts.ready", awaitPromise: true }); await sleep(400);
const fit = (await send("Runtime.evaluate", { returnByValue: true, expression:
  "(function(){var h=document.querySelector('h1'),p=document.querySelector('p'),s=104;while(p.getBoundingClientRect().bottom>590&&s>48){s-=4;h.style.fontSize=s+'px'}return p.getBoundingClientRect().bottom})()" })).result.result.value;
if (fit > 600) throw new Error("og-card: the promise runs into the hazard band (" + fit + ")");
const shot = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: 1200, height: 630, scale: 1 } });
writeFileSync(join(DOCS, "assets/brand/og-card.png"), Buffer.from(shot.result.data, "base64"));
console.log("wrote docs/assets/brand/og-card.png");
ws.close(); proc.kill(); process.exit(0);
