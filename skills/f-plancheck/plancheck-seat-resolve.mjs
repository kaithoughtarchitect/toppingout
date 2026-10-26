#!/usr/bin/env node
/**
 * Deterministic unattended seat resolver for `f-plancheck` (shaped like the cross-review seat rule).
 *
 * `f-plancheck`'s normal seat route is an operator-driven one-shot HTML picker on 127.0.0.1 — there
 * is no operator in an unattended run (e.g. a CI job), so that route cannot fire. This file is
 * the unattended alternative: given a `--host` (the family of the session doing the work) and a
 * `--player` (the family being reviewed/read for), it picks exactly one independent cross-family
 * seat from the roster's own `cost:"subscription"` rows and writes a seats file the *existing*,
 * *unchanged* `plancheck-dispatch.mjs` already knows how to consume (`resolveSeats`,
 * in `plancheck-dispatch.mjs`). The dispatcher is roster-authoritative — a seats file can
 * only ever supply `{id, door}`, never a model, vendor, or reasoning effort — so this resolver's
 * entire job is generating those two fields deterministically. It never launches the picker
 * (never self-fills a "pick" — that would be self-authorization wearing an audit trail's costume)
 * and never re-implements the family-resolution rule that `plancheck-pick.mjs` already owns:
 * `resolvePlayerVendor` and `validateRoster` are imported from that sibling file, not duplicated.
 *
 * Seat rule (ported verbatim from `scripts/cross-review-dispatch.mjs`'s
 * `selectReviewerSeat`, operator ruling 2026-09-23: "if claude is building use codex and if codex
 * is building use claude, just run auto"):
 *   host Anthropic family (claude) -> seat sol   (OpenAI / codex CLI)
 *   host OpenAI family (codex)     -> seat claude (Anthropic / claude CLI)
 *   any other resolvable host      -> seat claude, falling back to sol
 * Then drop any candidate whose roster `vendor` is in `new Set([hostVendor, playerVendor])`,
 * whose `cost !== "subscription"`, whose `door === "OpenRouter"`, or whose `pickableAs` lacks
 * `"panel"`. Nothing survives -> refuse. `grok` is never a candidate (operator ruling: binary
 * claude<->codex only) and no `cost:"openrouter"` row — nor any `OpenRouter`-door row, whatever
 * its `cost` field claims — is ever a candidate (an unattended run cannot ask
 * before spending, so it may only seat a $0-marginal-cost subscription CLI door).
 *
 * Deliberate strengthening over the cross-review seat rule: an unresolvable `--host` or `--player`
 * is a REFUSAL here, not that rule's "unrecognized/empty host -> claude" fallback. `f-plancheck/SKILL.md`'s existing law for an
 * unresolvable Player is "ask" — an unattended run cannot ask, so it refuses instead of guessing a
 * family it could not identify. That rule's "any other host" branch survives unchanged for any host that
 * *does* resolve to a family outside {Anthropic, OpenAI}.
 *
 * This resolver spawns nothing, probes no CLI, and reaches no network. The dispatcher's own
 * per-seat preflight (in `plancheck-dispatch.mjs`'s `main`) is the single source of availability
 * truth; a second availability check here could disagree with it and would only add a second,
 * possibly-stale, authority. Every eligible seat this resolver proposes is handed to the
 * dispatcher exactly as-is; the dispatcher decides whether the door actually answers.
 *
 * Usage:
 *   node plancheck-seat-resolve.mjs --host <claude|codex|roster-resolvable id> \
 *     --player <id> --out <path/to/seats.json>
 *   node plancheck-seat-resolve.mjs --self-test
 *
 * Exit codes: 0 ok (seats file written; the `--out` parent directory is created first if it does
 * not already exist — a fresh scratch directory must not require the caller to pre-create it). 1
 * usage error — a malformed --flag (empty/missing/option-shaped value, or a duplicated flag; see
 * `arg()`), or a roster that is unreadable / fails `validateRoster` (no seats file written). 2
 * refusal — no independent cross-family subscription seat available, or `--host`/`--player` did
 * not resolve to a vendor family (no seats file written). 4 internal error, via the
 * `isMainModule()` error boundary at the bottom of this file (e.g. `--out` naming an existing
 * directory rather than a file, or a permission-denied write) — never exit 0 on a fault. Exit
 * codes (--self-test): 0 every check passed, 1 otherwise.
 */
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { resolvePlayerVendor, validateRoster } from "./plancheck-pick.mjs";

