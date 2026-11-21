// The front page's "See it" cards: screenshot each sheet to docs/assets/see/<name>-<light|dark>.webp.
// Each is a tall crop of the sheet's best part (560 x 900 CSS px at 1.5x), so the card can pan down it on hover.
// It also records each page's sha1 in docs/assets/see/sources.json; scripts/build_site.py compares those hashes
// and warns "previews taken before their pages last changed" when a sheet changed after its shot.
//
// Run, after `python scripts/build_site.py`, from anywhere:
//   node scripts/previews.mjs [name ...]      (no names: every sheet; names are the first column of SHOTS)
// Needs Node 22+ (global fetch and WebSocket) and Google Chrome. Set CHROME_PATH to use another Chrome or Chromium.
// Then run the build again: the warning should be gone.
import { spawn } from "node:child_process";
import { writeFileSync, readFileSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const D = fileURLToPath(new URL("../docs/", import.meta.url));
const CHROME_DEFAULT = process.platform === "win32" ? "C:/Program Files/Google/Chrome/Application/chrome.exe"
  : process.platform === "darwin" ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" : "google-chrome";
const chrome = process.env.CHROME_PATH || CHROME_DEFAULT;
// [name, page, clip x, clip y, js to run first, crop height (default H)]
const SHOTS = [
  ["route", "route.html", 286, 14, ""],
  ["repo", "repo.html", 286, 14, ""],
  ["logbook", "logbook.html", 286, 14, ""],
  ["skills", "skills.html", 286, 14, ""],
  ["atlas", "raw/atlas.html", 0, 0, "", 740],
  ["playbooks", "playbooks.html", 286, 14, ""],
  ["board", "raw/board.html", 16, 0, ""],
  ["requirements", "requirements.html", 300, 20,
   "['Claude Code','Git','Node'].forEach(function(k){var b=document.querySelector('.kit[data-k=\"'+k+'\"] button');b&&b.click()})"],
  ["cloud", "cloud.html", 286, 14, ""],
];
const W = 560, H = 900, SCALE = 1.5;
const only = process.argv.slice(2);
for (const n of only) if (!SHOTS.some(([name]) => name === n)) throw new Error("previews: no sheet called " + n);
const port = 9600 + Math.floor(Math.random() * 90);
const proc = spawn(chrome, ["--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--hide-scrollbars", `--remote-debugging-port=${port}`, "--user-data-dir=" + join(tmpdir(), "prev-" + port), "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let target; for (let i = 0; i < 50 && !target; i++) { await sleep(200); try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page"); } catch {} }
if (!target) { proc.kill(); throw new Error(`previews: Chrome did not start (${chrome}); set CHROME_PATH`); }
const ws = new WebSocket(target.webSocketDebuggerUrl); await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const wait = {}; ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && wait[m.id]) { wait[m.id](m); delete wait[m.id]; } });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; wait[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
for (const theme of ["light", "dark"]) for (const [name, page, x, y, pre, h] of SHOTS) {
  if (only.length && !only.includes(name)) continue;
  await send("Emulation.setDeviceMetricsOverride", { width: 1400, height: 1100, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url: pathToFileURL(D + page).href }); await sleep(2200);
  await send("Runtime.evaluate", { expression: `try{localStorage.setItem("foreman-theme","${theme}");localStorage.setItem("to-welcome","1")}catch(e){};var wl=document.querySelector(".welcome");wl&&wl.remove();document.documentElement.setAttribute("data-theme","${theme}");${pre}` });
  await sleep(900);
  const r = await send("Page.captureScreenshot", { format: "webp", quality: 70, captureBeyondViewport: true, clip: { x, y, width: W, height: h || H, scale: SCALE } });
  writeFileSync(D + `assets/see/${name}-${theme}.webp`, Buffer.from(r.result.data, "base64"));
  console.log(name, theme);
}
// record each page's hash, keeping the ones not re-shot this run
const manPath = D + "assets/see/sources.json";
const man = existsSync(manPath) ? JSON.parse(readFileSync(manPath, "utf8")) : {};
for (const [name, page] of SHOTS) if (!only.length || only.includes(name)) man[page] = createHash("sha1").update(readFileSync(D + page)).digest("hex");
writeFileSync(manPath, JSON.stringify(man, null, 1) + "\n");
ws.close(); proc.kill();
