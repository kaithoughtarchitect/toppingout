#!/usr/bin/env node
/**
 * One-shot f-plancheck seat picker. Serves the console HTML, accepts one
 * POST /pick, writes plancheck-pick.json, exits. Nothing stays running.
 *
 *   node plancheck-pick.mjs --host <claude|codex|grok|roster-resolvable model id> --player <id> [--timeout 1800000] [--port 3155] [--no-open]
 *   (--host and --player both resolve to a vendor family through the roster: a known host id,
 *    a roster model id / cliModel / slug, or a family keyword — a pi-hosted session passes the
 *    model pi is running.)
 */
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import crypto from "node:crypto";

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROSTER_PATH = path.join(DIR, "plancheck-roster.json");
const PICK_PATH = path.join(DIR, "plancheck-pick.json");
const HTML_PATH = path.join(DIR, "plancheck-console.html");

const DOORS = new Set(["codex CLI", "claude CLI", "grok CLI", "OpenRouter"]);

/** Pure. No I/O. `{ id -> roster row }` for O(1) seat lookup. */
function modelsById(roster) {
  return Object.fromEntries((roster.models || []).map((m) => [m.id, m]));
}

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
}

/** Pure. No I/O. Resolves a --player id to a vendor family, or null. */
export function resolvePlayerVendor(id, roster) {
  if (id == null) return null;
  const lower = String(id).toLowerCase();

  const hosts = roster.hosts || {};
  if (hosts[lower] && hosts[lower].vendor) return hosts[lower].vendor;

  for (const m of roster.models || []) {
    if (String(m.id).toLowerCase() === lower) return m.vendor;
    if (m.cliModel && String(m.cliModel).toLowerCase() === lower) return m.vendor;
    if (m.slug && String(m.slug).toLowerCase() === lower) return m.vendor;
    if (m.vendor && String(m.vendor).toLowerCase() === lower) return m.vendor;
  }

  const families = roster.families || {};
  for (const [vendor, keywords] of Object.entries(families)) {
    for (const kw of keywords || []) {
      if (lower.includes(String(kw).toLowerCase())) return vendor;
    }
  }

  return null;
}

/** Pure. No I/O. Returns an error string, or null when the roster is well-formed. */
export function validateRoster(roster) {
  if (!roster || typeof roster !== "object") return "roster missing";
  const models = Array.isArray(roster.models) ? roster.models : null;
  if (!models || models.length === 0) return "roster.models must be a non-empty array";

  // First pass: which vendors already have a $0 CLI door (codex/claude/grok CLI).
  // An OpenRouter row for one of those vendors would duplicate a $0 door with a
  // pay-per-token one — refused below.
  const cliDoorVendors = new Set();
  for (const m of models) {
    if (m && typeof m === "object" && m.door && m.door !== "OpenRouter" && m.vendor) {
      cliDoorVendors.add(m.vendor);
    }
  }

  const seenIds = new Set();
  for (const m of models) {
    if (!m || typeof m !== "object") return "roster row missing";
    for (const field of ["id", "name", "vendor", "door", "effort", "pickableAs"]) {
      if (m[field] == null) return `roster row ${m.id || "?"} missing ${field}`;
    }
    if (seenIds.has(m.id)) return `duplicate roster id ${m.id}`;
    seenIds.add(m.id);
    if (m.effort !== "high") return `roster row ${m.id} effort must be "high"`;
    if (!DOORS.has(m.door)) return `roster row ${m.id} has unknown door ${m.door}`;
    if (m.door === "OpenRouter") {
      if (!m.slug) return `roster row ${m.id} (OpenRouter) missing slug`;
      if (String(m.slug).startsWith("anthropic/")) return `roster row ${m.id} slug must not be an anthropic/* OpenRouter id`;
      if (m.vendor === "Anthropic") return `roster row ${m.id} is an Anthropic OpenRouter row — Claude-family seats use the claude CLI`;
      if (cliDoorVendors.has(m.vendor)) return `roster row ${m.id} duplicates a $0 CLI door for ${m.vendor}`;
    } else if (!m.cliModel) {
      return `roster row ${m.id} (${m.door}) missing cliModel`;
    }
  }

  const picker = roster.picker || {};
  if (!(Number(picker.minSeats) >= 1)) return "roster.picker.minSeats must be >= 1";
  if (!(Number(picker.maxSeats) <= 5)) return "roster.picker.maxSeats must be <= 5";
  if (!(Number(picker.minSeats) <= Number(picker.maxSeats))) return "roster.picker.minSeats must be <= maxSeats";

  return null;
}

