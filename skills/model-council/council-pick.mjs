#!/usr/bin/env node
/**
 * One-shot council picker. Serves the chamber HTML, accepts one POST /pick,
 * writes council-pick.json, exits. Nothing stays running.
 *
 *   node council-pick.mjs --host claude|codex|grok [--timeout 1800000] [--port 3145]
 */
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import crypto from "node:crypto";

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROSTER_PATH = path.join(DIR, "council-roster.json");
const PICK_PATH = path.join(DIR, "council-pick.json");
const HTML_PATH = path.join(DIR, "model-council-console.html");

const HOST_VENDORS = { claude: "Anthropic", codex: "OpenAI", grok: "xAI" };
const HOST_KEYS = { claude: "claude", codex: "sol", grok: "grok" };

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const hostId = arg("host", "claude");
const timeoutMs = Number(arg("timeout", "1800000")) || 1800000;
const startPort = Number(arg("port", "3145")) || 3145;
const runToken = crypto.randomBytes(16).toString("hex");

if (!HOST_VENDORS[hostId]) {
  console.error(`COUNCIL_PICK_ERR unknown --host ${hostId} (claude|codex|grok)`);
  process.exit(1);
}

function validatePick(body, roster) {
  if (!body || typeof body !== "object") return "pick body missing";
  const panel = Array.isArray(body.panel) ? body.panel.map(String) : [];
  const auditor = body.auditor != null ? String(body.auditor) : "";
  if (panel.length < 2 || panel.length > 5) return "panel must be 2–5 seats";
  if (!auditor) return "auditor required";
  if (new Set(panel).size !== panel.length) return "duplicate panel key";
  if (panel.includes(auditor)) return "auditor cannot also sit on the panel";
  const byKey = Object.fromEntries((roster.models || []).map((m) => [m.key, m]));
  const hostVendor = HOST_VENDORS[hostId];
  const hostKey = HOST_KEYS[hostId];
  for (const k of [...panel, auditor]) {
    if (!byKey[k]) return `unknown key ${k}`;
  }
  const seenVendors = new Set();
  for (const k of panel) {
    const m = byKey[k];
    if (m.key === hostKey || m.vendor === hostVendor) return `${m.name} is the host  -  not a pick`;
    if (!(m.pickableAs || []).includes("panel")) return `${m.name} is not pickable as panel`;
    if (seenVendors.has(m.vendor)) return `duplicate panel vendor ${m.vendor}`;
    seenVendors.add(m.vendor);
  }
  const aud = byKey[auditor];
  if (aud.key === hostKey || aud.vendor === hostVendor) return `${aud.name} is the host  -  not a pick`;
  if (!(aud.pickableAs || []).includes("auditor")) return `${aud.name} is not pickable as auditor`;
  if (seenVendors.has(aud.vendor)) return `auditor vendor ${aud.vendor} already on the panel`;
  const allow = new Set(["low", "medium", "high", "xhigh", "max"]);
  const effortIn = body.effort && typeof body.effort === "object" ? body.effort : {};
  const effort = {};
  for (const k of [...panel, auditor]) {
    const raw = effortIn[k];
    if (raw != null && !allow.has(String(raw))) return `bad effort for ${k}`;
    effort[k] = raw != null ? String(raw) : (byKey[k].effort || "high");
  }
  body._effort = effort;
  return null;
}

function mime(file) {
  if (file.endsWith(".html")) return "text/html; charset=utf-8";
  if (file.endsWith(".json")) return "application/json; charset=utf-8";
  if (file.endsWith(".js")) return "text/javascript; charset=utf-8";
  return "application/octet-stream";
}

function openBrowser(url) {
  const plat = process.platform;
  if (plat === "win32") {
    // `cmd start` is unreliable from a detached spawn (quoted argv, no window).
    // PowerShell Start-Process uses the default browser and actually pops a tab.
    spawn("powershell", [
      "-NoProfile",
      "-NonInteractive",
      "-Command",
      `Start-Process ${JSON.stringify(url)}`,
    ], { detached: true, stdio: "ignore", windowsHide: true }).unref();
  } else if (plat === "darwin") spawn("open", [url], { detached: true, stdio: "ignore" }).unref();
  else spawn("xdg-open", [url], { detached: true, stdio: "ignore" }).unref();
}

function serveHtml() {
  const raw = fs.readFileSync(HTML_PATH, "utf8");
  const boot = `<script>window.__COUNCIL_HOST__=${JSON.stringify(hostId)};window.__COUNCIL_PICK__=true;</script>`;
  if (raw.includes("<!--COUNCIL_HOST-->")) return raw.replace("<!--COUNCIL_HOST-->", boot);
  return raw.replace("</head>", `${boot}</head>`);
}

