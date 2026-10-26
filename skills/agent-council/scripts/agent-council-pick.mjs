#!/usr/bin/env node
/**
 * One-shot agent-council seat picker. Serves the console HTML, accepts one
 * POST /pick, writes the pick file, exits. Nothing stays running.
 *
 *   node agent-council-pick.mjs --host <host id|vendor|alias> [--profile focused|balanced|full]
 *                               [--out <file>] [--timeout 1800000] [--port 3165] [--no-open]
 *
 * Three things separate this from the model-council and f-plancheck pickers, and
 * each is forced by agent-council's own law rather than chosen for variety:
 *
 *  1. Seat distinctness is not "one seat per vendor". The resolver refuses a
 *     table whose members share an id, a model, a vendor, a family, a base
 *     model, or a correlation group, so this picker imports the resolver's own
 *     `profileCollisions` instead of re-deriving a weaker rule. A pick this tab
 *     accepts therefore passes `prepare`'s collision, auditor-separation and
 *     qualification checks. It does NOT pre-check live transport availability:
 *     `prepare` resolves against a pi model catalog plus whichever native CLIs
 *     preflight, so an uninstalled `grok-cli` still leaves `grok` seatable here
 *     and rejected there. Availability is the one refusal this tab cannot
 *     predict.
 *  2. The auditor is a separate, non-participating choice — not the runner-up
 *     seat — and must be pairwise distinct from the chair and every seat.
 *  3. The pick file is written OUTSIDE the skill directory (default: the OS temp
 *     dir). The skill directory's file inventory is kept exact (a repo's
 *     readiness check may assert it and its `.claude`/`.agents` mirror
 *     equality); a pick receipt dropped inside the skill would break that for as
 *     long as it existed.
 *
 * This tab never approves the disclosure manifest. The manifest does not exist
 * until `prepare` has run, and `prepare` needs these seats — seat consent is
 * upstream of disclosure consent and stays a separate act.
 */
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import crypto from "node:crypto";

import {
  AGENT_COUNCIL_PANEL_PROFILES,
  adapterContract,
  profileCollisions,
  validateRosterPool,
} from "./agent-council-core.mjs";

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROSTER_PATH = path.join(DIR, "..", "references", "default-roster.json");
const HTML_PATH = path.join(DIR, "agent-council-console.html");
const DEFAULT_PICK_PATH = path.join(os.tmpdir(), "agent-council-pick.json");

const PICK_SCHEMA_VERSION = 1;

// The skill directory, whose file inventory is kept exact (a repo's readiness
// check may assert it). A receipt written anywhere under this root would break
// that for as long as it exists.
const SKILL_ROOT = path.resolve(DIR, "..");

/**
 * Pure. No I/O. The panel contract for a profile name, or null.
 *
 * `AGENT_COUNCIL_PANEL_PROFILES` is a plain frozen object, so a bracket lookup
 * resolves prototype keys: `PROFILES["__proto__"]` is `Object.prototype`, which
 * is truthy and sails past an `if (!contract)` guard. The core file already
 * solved this for its adapter table with `Object.hasOwn` and says to read it
 * through an accessor rather than by direct index; this is the same accessor for
 * the same hazard. An unknown name, a non-string, or a prototype key fails
 * closed to null.
 */
export function panelProfileContract(profileName) {
  if (typeof profileName !== "string") return null;
  if (!Object.hasOwn(AGENT_COUNCIL_PANEL_PROFILES, profileName)) return null;
  return AGENT_COUNCIL_PANEL_PROFILES[profileName];
}

/** Pure. No I/O. Every profile name the picker will accept. */
export function panelProfileNames() {
  return Object.keys(AGENT_COUNCIL_PANEL_PROFILES);
}

function arg(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
}

/** Pure. No I/O. Every profile row the pool declares, by id. */
export function profilesById(pool) {
  return Object.fromEntries([
    ...(pool.hosts ?? []),
    ...(pool.participants ?? []),
    ...(pool.auditors ?? []),
  ].map((profile) => [profile.id, profile]));
}