/** Pure. No I/O. Returns an error string, or null when the pick is valid. */
export function validatePick(body, roster, excludedVendors) {
  if (!body || typeof body !== "object") return "pick body missing";
  if (!Array.isArray(body.seats)) return "seats must be an array";
  const seats = body.seats.map(String);

  const { minSeats, maxSeats } = roster.picker || {};
  if (seats.length < minSeats || seats.length > maxSeats) {
    return `select between ${minSeats} and ${maxSeats} seats`;
  }
  if (new Set(seats).size !== seats.length) return "duplicate seat id";

  const byId = modelsById(roster);
  for (const id of seats) {
    if (!byId[id]) return `unknown seat ${id}`;
  }

  const excluded = new Set(excludedVendors || []);
  const seenVendors = new Set();
  for (const id of seats) {
    const m = byId[id];
    if (!(m.pickableAs || []).includes("panel")) return `${m.name} is not pickable as panel`;
    if (excluded.has(m.vendor)) return `${m.vendor} is the host/Player family — not a pick`;
    if (seenVendors.has(m.vendor)) return `duplicate seat vendor ${m.vendor}`;
    seenVendors.add(m.vendor);
  }

  return null;
}

function mime(file) {
  if (file.endsWith(".html")) return "text/html; charset=utf-8";
  if (file.endsWith(".json")) return "application/json; charset=utf-8";
  return "application/octet-stream";
}

// M8: opening the browser is a convenience, never a requirement — the URL is
// already printed to stdout above the call site. A missing/unspawnable
// browser launcher (powershell/open/xdg-open absent or erroring) must warn,
// not exit; the operator still has the printed URL to open by hand.
function openBrowser(url) {
  const plat = process.platform;
  let child;
  if (plat === "win32") {
    // `cmd start` is unreliable from a detached spawn (quoted argv, no window).
    // PowerShell Start-Process uses the default browser and actually pops a tab.
    child = spawn("powershell", [
      "-NoProfile",
      "-NonInteractive",
      "-Command",
      `Start-Process ${JSON.stringify(url)}`,
    ], { detached: true, stdio: "ignore", windowsHide: true });
  } else if (plat === "darwin") {
    child = spawn("open", [url], { detached: true, stdio: "ignore" });
  } else {
    child = spawn("xdg-open", [url], { detached: true, stdio: "ignore" });
  }
  child.on("error", (err) => {
    console.error(`PLANCHECK_PICK_WARN browser open failed: ${err.message} — open the URL above manually`);
  });
  child.unref();
}

function isMainModule() {
  try {
    return path.resolve(fileURLToPath(import.meta.url)) === path.resolve(process.argv[1] || "");
  } catch {
    return false;
  }
}