const DIR = dirname(fileURLToPath(import.meta.url));
const ROSTER_PATH = join(DIR, "plancheck-roster.json");

// The only two candidates this resolver may ever propose (operator ruling: claude<->codex only,
// never grok, never an OpenRouter row). Both are `cost:"subscription"` rows in the shipped roster;
// the `cost`/`door`/`pickableAs` checks in `selectUnattendedSeat` still gate them explicitly
// rather than trusting that fact silently, so a future roster edit that changed either row's
// `cost` OR `door` would be caught here, not silently seat a metered door. `door` is the field
// that actually decides where the money goes — a row can claim `cost:"subscription"` while its
// `door` reads `"OpenRouter"`, and `cost` alone would not catch that.
const CANDIDATE_IDS_FOR_ANTHROPIC_HOST = ["sol"];
const CANDIDATE_IDS_FOR_OPENAI_HOST = ["claude"];
const CANDIDATE_IDS_FOR_OTHER_HOST = ["claude", "sol"];

/**
 * Pure. No I/O (argv is injectable for `--self-test`; defaults to `process.argv`). Reads a
 * `--name value` pair off argv.
 *
 * B5 fix, ported from `scripts/cross-review-dispatch.mjs`'s `arg()` (NOT `plancheck-pick.mjs`'s
 * `arg()`, which silently collapses a present-but-empty value onto the "absent" fallback branch —
 * exactly the defect this refuses). PRESENCE and VALUE are handled separately:
 *   - Absent entirely -> `fallback` (the only case that may use it).
 *   - Present but the next token is missing, empty, or itself looks like another option
 *     (`--`-prefixed, e.g. `--out --host claude` silently binding `outArg = "--host"`) -> throw.
 *   - Present more than once -> throw, rather than silently taking the first occurrence.
 * @param {string} name flag name without the leading `--`.
 * @param {string} [fallback] value to use when the flag is not supplied at all.
 * @param {string[]} [argv] injectable for tests; defaults to `process.argv`.
 */
export function arg(name, fallback, argv = process.argv) {
  const flag = `--${name}`;
  const indices = [];
  for (let idx = 0; idx < argv.length; idx += 1) {
    if (argv[idx] === flag) indices.push(idx);
  }
  if (indices.length === 0) return fallback;
  if (indices.length > 1) {
    throw new Error(
      `${flag} was supplied ${indices.length} times — refusing rather than silently taking the ` +
        `first occurrence (this codebase declines to guess which one applies)`,
    );
  }
  const value = argv[indices[0] + 1];
  if (value === undefined || value === "" || value.startsWith("--")) {
    const got = value === undefined ? "nothing (flag was the last argument)" : JSON.stringify(value);
    throw new Error(
      `${flag} requires a non-empty value, got ${got} — omit the flag entirely to use its default, ` +
        `or supply a real value`,
    );
  }
  return value;
}

function hasFlag(name, argv = process.argv) {
  return argv.includes(`--${name}`);
}

function isMainModule() {
  try {
    return resolve(fileURLToPath(import.meta.url)) === resolve(process.argv[1] || "");
  } catch {
    return false;
  }
}