/**
 * Returns an error string, or null when the pool is well-formed.
 *
 * Delegates row checking to the resolver's own `validateRosterPool`, which is
 * role-scoped and closes the key set per role: a host row carrying a `model`, or
 * a seat row carrying a `runtimeDescriptor`, is refused here exactly as it is at
 * `prepare`. A hand-rolled check here was strictly weaker — it asked only for
 * "a model or a runtimeDescriptor" on any row, so a mis-copied host row would
 * pass the picker, let an operator complete a full pick, and only fail later.
 * Maintaining a second validator over the same file is how the two drift.
 *
 * The thrown validation error is converted to this file's string convention so
 * every caller keeps one idiom.
 */
export function validatePool(pool, nowMs = Date.now()) {
  try {
    const parsed = validateRosterPool(pool, nowMs);
    for (const [key, rows] of Object.entries(parsed)) {
      if (rows.length === 0) return `roster.${key} must be a non-empty array`;
    }
    const largest = Math.max(...Object.values(AGENT_COUNCIL_PANEL_PROFILES).map((entry) => entry.externalSeatCount));
    if (parsed.participants.length < largest) return `roster.participants must hold at least ${largest} rows`;
    return null;
  } catch (err) {
    return `roster: ${err.message}`;
  }
}

/**
 * Pure. No I/O. A host id, a vendor id, or a bare alias ("claude", "grok") —
 * anything that names exactly one host row. Ambiguity is an error, never a
 * silent first match: seating the wrong chair makes the whole panel self-review.
 */
export function resolveHost(pool, hostId) {
  if (hostId == null || String(hostId).trim() === "") return { host: null, error: "--host is required" };
  const wanted = String(hostId).trim().toLowerCase();
  const hosts = pool.hosts ?? [];
  const exact = hosts.find((profile) => String(profile.id).toLowerCase() === wanted);
  if (exact) return { host: exact, error: null };
  const matches = hosts.filter((profile) => (
    String(profile.lineage.vendorId).toLowerCase() === wanted
    || (profile.model != null && String(profile.model).toLowerCase() === wanted)
    || String(profile.id).toLowerCase().includes(wanted)
  ));
  if (matches.length === 1) return { host: matches[0], error: null };
  if (matches.length > 1) {
    return { host: null, error: `--host ${hostId} names ${matches.length} hosts (${matches.map((m) => m.id).join(", ")})` };
  }
  return { host: null, error: `unresolvable --host ${hostId} (known: ${hosts.map((m) => m.id).join(", ")})` };
}

/** Pure. No I/O. True when the row's qualification window has closed. */
export function isExpired(profile, nowMs) {
  const expiresAt = profile?.qualification?.expiresAt;
  if (!expiresAt) return true;
  const parsed = Date.parse(expiresAt);
  return !Number.isFinite(parsed) || parsed <= nowMs;
}

/**
 * Pure. No I/O. Why this row cannot be seated beside the ones already chosen —
 * the resolver's own reasons, so the tab and `prepare` never disagree.
 *
 * @returns {string[]} Empty means clear. Check `.length`, never truthiness: `[]`
 * is truthy, so the `if (err)` idiom every sibling validator in this file uses
 * would refuse every row here. The reasons are returned in full because callers
 * render them.
 */
export function seatBlockers(candidate, chosen, nowMs) {
  const reasons = [];
  if (isExpired(candidate, nowMs)) reasons.push("qualification expired");
  if (candidate?.qualification?.status && candidate.qualification.status !== "qualified") {
    reasons.push(`qualification ${candidate.qualification.status}`);
  }
  for (const other of chosen) {
    if (!other || other === candidate) continue;
    for (const reason of profileCollisions(candidate, other)) {
      reasons.push(`shares ${reason} with ${other.id}`);
    }
  }
  return [...new Set(reasons)];
}