function main() {
  const hostId = arg("host", undefined);
  let playerId = arg("player", undefined);
  const timeoutMs = Number(arg("timeout", "1800000")) || 1800000;
  const startPort = Number(arg("port", "3155")) || 3155;
  const noOpen = hasFlag("no-open");
  const runToken = crypto.randomBytes(16).toString("hex");

  let roster;
  try {
    roster = JSON.parse(fs.readFileSync(ROSTER_PATH, "utf8"));
  } catch (err) {
    console.error(`PLANCHECK_PICK_ERR roster: ${err.message}`);
    process.exit(1);
  }

  const rosterErr = validateRoster(roster);
  if (rosterErr) {
    console.error(`PLANCHECK_PICK_ERR roster: ${rosterErr}`);
    process.exit(1);
  }

  // `--host` can name a fixed CLI door (claude|codex|grok) or, for a
  // pi-hosted session, any roster id / cliModel / slug / family keyword the
  // roster can resolve — same resolution path as `--player` (A1).
  const hostVendor = resolvePlayerVendor(hostId, roster);
  if (!hostVendor) {
    console.error(`PLANCHECK_PICK_ERR unresolvable --host ${hostId}`);
    process.exit(1);
  }
  const hostRow = hostId != null && roster.hosts ? roster.hosts[String(hostId).toLowerCase()] : null;
  const hostLabel = hostRow ? hostRow.label : hostVendor;

  let playerDefaulted = false;
  if (!playerId) {
    playerId = hostId;
    playerDefaulted = true;
    console.log(`PLANCHECK_PICK_PLAYER=${playerId} (defaulted to host)`);
  }

  const playerVendor = resolvePlayerVendor(playerId, roster);
  if (!playerVendor) {
    console.error(`PLANCHECK_PICK_ERR unresolvable --player ${playerId}`);
    process.exit(1);
  }

  const excludedVendors = [...new Set([hostVendor, playerVendor])];
  const minSeats = Number(roster.picker.minSeats);
  const maxSeats = Number(roster.picker.maxSeats);

  try { fs.unlinkSync(PICK_PATH); } catch { /* no prior pick */ }

  function bootConfig() {
    return {
      host: hostId,
      hostVendor,
      hostLabel,
      player: playerId,
      playerVendor,
      excludedVendors,
      minSeats,
      maxSeats,
      pick: true,
    };
  }

  // M10: split into two phases so the route handler can tell an unreadable
  // asset apart from a boot-config injection failure and log each distinctly.
  function readHtmlAsset() {
    return fs.readFileSync(HTML_PATH, "utf8");
  }
  function injectBoot(raw) {
    // Every `<` becomes its JSON unicode escape (u003c) so a --host/--player
    // value containing `</script>` cannot terminate the boot element;
    // JSON.parse yields the identical string.
    const json = JSON.stringify(bootConfig()).replace(/</g, "\\u003c");
    const boot = `<script>window.__PLANCHECK__=${json};</script>`;
    if (raw.includes("<!--PLANCHECK_BOOT-->")) return raw.replace("<!--PLANCHECK_BOOT-->", boot);
    return raw.replace("</head>", `${boot}</head>`);
  }

  let settled = false;
  function finish(code, line) {
    if (settled) return;
    settled = true;
    if (line) console.log(line);
    server.close(() => process.exit(code));
    setTimeout(() => process.exit(code), 500);
  }

  // One-shot: the first successful POST /pick sets this and every later
  // POST (retry, double-click, replay) is refused with 409 — the pick file
  // is written exactly once (A4). `inFlight` (M9) covers the window between
  // validating a pick and its write landing — a second POST that arrives
  // mid-write must also get 409, not race the file write.
  let accepted = false;
  let inFlight = false;

  // POST /pick has a side effect (it writes the pick file), so it is the one
  // request a hostile page open in the operator's browser could forge: a
  // `text/plain` POST needs no CORS preflight and the write lands even
  // though the response stays opaque. Two same-origin gates, neither of
  // which changes the contract for the console or for local non-browser
  // clients: browsers always send `Origin` on a POST — any value other than
  // this server's own loopback origin is refused (absent = non-browser local
  // client, allowed; the literal "null" of a sandboxed/file: page is
  // refused) — and the body must be `application/json`, which forces a
  // cross-origin browser into a preflight this server answers 404.
  let boundPort = null;
  function isForeignOrigin(originHeader) {
    if (originHeader == null) return false;
    const own = new Set([
      `http://127.0.0.1:${boundPort}`,
      `http://localhost:${boundPort}`,
      `http://[::1]:${boundPort}`,
    ]);
    return !own.has(String(originHeader).toLowerCase());
  }
  function isJsonContentType(contentType) {
    return typeof contentType === "string" && contentType.trim().toLowerCase().startsWith("application/json");
  }

  const server = http.createServer((req, res) => {
    const url = new URL(req.url || "/", "http://127.0.0.1");
    const send = (status, type, bodyText) => {
      res.writeHead(status, { "content-type": type, "cache-control": "no-store" });
      res.end(bodyText);
    };

    if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/plancheck-console.html")) {
      // M10: the asset read and the boot-config injection are separate
      // failure modes with separate log lines — an unreadable HTML file is
      // not the same problem as bootConfig()/JSON.stringify throwing.
      let raw;
      try {
        raw = readHtmlAsset();
      } catch (err) {
        console.error(`PLANCHECK_PICK_ERR asset ${path.basename(HTML_PATH)}: ${err.message}`);
        return send(500, "text/plain", "picker asset unreadable");
      }
      try {
        return send(200, mime(HTML_PATH), injectBoot(raw));
      } catch (err) {
        console.error(`PLANCHECK_PICK_ERR boot: ${err.message}`);
        return send(500, "text/plain", "picker boot config unavailable");
      }
    }
    if (req.method === "GET" && url.pathname === "/config.json") {
      return send(200, "application/json; charset=utf-8", JSON.stringify(bootConfig()));
    }
    if (req.method === "GET" && url.pathname === "/plancheck-roster.json") {
      try {
        return send(200, mime(ROSTER_PATH), fs.readFileSync(ROSTER_PATH));
      } catch (err) {
        console.error(`PLANCHECK_PICK_ERR asset ${path.basename(ROSTER_PATH)}: ${err.message}`);
        return send(500, "text/plain", "picker asset unreadable");
      }
    }
    if (req.method === "POST" && url.pathname === "/pick") {
      if (accepted || inFlight) { send(409, "text/plain", "pick already recorded"); return; }
      if (isForeignOrigin(req.headers.origin)) {
        console.error(`PLANCHECK_PICK_WARN cross-origin POST /pick refused (origin ${String(req.headers.origin).slice(0, 200)})`);
        send(403, "text/plain", "cross-origin pick refused");
        return;
      }
      if (!isJsonContentType(req.headers["content-type"])) {
        console.error(`PLANCHECK_PICK_WARN non-JSON POST /pick refused (content-type ${String(req.headers["content-type"] ?? "").slice(0, 200)})`);
        send(415, "text/plain", "content-type must be application/json");
        return;
      }
      let raw = "";
      req.on("data", (c) => { raw += c; if (raw.length > 1e6) req.destroy(); });
      req.on("end", () => {
        if (accepted || inFlight) { send(409, "text/plain", "pick already recorded"); return; }
        let body;
        try { body = JSON.parse(raw || "{}"); } catch { send(400, "text/plain", "invalid json"); return; }
        const err = validatePick(body, roster, excludedVendors);
        if (err) { send(400, "text/plain", err); return; }
        inFlight = true;
        const byId = modelsById(roster);
        const seats = body.seats.map(String).map((id) => ({ id, door: byId[id].door }));
        const pick = {
          token: runToken,
          host: hostId,
          player: playerId,
          seats,
          pickedAt: new Date().toISOString(),
        };
        // M9: a failed write must not report success or silently do nothing
        // — the pick file either exists with the real pick, or the operator
        // sees an explicit failure and the process exits non-zero. `accepted`
        // is only set true after the write actually lands, so a write
        // failure leaves the one-shot gate open for `inFlight`'s reset below
        // (moot in practice — `finish` exits the process momentarily after).
        try {
          fs.writeFileSync(PICK_PATH, JSON.stringify(pick, null, 2));
        } catch (writeErr) {
          inFlight = false;
          console.error(`PLANCHECK_PICK_ERR write: ${writeErr.message}`);
          send(500, "text/plain", "could not record pick");
          finish(1, "PLANCHECK_PICK_ERR");
          return;
        }
        accepted = true;
        send(200, "application/json", JSON.stringify({ ok: true }));
        console.log(`PLANCHECK_PICK_FILE=${PICK_PATH}`);
        console.log(`PLANCHECK_PICK_TOKEN=${runToken}`);
        finish(0, "PLANCHECK_PICK_OK");
      });
      return;
    }
    send(404, "text/plain", "not found");
  });

  function listen(port) {
    server.once("error", (err) => {
      if (err && err.code === "EADDRINUSE" && port < startPort + 10) listen(port + 1);
      else {
        console.error(`PLANCHECK_PICK_ERR ${err.message}`);
        process.exit(1);
      }
    });
    server.listen(port, "127.0.0.1", () => {
      const addr = server.address();
      const p = addr && typeof addr === "object" ? addr.port : port;
      boundPort = p;
      // No `&` in this URL. Windows `start` splits on it and used to drop `host=`.
      const url = `http://127.0.0.1:${p}/plancheck-console.html?pick=1`;
      console.log(`PLANCHECK_PICK_URL=${url}`);
      console.log(`PLANCHECK_PICK_FILE=${PICK_PATH}`);
      console.log(`PLANCHECK_PICK_TOKEN=${runToken}`);
      console.log(`PLANCHECK_PICK_HOST=${hostId} (${hostVendor})`);
      console.log(`PLANCHECK_PICK_PLAYER=${playerId} (${playerVendor})`);
      if (!noOpen) openBrowser(url);
      setTimeout(() => finish(2, "PLANCHECK_PICK_TIMEOUT"), timeoutMs);
    });
  }

  listen(startPort);
}

if (isMainModule()) main();