/**
 * Shared shape for the `--host`/`--player` vendor-resolution refusal below: an unattended run
 * cannot ask, so an unresolved family is a refusal rather than a guess (see file header,
 * "Deliberate strengthening"). `note` carries the host branch's extra seat-rule-divergence callout; the
 * player branch has none. Text is byte-identical to the two inline blocks this replaces.
 * @param {string} flagName flag name without the leading `--` ("host" or "player").
 * @param {unknown} value the raw --host/--player value that failed to resolve.
 * @param {string} [note] appended verbatim after "guessing" (only the host branch uses this).
 */
function refuseUnresolvedVendor(flagName, value, note = "") {
  return {
    ok: false,
    seat: null,
    reason:
      `--${flagName} ${JSON.stringify(value)} did not resolve to a roster vendor family — an ` +
      `unattended run cannot ask, so this refuses rather than guessing${note}`,
  };
}

/**
 * Pure. No I/O. No spawn, no network, no CLI-availability probe — the dispatcher's own preflight
 * is the single source of availability truth (see file header). Returns
 * `{ ok: true, seat: { id, door }, reason: null }` or `{ ok: false, seat: null, reason }`.
 * `seat` carries EXACTLY the two keys the roster-authoritative dispatcher reads
 * (`resolveSeats` in `plancheck-dispatch.mjs`) — never a model, vendor, or effort field.
 * @param {{ host: unknown, player: unknown, roster: object }} input
 */
export function selectUnattendedSeat({ host, player, roster }) {
  const hostVendor = resolvePlayerVendor(host, roster);
  if (!hostVendor) {
    return refuseUnresolvedVendor("host", host, " (deliberate strengthening over the cross-review seat rule)");
  }
  const playerVendor = resolvePlayerVendor(player, roster);
  if (!playerVendor) {
    return refuseUnresolvedVendor("player", player);
  }

  let candidateOrder;
  if (hostVendor === "Anthropic") candidateOrder = CANDIDATE_IDS_FOR_ANTHROPIC_HOST;
  else if (hostVendor === "OpenAI") candidateOrder = CANDIDATE_IDS_FOR_OPENAI_HOST;
  else candidateOrder = CANDIDATE_IDS_FOR_OTHER_HOST;

  const excludedVendors = new Set([hostVendor, playerVendor]);
  const byId = Object.fromEntries((roster.models || []).map((m) => [m.id, m]));

  for (const id of candidateOrder) {
    const row = byId[id];
    if (!row) continue; // roster does not carry the expected id at all — not a candidate
    if (row.cost !== "subscription") continue; // never a metered door, unattended (cannot ask before spending)
    if (row.door === "OpenRouter") continue; // never a metered door, whatever the row claims about `cost`
    if (!Array.isArray(row.pickableAs) || !row.pickableAs.includes("panel")) continue;
    if (excludedVendors.has(row.vendor)) continue; // host's or Player's own family
    return { ok: true, seat: { id: row.id, door: row.door }, reason: null };
  }

  return {
    ok: false,
    seat: null,
    reason:
      `no independent cross-family subscription seat for host ${JSON.stringify(host)} ` +
      `(vendor ${hostVendor}) / player ${JSON.stringify(player)} (vendor ${playerVendor}) — ` +
      `excluded families: ${[...excludedVendors].join(", ")}`,
  };
}