/** Pure. No I/O. Returns an error string, or null when the pick is valid. */
export function validatePick(body, pool, host, nowMs) {
  if (!body || typeof body !== "object") return "pick body missing";

  const profileName = String(body.profile ?? "");
  const contract = panelProfileContract(profileName);
  if (!contract) return `profile must be one of ${panelProfileNames().join(", ")}`;

  if (!Array.isArray(body.seats)) return "seats must be an array";
  const seatIds = body.seats.map(String);
  if (seatIds.length !== contract.externalSeatCount) {
    return `${profileName} seats exactly ${contract.externalSeatCount} external models`;
  }
  if (new Set(seatIds).size !== seatIds.length) return "duplicate seat id";

  const auditorId = body.auditor == null ? "" : String(body.auditor);
  if (!auditorId) return "an auditor is required";
  if (seatIds.includes(auditorId)) return "the auditor never sits on the panel";

  const participants = new Map((pool.participants ?? []).map((profile) => [profile.id, profile]));
  const auditors = new Map((pool.auditors ?? []).map((profile) => [profile.id, profile]));

  const seats = [];
  for (const id of seatIds) {
    const profile = participants.get(id);
    if (!profile) return `unknown seat ${id}`;
    seats.push(profile);
  }
  const auditor = auditors.get(auditorId);
  if (!auditor) return `unknown auditor ${auditorId}`;

  // An auditor reads the panel's own records back, so its transport must be
  // able to write a response file the runner can read — the adapter table is
  // the authority, exactly as it is at roster resolution.
  if (adapterContract(auditor.qualification?.adapter?.name)?.auditCapable !== true) {
    return `${auditorId} runs a transport that cannot audit`;
  }

  const table = [host, ...seats, auditor];
  // `seatBlockers` is the per-row rule: qualification window plus declared
  // status. Call it rather than re-testing expiry inline — an inline check that
  // reads only `expiresAt` skips `qualification.status`, and would seat a row
  // that is disqualified but not yet expired.
  for (const profile of table) {
    const rowBlockers = seatBlockers(profile, [], nowMs);
    if (rowBlockers.length) return `${profile.id}: ${rowBlockers.join("; ")}`;
  }
  for (let left = 0; left < table.length; left += 1) {
    for (let right = left + 1; right < table.length; right += 1) {
      const reasons = profileCollisions(table[left], table[right]);
      if (reasons.length) return `${table[left].id} and ${table[right].id} share ${reasons.join(", ")}`;
    }
  }
  return null;
}

/**
 * Pure. No I/O. The exact `prepare` flags this pick means.
 *
 * `--host-id` is included because `prepare` requires it and because the chair is
 * what every collision in this pick was judged against. Emitting the seats
 * without it would invite the caller to supply its own host, unpinning the
 * decision the operator actually made.
 */
export function prepareArgsFor(profileName, seatIds, auditorId, hostId) {
  return [
    "--host-id", hostId,
    "--profile", profileName,
    ...seatIds.flatMap((id) => ["--seat", id]),
    "--auditor", auditorId,
  ];
}

/**
 * Pure. No I/O. Why this receipt path is unusable, or null.
 *
 * `--out` has no equivalent in the model-council or f-plancheck pickers, which
 * hardcode their receipt path. Two things it must not do: land inside the skill
 * (its file inventory is kept exact), and destroy a file this tool
 * did not write.
 */
export function receiptPathBlocker(pickPath, skillRoot = SKILL_ROOT) {
  const resolved = path.resolve(pickPath);
  const relative = path.relative(path.resolve(skillRoot), resolved);
  if (relative !== "" && !relative.startsWith("..") && !path.isAbsolute(relative)) {
    return `--out ${resolved} is inside the skill directory, where a pick receipt would fail the agent-council-contracts inventory gate`;
  }
  return null;
}

/**
 * Parses a pick receipt, or throws.
 *
 * The receipt is a cross-process contract: this file writes it and a separate
 * agent session reads it. Until now the read side existed only as prose in
 * SKILL.md telling that agent to compare the token itself, with nothing in code
 * to enforce it — and skipping that comparison means acting on a stale pick from
 * an earlier run, which `prepare` cannot catch because a stale pick is still a
 * legal one. `expectedToken` is the value the picker printed as
 * `AGENT_COUNCIL_PICK_TOKEN=`.
 */