const roster = JSON.parse(fs.readFileSync(ROSTER_PATH, "utf8"));
try { fs.unlinkSync(PICK_PATH); } catch { /* no prior pick */ }

let settled = false;
function finish(code, line) {
  if (settled) return;
  settled = true;
  if (line) console.log(line);
  server.close(() => process.exit(code));
  setTimeout(() => process.exit(code), 500);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url || "/", `http://127.0.0.1`);
  const send = (status, type, body) => {
    res.writeHead(status, { "content-type": type, "cache-control": "no-store" });
    res.end(body);
  };

  if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/model-council-console.html")) {
    return send(200, mime(HTML_PATH), serveHtml());
  }
  if (req.method === "GET" && url.pathname === "/config.json") {
    return send(200, "application/json; charset=utf-8", JSON.stringify({ host: hostId, pick: true }));
  }
  if (req.method === "GET" && url.pathname === "/council-roster.json") {
    return send(200, mime(ROSTER_PATH), fs.readFileSync(ROSTER_PATH));
  }
  if (req.method === "POST" && url.pathname === "/pick") {
    // POST /pick writes the pick file, so it is the one request a hostile page open in the owner's
    // browser could forge (a text/plain POST needs no preflight). Same gates as f-plancheck's picker:
    // a foreign or "null" Origin is refused, the body must be application/json, and only one pick lands.
    if (accepted || inFlight) { send(409, "text/plain", "pick already recorded"); return; }
    if (isForeignOrigin(req.headers.origin)) {
      console.error(`COUNCIL_PICK_WARN cross-origin POST /pick refused (origin ${String(req.headers.origin).slice(0, 200)})`);
      send(403, "text/plain", "cross-origin pick refused");
      return;
    }
    if (!isJsonContentType(req.headers["content-type"])) {
      send(415, "text/plain", "content-type must be application/json");
      return;
    }
    let raw = "";
    req.on("data", (c) => { raw += c; if (raw.length > 1e6) req.destroy(); });
    req.on("end", () => {
      if (accepted || inFlight) { send(409, "text/plain", "pick already recorded"); return; }
      let body;
      try { body = JSON.parse(raw || "{}"); } catch { send(400, "text/plain", "invalid json"); return; }
      const err = validatePick(body, roster);
      if (err) { send(400, "text/plain", err); return; }
      const pick = {
        host: hostId,
        token: runToken,
        panel: body.panel.map(String),
        auditor: String(body.auditor),
        effort: body._effort || {},
        pickedAt: new Date().toISOString(),
      };
      inFlight = true;
      try {
        fs.writeFileSync(PICK_PATH, JSON.stringify(pick, null, 2));
      } catch (writeErr) {
        inFlight = false;
        console.error(`COUNCIL_PICK_ERR write: ${writeErr.message}`);
        send(500, "text/plain", "could not record pick");
        finish(1, "COUNCIL_PICK_ERR");
        return;
      }
      accepted = true;
      send(200, "application/json", JSON.stringify({ ok: true }));
      console.log(`COUNCIL_PICK_FILE=${PICK_PATH}`);
      console.log(`COUNCIL_PICK_TOKEN=${runToken}`);
      finish(0, "COUNCIL_PICK_OK");
    });
    return;
  }
  send(404, "text/plain", "not found");
});

let accepted = false;
let inFlight = false;
let boundPort = null;
function isForeignOrigin(originHeader) {
  if (originHeader == null) return false;   // a non-browser local client sends none
  const own = new Set([`http://127.0.0.1:${boundPort}`, `http://localhost:${boundPort}`, `http://[::1]:${boundPort}`]);
  return !own.has(String(originHeader).toLowerCase());
}
function isJsonContentType(contentType) {
  return typeof contentType === "string" && contentType.trim().toLowerCase().startsWith("application/json");
}

function listen(port) {
  server.once("error", (err) => {
    if (err && err.code === "EADDRINUSE" && port < startPort + 10) listen(port + 1);
    else {
      console.error(`COUNCIL_PICK_ERR ${err.message}`);
      process.exit(1);
    }
  });
  server.listen(port, "127.0.0.1", () => {
    const addr = server.address();
    const p = addr && typeof addr === "object" ? addr.port : port;
    boundPort = p;
    // No `&` in this URL. Windows `start` splits on it and used to drop `host=`.
    const url = `http://127.0.0.1:${p}/model-council-console.html?pick=1`;
    console.log(`COUNCIL_PICK_URL=${url}`);
    console.log(`COUNCIL_PICK_FILE=${PICK_PATH}`);
    console.log(`COUNCIL_PICK_TOKEN=${runToken}`);
    openBrowser(url);
    setTimeout(() => finish(2, "COUNCIL_PICK_TIMEOUT"), timeoutMs);
  });
}

listen(startPort);