function main() {
  if (hasFlag("self-test")) {
    selfTest();
    return;
  }

  let host, player, outArg;
  try {
    host = arg("host");
    player = arg("player");
    outArg = arg("out");
  } catch (err) {
    console.error(`PLANCHECK_SEAT_RESOLVE_ERR ${err instanceof Error ? err.message : String(err)}`);
    process.exit(1);
    return;
  }

  if (!host || !player || !outArg) {
    console.error("PLANCHECK_SEAT_RESOLVE_ERR missing required --host/--player/--out");
    process.exit(1);
    return;
  }

  let roster;
  try {
    roster = JSON.parse(readFileSync(ROSTER_PATH, "utf8"));
  } catch (err) {
    console.error(`PLANCHECK_SEAT_RESOLVE_ERR roster: ${err instanceof Error ? err.message : String(err)}`);
    process.exit(1);
    return;
  }

  const rosterErr = validateRoster(roster);
  if (rosterErr) {
    console.error(`PLANCHECK_SEAT_RESOLVE_ERR roster: ${rosterErr}`);
    process.exit(1);
    return;
  }

  // f-plancheck Law A parity (plancheck-pick.mjs:229, "Do not reuse a leftover pick file"): clear
  // --out BEFORE selecting, not after a success — unconditionally, regardless of whether this run
  // goes on to succeed or refuse. A refusal below must not leave a PREVIOUS run's seats file
  // sitting at this path — the file's existence has to mean what its contents claim. `force: true`
  // makes a missing path (the common case) a silent no-op. It does NOT swallow every fault: if
  // `--out` names an existing DIRECTORY, `rmSync` without `recursive: true` throws here
  // (`ERR_FS_EISDIR`, confirmed empirically on this platform; the directory is left untouched) —
  // that is a genuine internal error, not a usage error, and is deliberately left unguarded so it
  // surfaces via the isMainModule() error boundary at the bottom of this file (exit 4), same
  // reasoning as the writeFileSync below.
  const outPath = resolve(outArg);
  rmSync(outPath, { force: true });

  const result = selectUnattendedSeat({ host, player, roster });
  if (!result.ok) {
    // No file written on refusal — not an empty one, not a partial one, and the unlink above
    // already cleared anything a previous run left at this exact path. Deliberately no directory
    // creation above this branch either: creating `--out`'s parent is a SUCCESS-path side effect
    // only (see below) — a refused run must not touch the filesystem beyond that unlink.
    console.error(`PLANCHECK_SEAT_RESOLVE_REFUSED ${result.reason}`);
    process.exit(2);
    return;
  }

  const hostVendor = resolvePlayerVendor(host, roster);
  const playerVendor = resolvePlayerVendor(player, roster);
  const payload = { seats: [{ id: result.seat.id, door: result.seat.door }] };

  // On success only: create the --out parent directory if it does not already exist yet, exactly
  // as originally specified — a fresh scratch directory (exactly what a CI job hands
  // this resolver on its first run) must not require the caller to have pre-created it. `recursive:
  // true` makes an already-existing parent a silent no-op, matching mkdirSync's own documented
  // behavior.
  mkdirSync(dirname(outPath), { recursive: true });

  // Deliberately NOT wrapped in try/catch: a write failure here — now that the parent directory is
  // guaranteed to exist — is a genuine internal fault, not a usage error (e.g. a permission-denied
  // write, or the OS refusing to create the file for some other reason). It bubbles to the
  // isMainModule() error boundary at the bottom of this file, which exits 4 (mirrors
  // `scripts/cross-review-dispatch.mjs`'s documented reasoning for the same split).
  writeFileSync(outPath, JSON.stringify(payload), "utf8");

  console.log(
    `PLANCHECK_SEAT_RESOLVE_OK ${result.seat.id} ${result.seat.door} host:${hostVendor} player:${playerVendor}`,
  );
  process.exit(0);
}

// ── self-test (offline, no CLI probe, no spawn, no model call, no network) ─────────────────────