export function parsePickReceipt(raw, expectedToken) {
  let receipt;
  try {
    receipt = JSON.parse(raw);
  } catch (err) {
    throw new Error(`pick receipt is not JSON: ${err.message}`);
  }
  if (!receipt || typeof receipt !== "object" || Array.isArray(receipt)) throw new Error("pick receipt is not an object");
  if (receipt.schemaVersion !== PICK_SCHEMA_VERSION) {
    throw new Error(`pick receipt schemaVersion ${receipt.schemaVersion} is not ${PICK_SCHEMA_VERSION}`);
  }
  if (typeof receipt.token !== "string" || receipt.token.length === 0) throw new Error("pick receipt carries no token");
  if (typeof expectedToken !== "string" || expectedToken.length === 0) throw new Error("no expected token was supplied");
  if (receipt.token !== expectedToken) throw new Error("pick receipt token does not match this run; it belongs to another picker run");
  const contract = panelProfileContract(receipt.profile);
  if (!contract) throw new Error(`pick receipt names an unknown profile ${receipt.profile}`);
  if (!Array.isArray(receipt.seats) || receipt.seats.length !== receipt.externalSeatCount) {
    throw new Error("pick receipt seat count disagrees with its own profile");
  }
  if (receipt.seats.length !== contract.externalSeatCount) {
    throw new Error("pick receipt seat count disagrees with the panel profile");
  }
  if (!receipt.auditor || typeof receipt.auditor.id !== "string") throw new Error("pick receipt names no auditor");
  if (!Array.isArray(receipt.prepareArgs) || !receipt.prepareArgs.includes("--host-id")) {
    throw new Error("pick receipt carries no runnable prepare args");
  }
  return receipt;
}

function mime(file) {
  if (file.endsWith(".html")) return "text/html; charset=utf-8";
  if (file.endsWith(".json")) return "application/json; charset=utf-8";
  return "application/octet-stream";
}

// Opening the browser is a convenience, never a requirement — the URL is
// printed to stdout above the call site, so a missing launcher warns and the
// operator opens the printed URL by hand.
function openBrowser(url) {
  const platform = process.platform;
  let child;
  if (platform === "win32") {
    // `cmd start` is unreliable from a detached spawn (quoted argv, no window).
    // PowerShell Start-Process uses the default browser and actually pops a tab.
    child = spawn("powershell", [
      "-NoProfile",
      "-NonInteractive",
      "-Command",
      `Start-Process ${JSON.stringify(url)}`,
    ], { detached: true, stdio: "ignore", windowsHide: true });
  } else if (platform === "darwin") {
    child = spawn("open", [url], { detached: true, stdio: "ignore" });
  } else {
    child = spawn("xdg-open", [url], { detached: true, stdio: "ignore" });
  }
  child.on("error", (err) => {
    console.error(`AGENT_COUNCIL_PICK_WARN browser open failed: ${err.message} — open the URL above manually`);
  });
  // `error` only covers a launcher that could not start. A launcher that starts
  // and then fails — no default browser registered, a URL it will not accept —
  // exits non-zero with its output discarded, which would otherwise be the one
  // failure mode this function promises to warn about and does not.
  child.on("exit", (code) => {
    if (code !== 0) {
      console.error(`AGENT_COUNCIL_PICK_WARN browser launcher exited ${code} — open the URL above manually`);
    }
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

if (isMainModule()) main();

/**
 * Everything the picker's HTTP surface needs, with no CLI parsing, no browser
 * launch and no `process.exit`. Exported rather than inlined in `main()` so the
 * one-shot gate, the two same-origin refusals and the write-failure rollback are
 * reachable from a test without spawning a process or exiting one: bind this to
 * 127.0.0.1:0 and drive it with real requests. Both sibling pickers inline their
 * handler and consequently test none of it.
 *
 * `onSettled(code, line)` is how the handler says the run is over; `main()` maps
 * that onto closing the server and exiting.
 */
export function createPickSurface(context) {
  const {
    pool,
    host,
    profileName,
    pickPath,
    runToken,
    htmlPath = HTML_PATH,
    now = () => Date.now(),
    onSettled = () => {},
  } = context;

  // Exported as a reuse seam, so it validates its own inputs rather than
  // trusting that every future caller replicates `main()`'s startup sequence.
  for (const [field, value] of [["pool", pool], ["host", host], ["pickPath", pickPath], ["runToken", runToken]]) {
    if (!value) throw new Error(`createPickSurface needs ${field}`);
  }
  if (!panelProfileContract(profileName)) throw new Error(`createPickSurface needs a known profileName, got ${JSON.stringify(profileName)}`);

  // One-shot. `accepted` is set only after the receipt write lands, and it is
  // what refuses every replay. `inFlight` covers the window between validating
  // a pick and that write landing — a window not reachable while the write is
  // synchronous, since nothing yields between the guard and `writeFileSync`. So
  // `inFlight` is unobservable belt-and-braces today, kept because an async
  // write would open the window for real. Untested by construction, and named
  // as such rather than counted as a tested guarantee.
  //
  // `boundPort` is the only field a caller may write, and only once, because the
  // port is unknown until the server's `listening` event. `accepted` and
  // `inFlight` are handler-internal: writing either from outside disables the
  // one-shot guard.
  const state = { accepted: false, inFlight: false, boundPort: null };

  function bootConfig() {
    const nowMs = now();
    const decorate = (profile) => {
      const adapterName = profile.qualification?.adapter?.name ?? null;
      const contract = adapterContract(adapterName);
      return {
        id: profile.id,
        // Resolver-faithful: a host row has no model, and the collision rule skips
        // the model axis when either side lacks one. Backfilling a display string
        // here would make the client's model axis active for host comparisons
        // where the resolver's never is — a mirror that matches by data luck
        // rather than by shape.
        model: profile.model ?? null,
        // What the chair strip shows a human. Never compared.
        displayLabel: profile.model ?? profile.runtimeDescriptor ?? profile.lineage.baseModelId,
        variant: profile.variant ?? null,
        vendorId: profile.lineage.vendorId,
        familyId: profile.lineage.familyId,
        baseModelId: profile.lineage.baseModelId,
        correlationGroupIds: profile.lineage.correlationGroupIds,
        adapter: adapterName,
        adapterVersion: profile.qualification?.adapter?.version ?? null,
        subscription: contract?.subscriptionTransport === true,
        auditCapable: contract?.auditCapable === true,
        expiresAt: profile.qualification?.expiresAt ?? null,
        expired: isExpired(profile, nowMs),
        evidenceRef: profile.qualification?.evidenceRef ?? null,
      };
    };
    return {
      pick: true,
      now: new Date(nowMs).toISOString(),
      profile: profileName,
      profiles: AGENT_COUNCIL_PANEL_PROFILES,
      host: decorate(host),
      participants: (pool.participants ?? []).map(decorate),
      auditors: (pool.auditors ?? []).map(decorate),
    };
  }

  function injectBoot(raw) {
    // Every `<` becomes its JSON unicode escape so a roster value containing
    // `</script>` cannot terminate the boot element; JSON.parse yields the
    // identical string.
    const json = JSON.stringify(bootConfig()).replace(/</g, "\\u003c");
    const boot = `<script>window.__AGENT_COUNCIL__=${json};</script>`;
    if (raw.includes("<!--AGENT_COUNCIL_BOOT-->")) return raw.replace("<!--AGENT_COUNCIL_BOOT-->", boot);
    return raw.replace("</head>", `${boot}</head>`);
  }

  // POST /pick has a side effect, so it is the one request a hostile page open
  // in the operator's browser could forge: a `text/plain` POST needs no CORS
  // preflight and the write would land even though the response stays opaque.
  // Two same-origin gates close it — browsers always send `Origin` on a POST,
  // and requiring `application/json` forces a cross-origin browser into a
  // preflight this server answers 404.
  function isForeignOrigin(originHeader) {
    if (originHeader == null) return false;
    const own = new Set([
      `http://127.0.0.1:${state.boundPort}`,
      `http://localhost:${state.boundPort}`,
      `http://[::1]:${state.boundPort}`,
    ]);
    return !own.has(String(originHeader).toLowerCase());
  }
  function isJsonContentType(contentType) {
    return typeof contentType === "string" && contentType.trim().toLowerCase().startsWith("application/json");
  }

  function handler(req, res) {
    const url = new URL(req.url || "/", "http://127.0.0.1");
    const send = (status, type, body) => {
      res.writeHead(status, { "content-type": type, "cache-control": "no-store" });
      res.end(body);
    };

    if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/agent-council-console.html")) {
      let raw;
      try {
        raw = fs.readFileSync(htmlPath, "utf8");
      } catch (err) {
        console.error(`AGENT_COUNCIL_PICK_ERR asset ${path.basename(htmlPath)}: ${err.message}`);
        return send(500, "text/plain", "picker asset unreadable");
      }
      try {
        return send(200, mime(htmlPath), injectBoot(raw));
      } catch (err) {
        console.error(`AGENT_COUNCIL_PICK_ERR boot: ${err.message}`);
        return send(500, "text/plain", "picker boot config unavailable");
      }
    }
    if (req.method === "GET" && url.pathname === "/config.json") {
      try {
        return send(200, "application/json; charset=utf-8", JSON.stringify(bootConfig()));
      } catch (err) {
        console.error(`AGENT_COUNCIL_PICK_ERR boot: ${err.message}`);
        return send(500, "text/plain", "picker boot config unavailable");
      }
    }
    if (req.method === "POST" && url.pathname === "/pick") {
      if (state.accepted || state.inFlight) { send(409, "text/plain", "pick already recorded"); return; }
      if (isForeignOrigin(req.headers.origin)) {
        console.error(`AGENT_COUNCIL_PICK_WARN cross-origin POST /pick refused (origin ${String(req.headers.origin).slice(0, 200)})`);
        send(403, "text/plain", "cross-origin pick refused");
        return;
      }
      if (!isJsonContentType(req.headers["content-type"])) {
        console.error(`AGENT_COUNCIL_PICK_WARN non-JSON POST /pick refused (content-type ${String(req.headers["content-type"] ?? "").slice(0, 200)})`);
        send(415, "text/plain", "content-type must be application/json");
        return;
      }
      let raw = "";
      req.on("data", (chunk) => { raw += chunk; if (raw.length > 1e6) req.destroy(); });
      req.on("end", () => {
        if (state.accepted || state.inFlight) { send(409, "text/plain", "pick already recorded"); return; }
        let body;
        try { body = JSON.parse(raw || "{}"); } catch { send(400, "text/plain", "invalid json"); return; }
        const nowMs = now();
        const err = validatePick(body, pool, host, nowMs);
        if (err) { send(400, "text/plain", err); return; }
        state.inFlight = true;

        // Everything from here to the write is guarded as one unit. Building the
        // receipt only touches rows `validatePick` already resolved, so a throw
        // here is not reachable today — but an uncaught throw inside a request
        // handler kills the process with a raw stack, leaves the browser with no
        // response and `inFlight` stuck true, and every other risky block in
        // this file already names its own failure.
        try {
          const byId = profilesById(pool);
          const seatIds = body.seats.map(String);
          const auditorId = String(body.auditor);
          const profile = String(body.profile);
          const describe = (id) => {
            const row = byId[id];
            const adapterName = row.qualification?.adapter?.name ?? null;
            return {
              id,
              model: row.model,
              vendorId: row.lineage.vendorId,
              adapter: adapterName,
              subscription: adapterContract(adapterName)?.subscriptionTransport === true,
            };
          };
          const pick = {
            schemaVersion: PICK_SCHEMA_VERSION,
            token: runToken,
            host: host.id,
            profile,
            externalSeatCount: panelProfileContract(profile).externalSeatCount,
            seats: seatIds.map(describe),
            auditor: describe(auditorId),
            prepareArgs: prepareArgsFor(profile, seatIds, auditorId, host.id),
            pickedAt: new Date(nowMs).toISOString(),
          };
          fs.writeFileSync(pickPath, `${JSON.stringify(pick, null, 2)}\n`);
          // Both flags, and both matter. `accepted` is what refuses every
          // later POST; `inFlight` must be released because its only job was to
          // hold the write window, which has now closed. Leave `inFlight`
          // latched instead and it silently does `accepted`'s work, so the
          // one-shot guarantee rests on the wrong flag and neither can be
          // tested independently.
          state.accepted = true;
          state.inFlight = false;
          send(200, "application/json", JSON.stringify({ ok: true }));
          console.log(`AGENT_COUNCIL_PICK_FILE=${pickPath}`);
          console.log(`AGENT_COUNCIL_PICK_TOKEN=${runToken}`);
          console.log(`AGENT_COUNCIL_PICK_ARGS=${pick.prepareArgs.join(" ")}`);
          onSettled(0, "AGENT_COUNCIL_PICK_OK");
        } catch (recordErr) {
          // The receipt either exists with the real pick, or the operator sees
          // an explicit failure and a non-zero exit. Never a success report.
          state.inFlight = false;
          console.error(`AGENT_COUNCIL_PICK_ERR write: ${recordErr.message}`);
          send(500, "text/plain", "could not record pick");
          onSettled(1, "AGENT_COUNCIL_PICK_ERR");
        }
      });
      return;
    }
    send(404, "text/plain", "not found");
  }

  return { state, handler, bootConfig };
}

/**
 * Pure. No I/O. An integer CLI value, or a named error.
 *
 * `Number(arg(...)) || fallback` silently swallowed an explicit `0` — and
 * `--port 0` is the ordinary way to ask for any free port — while also turning
 * unparseable garbage into the default without a word. Every other bad flag in
 * this file exits with a named error, so these do too.
 */
export function integerArg(name, raw, fallback, minimum) {
  if (raw === undefined) return { value: fallback, error: null };
  // Number("") is 0 and Number(" ") is 0. Neither is someone asking for zero,
  // so blank input is named rather than inherited as a valid value.
  if (typeof raw === "string" && raw.trim() === "") {
    return { value: null, error: `--${name} was given no value` };
  }
  const value = Number(raw);
  if (!Number.isInteger(value) || value < minimum) {
    return { value: null, error: `--${name} must be an integer >= ${minimum} (got ${JSON.stringify(raw)})` };
  }
  return { value, error: null };
}

/**
 * Removes a prior receipt at `pickPath`, or explains why it will not.
 *
 * The reference pickers hardcode their receipt path, so their unconditional
 * unlink can only ever hit their own stale file. `--out` turns that same line
 * into a delete of any path an operator or a calling agent names, and a run that
 * then times out records nothing — the named file is simply gone. So: only a
 * file that parses as one of this tool's own receipts is removed, and a failure
 * that is not "no such file" is reported rather than swallowed.
 */
export function clearPriorReceipt(pickPath, io = fs) {
  let raw;
  try {
    raw = io.readFileSync(pickPath, "utf8");
  } catch (err) {
    if (err.code === "ENOENT") return null;
    return `--out ${pickPath} is unreadable (${err.code ?? err.message})`;
  }
  let prior = null;
  try { prior = JSON.parse(raw); } catch { prior = null; }
  if (!prior || typeof prior !== "object" || prior.schemaVersion !== PICK_SCHEMA_VERSION || typeof prior.token !== "string") {
    return `--out ${pickPath} exists and is not a pick receipt this tool wrote; refusing to delete it`;
  }
  try {
    io.unlinkSync(pickPath);
  } catch (err) {
    return `could not remove the prior receipt at ${pickPath} (${err.code ?? err.message})`;
  }
  return null;
}

// Every startup guard below reports the same way: name the problem, exit 1.
// Collected here once so `main()` reads as a sequence of checks rather than a
// sequence of copies of this same two-line report-and-exit.
function failFast(message) {
  console.error(`AGENT_COUNCIL_PICK_ERR ${message}`);
  process.exit(1);
}

function main() {
  const hostArg = arg("host", undefined);
  const profileArg = arg("profile", "full");
  const pickPath = path.resolve(arg("out", DEFAULT_PICK_PATH));
  const noOpen = hasFlag("no-open");
  const runToken = crypto.randomBytes(16).toString("hex");

  const timeout = integerArg("timeout", arg("timeout", undefined), 1800000, 1);
  const port = integerArg("port", arg("port", undefined), 3165, 0);
  for (const parsed of [timeout, port]) {
    if (parsed.error) failFast(parsed.error);
  }
  const timeoutMs = timeout.value;
  const startPort = port.value;

  let pool;
  try {
    pool = JSON.parse(fs.readFileSync(ROSTER_PATH, "utf8"));
  } catch (err) {
    failFast(`roster: ${err.message}`);
  }

  const poolErr = validatePool(pool);
  if (poolErr) failFast(`roster: ${poolErr}`);

  const { host, error: hostErr } = resolveHost(pool, hostArg);
  if (hostErr) failFast(hostErr);

  if (!panelProfileContract(profileArg)) {
    failFast(`unknown --profile ${profileArg} (${panelProfileNames().join("|")})`);
  }

  const pathErr = receiptPathBlocker(pickPath);
  if (pathErr) failFast(pathErr);

  const priorErr = clearPriorReceipt(pickPath);
  if (priorErr) failFast(priorErr);

  let settled = false;
  function finish(code, line) {
    if (settled) return;
    settled = true;
    if (line) console.log(line);
    server.close(() => process.exit(code));
    setTimeout(() => process.exit(code), 500);
  }

  const surface = createPickSurface({
    pool,
    host,
    profileName: profileArg,
    pickPath,
    runToken,
    onSettled: finish,
  });
  const server = http.createServer(surface.handler);

  // Registered once, outside `listen`, and deliberately not passed as the
  // `listen(port, cb)` callback: that form attaches `cb` as a one-shot
  // `listening` listener, and a bind that fails with EADDRINUSE never consumes
  // it. Each retry then added another, so binding after N busy ports printed
  // this whole banner N+1 times — and the SKILL tells the calling agent to parse
  // these exact lines off stdout.
  server.once("listening", () => {
    const address = server.address();
    const bound = address && typeof address === "object" ? address.port : startPort;
    surface.state.boundPort = bound;
    // No `&` in this URL. It is also printed for the operator to open by hand,
    // and pasted into `cmd.exe`'s `start` an `&` truncates everything after it.
    // (This process launches the browser through PowerShell `Start-Process`
    // with a quoted argument, which is unaffected — the hazard is the manual
    // path, not this one.)
    const url = `http://127.0.0.1:${bound}/agent-council-console.html?pick=1`;
    console.log(`AGENT_COUNCIL_PICK_URL=${url}`);
    console.log(`AGENT_COUNCIL_PICK_FILE=${pickPath}`);
    console.log(`AGENT_COUNCIL_PICK_TOKEN=${runToken}`);
    console.log(`AGENT_COUNCIL_PICK_HOST=${host.id} (${host.lineage.vendorId})`);
    if (!noOpen) openBrowser(url);
    setTimeout(() => finish(2, "AGENT_COUNCIL_PICK_TIMEOUT"), timeoutMs);
  });

  function listen(attempt) {
    server.once("error", (err) => {
      // Port 0 already means "any free port", so there is nothing to walk up to.
      if (err && err.code === "EADDRINUSE" && startPort !== 0 && attempt < startPort + 10) listen(attempt + 1);
      else {
        console.error(`AGENT_COUNCIL_PICK_ERR ${err.message}`);
        process.exit(1);
      }
    });
    server.listen(attempt, "127.0.0.1");
  }

  listen(startPort);
}