function selfTest() {
  let passed = 0;
  let failed = 0;
  function check(name, cond, detail = "") {
    if (cond) {
      passed += 1;
      console.log(`PASS ${name}`);
    } else {
      failed += 1;
      console.error(`FAIL ${name}${detail ? ` — ${detail}` : ""}`);
    }
  }

  let roster;
  try {
    roster = JSON.parse(readFileSync(ROSTER_PATH, "utf8"));
  } catch (err) {
    console.error(`PLANCHECK_SEAT_RESOLVE_ERR self-test could not read the real roster: ${err.message}`);
    process.exit(1);
    return;
  }
  const rosterErr = validateRoster(roster);
  if (rosterErr) {
    console.error(`PLANCHECK_SEAT_RESOLVE_ERR self-test: real roster failed validateRoster: ${rosterErr}`);
    process.exit(1);
    return;
  }

  // Fixture cases below all start from a deep copy of the real roster so they can mutate one row
  // without disturbing the real-roster cases sharing this run.
  function cloneRoster() {
    return JSON.parse(JSON.stringify(roster));
  }

  // ── Seat rule, ported + adapted (9 cases against the REAL shipped roster) ──────────────────────
  // "Unavailable" in the cross-review seat rule (a probed CLI --version failure) has no counterpart here — this design
  // never probes. The closest analogue is a candidate being filtered out (excluded vendor, or a
  // fixture roster where the row is not eligible), so cases below use that instead of a boolean.
  // Case 4 deliberately diverges from that rule's own "unrecognized/empty host -> claude" fallback — see
  // the file header's "Deliberate strengthening" note; that is intentional, not a missed port.
  check(
    "seat rule 1: host Anthropic family (claude), independent player -> sol/codex CLI",
    (() => {
      const r = selectUnattendedSeat({ host: "claude", player: "grok", roster });
      return r.ok === true && r.seat.id === "sol" && r.seat.door === "codex CLI";
    })(),
  );
  check(
    "seat rule 2: host OpenAI family (codex), independent player -> claude/claude CLI",
    (() => {
      const r = selectUnattendedSeat({ host: "codex", player: "grok", roster });
      return r.ok === true && r.seat.id === "claude" && r.seat.door === "claude CLI";
    })(),
  );
  check(
    "seat rule 3: any other resolvable host family (grok/xAI), independent player -> claude preferred",
    (() => {
      const r = selectUnattendedSeat({ host: "grok", player: "qwen", roster });
      return r.ok === true && r.seat.id === "claude";
    })(),
  );
  check(
    "seat rule 4 (adapted): unresolvable host is a REFUSAL, not the cross-review 'any other host -> claude'",
    selectUnattendedSeat({ host: "definitely-not-a-real-vendor-family-000", player: "grok", roster }).ok === false,
  );
  check(
    "seat rule 5: any-other-host, player is Anthropic family -> claude excluded, falls back to sol",
    (() => {
      const r = selectUnattendedSeat({ host: "grok", player: "claude-opus-5", roster });
      return r.ok === true && r.seat.id === "sol";
    })(),
  );
  check(
    "seat rule 6: host claude, player OpenAI family -> only candidate (sol) excluded -> ok:false, seat:null",
    (() => {
      const r = selectUnattendedSeat({ host: "claude", player: "gpt-6-astra", roster });
      return r.ok === false && r.seat === null;
    })(),
  );
  check(
    "seat rule 7: host codex, player Anthropic family -> refuses same-family fallback, not codex-reviews-codex",
    (() => {
      const r = selectUnattendedSeat({ host: "codex", player: "claude-opus-5", roster });
      return r.ok === false && r.seat === null;
    })(),
  );
  check(
    "seat rule 8: neither subscription candidate eligible (fixture) -> ok:false regardless of host",
    (() => {
      const fixture = cloneRoster();
      for (const m of fixture.models) {
        if (m.id === "claude" || m.id === "sol") m.cost = "openrouter";
      }
      const r = selectUnattendedSeat({ host: "grok", player: "qwen", roster: fixture });
      return r.ok === false && r.seat === null;
    })(),
  );
  check(
    "seat rule 9: host resolution is case-insensitive (resolvePlayerVendor lowercases)",
    (() => {
      const r = selectUnattendedSeat({ host: "Claude", player: "grok", roster });
      return r.ok === true && r.seat.id === "sol";
    })(),
  );

  // Unresolvable --player is the same strengthening as unresolvable --host.
  check(
    "unresolvable --player is a refusal, not a no-exclusion pass",
    selectUnattendedSeat({ host: "claude", player: "definitely-not-a-real-vendor-family-000", roster }).ok === false,
  );

  // ── pickableAs guard (mutation-hardened) ────────────────────────────────────────────────────
  // Every row in the shipped roster today happens to carry pickableAs:["panel"], so this half of
  // the drop filter (`!Array.isArray(row.pickableAs) || !row.pickableAs.includes("panel")`) is
  // unreachable against the real roster alone — a guard that rots silently, exactly this work's
  // recurring defect class. Fixture rosters make it reachable: mutate the row that WOULD be
  // chosen (sol, under an Anthropic host, the only candidate in that branch) so it fails the
  // check, and assert the resolver refuses rather than seating it anyway.
  check(
    'pickableAs guard: sol excluded when pickableAs is "[]" -> refusal, not seated anyway',
    (() => {
      const fixture = cloneRoster();
      const sol = fixture.models.find((m) => m.id === "sol");
      sol.pickableAs = [];
      const r = selectUnattendedSeat({ host: "claude", player: "grok", roster: fixture });
      return r.ok === false && r.seat === null;
    })(),
  );
  check(
    "pickableAs guard: sol excluded when pickableAs is missing entirely (Array.isArray half) -> refusal",
    (() => {
      const fixture = cloneRoster();
      const sol = fixture.models.find((m) => m.id === "sol");
      delete sol.pickableAs;
      const r = selectUnattendedSeat({ host: "claude", player: "grok", roster: fixture });
      return r.ok === false && r.seat === null;
    })(),
  );
  check(
    "pickableAs guard: sol excluded when pickableAs is a non-array value (Array.isArray half) -> refusal",
    (() => {
      const fixture = cloneRoster();
      const sol = fixture.models.find((m) => m.id === "sol");
      sol.pickableAs = "panel"; // a string, not an array
      const r = selectUnattendedSeat({ host: "claude", player: "grok", roster: fixture });
      return r.ok === false && r.seat === null;
    })(),
  );

  // ── money guard (Fix 1, mutation-hardened): `door` decides, not `cost` alone ───────────────────
  // Proves the clause added immediately after the `cost` check actually bites: a roster edit that
  // moved sol onto an OpenRouter door while leaving `cost: "subscription"` untouched must still be
  // refused, not seated. `door` is the field the dispatcher's `resolveSeats` actually reads to pick
  // a transport (`plancheck-dispatch.mjs`'s `DOOR_SLUG`/model resolution) — `cost` alone cannot be
  // trusted to agree with it after a future edit, and before this guard existed this exact fixture
  // dispatched through OpenRouter with a live model slug.
  check(
    'money guard: sol refused when its door reads "OpenRouter" though cost still reads "subscription"',
    (() => {
      const fixture = cloneRoster();
      const sol = fixture.models.find((m) => m.id === "sol");
      sol.door = "OpenRouter";
      sol.slug = "openai/gpt-6-astra";
      const r = selectUnattendedSeat({ host: "claude", player: "grok", roster: fixture });
      return r.ok === false && r.seat === null;
    })(),
  );

  // ── Vendor-exclusion matrix over every `hosts` key ───────────────────────────────────────────
  // player = "qwen" (Alibaba) for every host: independent of every hosts-family vendor
  // (Anthropic/OpenAI/xAI), so all three host cases here resolve to a seat and the roster-derived
  // fields (cost/effort/vendor/door) can be asserted for "every host case" as required.
  const matrixPlayer = "qwen";
  const matrixPlayerVendor = resolvePlayerVendor(matrixPlayer, roster);
  for (const hostId of Object.keys(roster.hosts)) {
    const hostVendor = roster.hosts[hostId].vendor;
    const r = selectUnattendedSeat({ host: hostId, player: matrixPlayer, roster });
    check(`matrix[${hostId}]: resolves to a seat for an independent player`, r.ok === true && r.seat !== null);
    if (r.ok) {
      const row = roster.models.find((m) => m.id === r.seat.id);
      check(
        `matrix[${hostId}]: chosen seat vendor excludes host+player families`,
        !!row && row.vendor !== hostVendor && row.vendor !== matrixPlayerVendor,
      );
      check(`matrix[${hostId}]: chosen seat cost is "subscription"`, !!row && row.cost === "subscription");
      check(
        `matrix[${hostId}]: chosen seat is pickableAs "panel" (a guard selectUnattendedSeat itself enforces, not just roster hygiene)`,
        !!row && Array.isArray(row.pickableAs) && row.pickableAs.includes("panel"),
      );
      check(`matrix[${hostId}]: chosen seat door is never "OpenRouter"`, !!row && row.door !== "OpenRouter");
      check(
        `matrix[${hostId}]: seat object has exactly {id,door} keys`,
        JSON.stringify(Object.keys(r.seat).sort()) === JSON.stringify(["door", "id"]),
      );
    }
  }

  // No openrouter-cost id is ever emitted — structural: the only ids `selectUnattendedSeat` can
  // ever place in `candidateOrder` are "claude" and "sol", but assert it directly too rather than
  // trust the construction silently.
  check(
    "no openrouter-cost id is ever emitted across host cases (candidates fixed to {claude, sol})",
    ["claude", "codex", "grok"]
      .map((hostId) => selectUnattendedSeat({ host: hostId, player: "qwen", roster }))
      .every((r) => !r.ok || ["claude", "sol"].includes(r.seat.id)),
  );

  // ── arg() presence-vs-value (B5) ────────────────────────────────────────────────────────────
  check(
    "arg: flag absent entirely returns the fallback",
    arg("nope", "fallback-value", ["node", "script"]) === "fallback-value",
  );
  check(
    "arg: flag present with a real value returns that value",
    arg("host", "fallback", ["node", "script", "--host", "claude"]) === "claude",
  );
  check(
    'arg: --out "" refuses rather than silently falling back to a default',
    (() => {
      try {
        arg("out", "/default/seats.json", ["node", "script", "--out", ""]);
        return false;
      } catch (err) {
        return /non-empty value/.test(err.message);
      }
    })(),
  );
  check(
    'arg: an option-shaped value ("--out --host claude") refuses rather than swallowing it',
    (() => {
      try {
        arg("out", undefined, ["node", "script", "--out", "--host", "claude"]);
        return false;
      } catch {
        return true;
      }
    })(),
  );
  check(
    "arg: a duplicated flag refuses rather than silently taking the first occurrence",
    (() => {
      try {
        arg("host", undefined, ["node", "script", "--host", "claude", "--host", "codex"]);
        return false;
      } catch {
        return true;
      }
    })(),
  );

  console.log(
    failed === 0
      ? `\nPLANCHECK_SEAT_RESOLVE_SELFTEST_OK ${passed}/${passed}`
      : `\nPLANCHECK_SEAT_RESOLVE_SELFTEST_FAILED ${passed} passed, ${failed} failed`,
  );
  process.exit(failed === 0 ? 0 : 1);
}

// Error boundary (mirrors `scripts/cross-review-dispatch.mjs`'s own): without it, an internal
// fault (e.g. `writeFileSync` failing on a missing/read-only `--out` parent) surfaces as an
// uncaught stack and Node's default exit 1 — but this file's documented contract reserves 1 for a
// USAGE error, not an internal one. Exit 4 keeps that contract honest while still failing loudly.
if (isMainModule()) {
  try {
    main();
  } catch (err) {
    process.stderr.write(
      `PLANCHECK_SEAT_RESOLVE_INTERNAL_ERR ${err instanceof Error ? err.stack || err.message : String(err)}\n`,
    );
    process.exit(4);
  }
}
