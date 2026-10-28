#!/usr/bin/env node
/**
 * Bounded preflight + parallel headless dispatch of every picked f-plancheck
 * seat. Writes one log per seat and a `dispatch.json` receipt. Never spawns
 * a seat whose preflight failed; retries a failed attempt once, then omits
 * the seat by name. Never prints, logs, or persists any environment value —
 * `OPENROUTER_API_KEY` is passed through `process.env` untouched and never
 * inspected beyond a presence check. Every stdout/stderr artifact is passed
 * through `scrubSecrets` before it touches disk (a seat's read-only tools can
 * still open a local `.env`; a key echoed into findings must not persist).
 *
 *   node .claude/skills/f-plancheck/plancheck-dispatch.mjs --assignment <file> --seats <seats.json> --out <dir> [--cwd <repo>] [--timeout <ms>] [--dry-run] [--preflight-only]
 */
import { spawn, spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROSTER_PATH = path.join(DIR, "plancheck-roster.json");

const DOOR_SLUG = Object.freeze({
  "codex CLI": "codex",
  "claude CLI": "claude",
  "grok CLI": "grok",
  OpenRouter: "openrouter",
});

const CLI_NAME_FOR_DOOR = Object.freeze({
  codex: "codex",
  claude: "claude",
  grok: "grok",
  openrouter: "pi",
});

const MAX_OUTPUT_BYTES = 16 * 1024 * 1024;
// Independent of MAX_OUTPUT_BYTES (B4) — stderr TRUNCATES past this cap
// (stops appending, keeps the process alive) instead of killing the
// process the way an oversized stdout does.
const MAX_STDERR_BYTES = 16 * 1024 * 1024;
const PREFLIGHT_TIMEOUT_MS = 20_000;
const PREFLIGHT_MAX_BYTES = 1024 * 1024;
// After a best-effort kill (taskkill / SIGTERM+SIGKILL), how long to wait
// for `close` before giving up and resolving the attempt anyway (B6).
const KILL_GRACE_MS = 20_000;

// S3: every child spawnCapture starts is tracked here for the lifetime of
// the process, so a SIGINT/SIGTERM to this dispatch process (handleInterrupt,
// near main()) can kill every in-flight child before writing the receipt and
// exiting — otherwise a programmatic interrupt leaves e.g. an OpenRouter
// seat's underlying process running (and spending) after dispatch itself has
// already exited 130. Entries are `{ child, killTree }` — `killTree` is the
// same per-child kill routine spawnCapture already uses on timeout/overflow.
const LIVE_CHILDREN = new Set();

/**
 * `--permission-mode plan` already allows grok's built-in read-only shell
 * set (git reads, listing) headless — live-probed 2026-09-02 (probe outputs kept in the
 * source workspace, not shipped):
 * plan mode + this narrower allowlist (the non-git CLI --help/--version/
 * listing commands the assignment names) reached `stopReason: "end_turn"`
 * on the real fixture assignment. An earlier `--permission-mode dontAsk`
 * variant (lacking plan mode's built-in read-only set) cancelled sooner —
 * disproved, not used. `--disallowed-tools` blocks writes outright.
 * Exported so SKILL.md can cite it.
 */
export const GROK_READ_ONLY_ALLOW_RULES = Object.freeze([
  "Bash(node --version)",
  "Bash(node -v)",
  "Bash(npm --version)",
  "Bash(codex --help)",
  "Bash(codex exec --help)",
  "Bash(codex --version)",
  "Bash(claude --help)",
  "Bash(claude --version)",
  "Bash(grok --help)",
  "Bash(grok --version)",
  "Bash(grok models)",
  "Bash(pi --help)",
  "Bash(pi --version)",
  "Bash(pi --list-models:*)",
]);

// Same detector list as .claude/skills/agent-council/scripts/agent-council.mjs:61-70
// (duplicated here, not imported — this file has no dependency on that one).
const SECRET_DETECTORS = Object.freeze([
  /-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----/,
  /\bsk-or-v1-[A-Za-z0-9_-]{20,}\b/,
  /\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b/,
  /\bsk-ant-[A-Za-z0-9_-]{20,}\b/,
  /\bgh[pousr]_[A-Za-z0-9]{20,}\b/,
  /\bAKIA[0-9A-Z]{16}\b/,
  /\bxox[baprs]-[A-Za-z0-9-]{20,}\b/,
  /\bBearer\s+[A-Za-z0-9._~-]{32,}\b/i,
]);

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
}

function isMainModule() {
  try {
    return path.resolve(fileURLToPath(import.meta.url)) === path.resolve(process.argv[1] || "");
  } catch {
    return false;
  }
}

/** Pure. No I/O. Redacts any recognizable secret shape found in `text`. */
export function scrubSecrets(text) {
  if (typeof text !== "string") return text;
  let out = text;
  for (const re of SECRET_DETECTORS) {
    const flags = re.flags.includes("g") ? re.flags : `${re.flags}g`;
    out = out.replace(new RegExp(re.source, flags), "[REDACTED]");
  }
  return out;
}

// H1 (2026-09-02 5c hunter): error-context patterns only — a bare `\b429\b`,
// unqualified "usage limit" / "rate limit" / "too many requests" matched
// transcript prose and quoted source lines (e.g. a grep dump of `:429:` from
// an unrelated file). Each pattern below requires the line to also carry an
// error marker, except the two exact vendor literals, which are unambiguous
// on their own regardless of prefix (S2).
const USAGE_LIMIT_EXACT_RES = Object.freeze([
  /you've hit your usage limit/i,
  /\b429 Too Many Requests\b/i,
]);
const USAGE_LIMIT_SIGNAL_RES = Object.freeze([
  /\bHTTP 429\b/,
  /\bstatus(?: code)?\s*[:=]?\s*429\b/i,
  /\brate[ _-]?limit(?:ed| exceeded)\b/i,
]);
// S2: the marker may appear anywhere in the line (a timestamp/level prefix
// like `2026-09-02T12:00:00Z ERROR …`, or an inline `stream error: …`), not
// only at line start.
const ERROR_MARKER_RE = /\b(ERROR|Error|error|fatal|FATAL)\b|\[error\]/;

/**
 * Pure. No I/O. Scans the combined stderr+stdout lines from the end
 * backwards for a quota / rate limit shape, returning the LAST matching
 * line — trimmed and truncated to 200 chars — or null (B3, H1). A line
 * matches when it contains one of the exact vendor literals (`You've hit
 * your usage limit`, `429 Too Many Requests`; case-insensitive, any
 * prefix/position), or when it matches one of the remaining quota/rate-limit
 * signal patterns AND carries an error marker anywhere in the line — this
 * excludes transcript prose ("quota / rate limit errors must be surfaced")
 * and quoted source lines (`file.mjs:429:    choiceId,`) that merely mention
 * the shape without being an actual error line. Checked before deciding
 * whether to retry: a quota door is omitted, never retried into a second
 * hour against the same limit.
 */
export function detectUsageLimit(stdoutText, stderrText) {
  const combined = `${stderrText || ""}\n${stdoutText || ""}`;
  const lines = combined.split(/\r?\n/);
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i];
    if (USAGE_LIMIT_EXACT_RES.some((re) => re.test(line))) return line.trim().slice(0, 200);
    if (ERROR_MARKER_RE.test(line) && USAGE_LIMIT_SIGNAL_RES.some((re) => re.test(line))) {
      return line.trim().slice(0, 200);
    }
  }
  return null;
}

/** Pure. No I/O. Lowercase; every char outside [a-z0-9.-] becomes "-". */
export function sanitizeModel(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9.-]/g, "-");
}

/** Pure. No I/O. `read-<doorSlug>-<sanitizeModel(model)>` — shared stem for every artifact name. */
function baseNameFor(seat) {
  return `read-${seat.doorSlug}-${sanitizeModel(seat.model)}`;
}

/** Pure. No I/O. `<baseNameFor(seat)>.log`. */
export function logNameFor(seat) {
  return `${baseNameFor(seat)}.log`;
}

/**
 * Pure. No I/O. Resolves a copied pick file against the roster.
 * Returns { ok: true, seats: [...] } or { ok: false, reason }.
 * Every returned seat: { id, name, vendor, door, doorSlug, model, log }.
 */
export function resolveSeats(seatsFile, roster) {
  if (!seatsFile || typeof seatsFile !== "object") return { ok: false, reason: "seats file missing" };
  if (!Array.isArray(seatsFile.seats) || seatsFile.seats.length === 0) {
    return { ok: false, reason: "seats must be a non-empty array" };
  }
  const byId = Object.fromEntries((roster.models || []).map((m) => [m.id, m]));

  const resolved = [];
  const seenLogNames = new Map();
  for (const raw of seatsFile.seats) {
    if (!raw || raw.id == null) return { ok: false, reason: "seat missing id" };
    const id = String(raw.id);
    const row = byId[id];
    if (!row) return { ok: false, reason: `unknown roster id ${id}` };
    if (raw.door !== row.door) {
      return { ok: false, reason: `seat ${id} door "${raw.door}" does not match roster door "${row.door}"` };
    }
    const doorSlug = DOOR_SLUG[row.door];
    if (!doorSlug) return { ok: false, reason: `seat ${id} has unknown door ${row.door}` };
    const model = row.door === "OpenRouter" ? row.slug : row.cliModel;
    if (!model) return { ok: false, reason: `seat ${id} (${row.door}) missing model field` };

    const log = logNameFor({ doorSlug, model });
    if (seenLogNames.has(log)) {
      return { ok: false, reason: `log name collision ${log} (seats ${seenLogNames.get(log)}, ${id})` };
    }
    seenLogNames.set(log, id);

    // grok's raw JSON filename is known up front (like `log`) so a failed
    // attempt still has a place to land its raw stdout for diagnosis.
    const rawJsonName = doorSlug === "grok" ? `read-grok-${sanitizeModel(model)}.json` : undefined;

    resolved.push({ id, name: row.name, vendor: row.vendor, door: row.door, doorSlug, model, log, raw: rawJsonName });
  }
  return { ok: true, seats: resolved };
}

/**
 * Win32-aware CLI executable resolution. Not pure (reads PATH + filesystem).
 * Returns { command, argsPrefix, shell, resolvedFrom, reason? }.
 * `command` is null (with `reason`) when nothing on PATH matches `name`.
 * Node refuses to spawn .cmd/.bat with shell:false (EINVAL, CVE-2024-27980
 * mitigation), so a resolved npm .cmd shim is unwrapped to the underlying
 * node_modules target it invokes. No shell:true fallback (B8) — a `.cmd`
 * shim whose target cannot be parsed out refuses (`command: null`, a
 * `reason`) rather than mangling argv through a shell; `shell` in the
 * receipt is therefore always false.
 */
export function resolveCli(name, env) {
  const pathValue = env.PATH ?? env.Path ?? env.path ?? "";
  const isWin = process.platform === "win32";
  const exts = isWin ? [".exe", ".cmd", ".bat", ""] : [""];

  let found = null;
  for (const dir of pathValue.split(path.delimiter).filter(Boolean)) {
    for (const ext of exts) {
      const candidate = path.join(dir, `${name}${ext}`);
      try {
        if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) { found = candidate; break; }
      } catch {
        // Inaccessible PATH entry — skip it, keep searching.
      }
    }
    if (found) break;
  }
  if (!found) return { command: null, argsPrefix: [], shell: false, resolvedFrom: null, reason: `executable not found: ${name}` };

  if (isWin && /\.cmd$/i.test(found)) {
    let text = "";
    try { text = fs.readFileSync(found, "utf8"); } catch { text = ""; }
    const dir0 = path.dirname(found);
    const match = text.match(/node_modules[\\/][^\r\n"]*?\.(js|exe)\b/i);
    if (match) {
      const resolved = path.join(dir0, match[0]);
      if (/\.js$/i.test(resolved)) return { command: process.execPath, argsPrefix: [resolved], shell: false, resolvedFrom: found };
      if (/\.exe$/i.test(resolved)) return { command: resolved, argsPrefix: [], shell: false, resolvedFrom: found };
    }
    return { command: null, argsPrefix: [], shell: false, resolvedFrom: found, reason: `unresolvable .cmd shim: ${found}` };
  }

  return { command: found, argsPrefix: [], shell: false, resolvedFrom: found };
}

/**
 * If `absPath` is inside `cwd`, return the relative form (keeps argv clean
 * against a repo path that contains a space); otherwise return `absPath`.
 */
function relativizeUnderCwd(cwd, absPath) {
  const rel = path.relative(cwd, absPath);
  if (rel.startsWith("..")) return absPath;
  return rel;
}

/**
 * Exact argv per door. Does not include the resolved CLI binary itself.
 * For codex, also sets `seat._lastMessagePath` (absolute) — the file the
 * `-o`/`--output-last-message` flag tells codex to write its final message
 * to; `dispatchSeat` reads it back after the process exits (B2). `ctx.outDir`
 * is required for the codex branch only. `ctx.attemptNum` (default 1, H2)
 * names the codex last-message path per attempt
 * (`<base>.attempt<N>.last.md`) so a retried attempt never overwrites the
 * first attempt's evidence before `dispatchSeat` decides which one won.
 */
export function buildArgvForSeat(seat, ctx) {
  const assignmentPathArg = relativizeUnderCwd(ctx.cwd, ctx.absAssignmentPath);
  switch (seat.doorSlug) {
    case "codex": {
      const attemptNum = ctx.attemptNum ?? 1;
      const lastMessagePath = path.join(ctx.outDir, `${baseNameFor(seat)}.attempt${attemptNum}.last.md`);
      seat._lastMessagePath = lastMessagePath;
      const lastMessageArg = relativizeUnderCwd(ctx.cwd, lastMessagePath);
      // --ignore-user-config is deliberately NOT passed (removed 2026-09-23, live cold-read failure).
      // ~/.codex/config.toml carries a global `sandbox = "elevated"` that is what permits
      // CreateProcess on Windows; --ignore-user-config discarded it, so with the flag the seat could
      // reach the network and still read nothing, refusing with "blocked by policy" — correctly
      // vetoed by hasFindingsShape. Proven by A/B/D testing, including from the runner's own
      // untrusted job workspace (not just a trusted project dir). Accepted cost, taken knowingly by
      // the operator on 2026-09-23: the seat now inherits the operator's config.toml, including any
      // configured MCP servers, hooks and plugins, so this seat is less hermetic than before.
      return [
        "exec", "-m", seat.model, "-c", `model_reasoning_effort="high"`, "--sandbox", "read-only",
        "--skip-git-repo-check", "-o", lastMessageArg, "-",
      ];
    }
    case "claude":
      return [
        "-p", "--model", seat.model, "--effort", "high", "--permission-mode", "plan",
        "--tools", "Read,Grep,Glob,Bash", "--disallowedTools", "Edit,Write,NotebookEdit",
        "--no-session-persistence", "--output-format", "text",
      ];
    case "grok":
      return [
        "--prompt-file", assignmentPathArg, "--output-format", "json", "--cwd", ctx.cwd,
        "--permission-mode", "plan",
        "--disallowed-tools", "Edit,Write,MultiEdit,NotebookEdit",
        ...GROK_READ_ONLY_ALLOW_RULES.flatMap((rule) => ["--allow", rule]),
        "--reasoning-effort", "high", "--no-subagents", "-m", seat.model,
      ];
    case "openrouter":
      return [
        "-p", "--no-session", "--no-context-files", "--no-extensions", "--no-skills",
        "--no-prompt-templates", "--no-mcp", "--no-approve", "--tools", "read,grep,find,ls",
        "--model", `openrouter/${seat.model}`, "--thinking", "high", `@${assignmentPathArg}`,
        "Execute the attached cold-seat f-plancheck assignment exactly as written. Output findings only, in the shape it specifies.",
      ];
    default:
      throw new Error(`unknown doorSlug ${seat.doorSlug}`);
  }
}

/**
 * Spawn one bounded attempt. windowsHide + shell:false by default (shell
 * only when the caller's invocation could not be unwrapped from a .cmd —
 * and per B8 that no longer happens: an unresolvable .cmd shim refuses in
 * resolveCli instead). Stdout is capped at `maxBytes`, then kills (B4).
 * Stderr has its own independent MAX_STDERR_BYTES cap that TRUNCATES —
 * stops appending, sets `stderrTruncated: true` — without killing the
 * process (B4). Kills on timeout too (win32: taskkill /T /F /PID, else
 * SIGTERM then SIGKILL). A kill is best-effort and may not land; if `close`
 * never arrives within KILL_GRACE_MS of a kill attempt, the attempt is
 * resolved anyway with `killedUnconfirmed: true` rather than hanging the
 * seat forever (B6).
 */
function spawnCapture({ command, args, cwd, env, shell, input, timeoutMs, maxBytes }) {
  return new Promise((resolve) => {
    const startedAt = new Date().toISOString();
    let child;
    try {
      child = spawn(command, args, {
        cwd,
        env,
        windowsHide: true,
        shell: !!shell,
        stdio: [input != null ? "pipe" : "ignore", "pipe", "pipe"],
      });
    } catch (err) {
      resolve({
        exitCode: null, stdout: Buffer.alloc(0), stderr: Buffer.alloc(0),
        startedAt, endedAt: new Date().toISOString(), timedOut: false, outputLimited: false,
        stderrTruncated: false, killedUnconfirmed: false, spawnError: err.message, stdinError: null,
      });
      return;
    }

    // S3: registered once the child exists, before any listener can settle
    // the promise — `killTree` below is a closure over this exact `child`.
    const liveEntry = { child, killTree: () => killTree() };
    LIVE_CHILDREN.add(liveEntry);

    let stdout = Buffer.alloc(0);
    let stderr = Buffer.alloc(0);
    let stdoutBytes = 0;
    let stderrBytes = 0;
    let outputLimited = false;
    let stderrTruncated = false;
    let timedOut = false;
    let settled = false;
    let timer = null;
    // M13: an EPIPE (or other) error writing the assignment to the child's
    // stdin was previously swallowed by an empty listener — codex/claude
    // would then run with a truncated or absent prompt and fail in a way
    // indistinguishable from a normal empty-output failure. Captured here,
    // surfaced on the attempt record, and treated as a non-terminal failure
    // (retry allowed) by the caller.
    let stdinError = null;

    function armKillGrace() {
      setTimeout(() => {
        if (settled) return;
        settled = true;
        if (timer) clearTimeout(timer);
        resolve({
          exitCode: null, stdout, stderr, startedAt, endedAt: new Date().toISOString(),
          timedOut, outputLimited, stderrTruncated, killedUnconfirmed: true, spawnError: null, stdinError,
        });
      }, KILL_GRACE_MS);
    }

    function killTree() {
      if (!Number.isInteger(child.pid)) return;
      if (process.platform === "win32") {
        try { spawnSync("taskkill", ["/T", "/F", "/PID", String(child.pid)], { windowsHide: true, timeout: 15_000 }); } catch { /* best effort */ }
      } else {
        try { child.kill("SIGTERM"); } catch { /* ignore */ }
        setTimeout(() => { try { child.kill("SIGKILL"); } catch { /* ignore */ } }, 2000);
      }
      armKillGrace();
    }

    function finish(exitCode) {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      resolve({
        exitCode, stdout, stderr, startedAt, endedAt: new Date().toISOString(),
        timedOut, outputLimited, stderrTruncated, killedUnconfirmed: false, spawnError: null, stdinError,
      });
    }

    timer = setTimeout(() => { timedOut = true; killTree(); }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      if (outputLimited) return;
      stdoutBytes += chunk.length;
      if (stdoutBytes > maxBytes) {
        outputLimited = true;
        killTree();
        return;
      }
      stdout = Buffer.concat([stdout, chunk]);
    });
    child.stderr.on("data", (chunk) => {
      if (stderrTruncated) return;
      stderrBytes += chunk.length;
      if (stderrBytes > MAX_STDERR_BYTES) {
        stderrTruncated = true;
        return;
      }
      stderr = Buffer.concat([stderr, chunk]);
    });
    child.on("error", (err) => {
      LIVE_CHILDREN.delete(liveEntry);
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      resolve({
        exitCode: null, stdout, stderr, startedAt, endedAt: new Date().toISOString(),
        timedOut, outputLimited, stderrTruncated, killedUnconfirmed: false, spawnError: err.message, stdinError,
      });
    });
    child.on("close", (code) => { LIVE_CHILDREN.delete(liveEntry); finish(code); });

    if (input != null && child.stdin) {
      // EPIPE if the child exits before the write completes is expected and
      // non-fatal on its own — the process outcome is tracked via
      // `close`/`error` above (B5) — but ANY stdin error is still recorded
      // (M13) so a genuinely truncated prompt is distinguishable from a
      // clean empty-output failure.
      child.stdin.on("error", (err) => {
        if (!stdinError) stdinError = err && err.message ? err.message : String(err);
      });
      try {
        child.stdin.write(input);
        child.stdin.end();
      } catch (err) {
        if (!stdinError) stdinError = err && err.message ? err.message : String(err);
      }
    }
  });
}

/**
 * M5: appends a scrubbed hint from `stderrBuffer` (its first non-blank
 * line, ≤200 chars) to a preflight failure `reason` when the probe that
 * produced it wrote anything to stderr — preflight stderr was previously
 * captured and discarded, leaving "version check failed (exit 1)" with no
 * clue why. No-op when `stderrBuffer` is empty/absent.
 */
function appendStderrHint(reason, stderrBuffer) {
  if (!stderrBuffer || stderrBuffer.length === 0) return reason;
  const text = scrubSecrets(stderrBuffer.toString("utf8"));
  const firstLine = text.split(/\r?\n/).find((l) => l.trim().length > 0);
  if (!firstLine) return reason;
  return `${reason} — ${firstLine.trim().slice(0, 200)}`;
}

/**
 * Bounded per-seat preflight. Returns { ok, version?, reason?, invocation }.
 * `invocation` is carried for the dispatch step, never serialized as-is.
 */
async function runPreflight(seat, ctx) {
  const cliName = CLI_NAME_FOR_DOOR[seat.doorSlug];
  const invocation = resolveCli(cliName, ctx.env);
  if (!invocation.command) {
    // `invocation.reason` already distinguishes "not found" from an
    // unresolvable .cmd shim (B8) — propagate it as-is. No process ran, so
    // there is no stderr to append (M5).
    return { ok: false, reason: invocation.reason || `executable not found: ${cliName}`, invocation };
  }

  // Both preflight probes below share every spawnCapture option except the
  // trailing CLI arg — capture invocation/ctx once and vary just that.
  const probe = (extraArg) => spawnCapture({
    command: invocation.command,
    args: [...invocation.argsPrefix, extraArg],
    cwd: ctx.cwd,
    env: ctx.env,
    shell: invocation.shell,
    input: null,
    timeoutMs: PREFLIGHT_TIMEOUT_MS,
    maxBytes: PREFLIGHT_MAX_BYTES,
  });

  const versionResult = await probe("--version");
  if (versionResult.spawnError) return { ok: false, reason: `version check spawn error: ${versionResult.spawnError}`, invocation };
  if (versionResult.timedOut || versionResult.exitCode !== 0) {
    return {
      ok: false,
      reason: appendStderrHint(`version check failed (exit ${versionResult.exitCode}, timed_out=${versionResult.timedOut})`, versionResult.stderr),
      invocation,
    };
  }
  const version = versionResult.stdout.toString("utf8").split(/\r?\n/)[0].trim();

  if (seat.doorSlug === "openrouter") {
    if (!ctx.env.OPENROUTER_API_KEY) return { ok: false, reason: "OPENROUTER_API_KEY missing", invocation, version };
  }

  if (seat.doorSlug === "grok") {
    const modelsResult = await probe("models");
    // M4: distinct reasons per grok-models failure mode, replacing a single
    // catch-all "model not listed by grok models" that hid a spawn error, a
    // timeout, or a non-zero exit behind the same misleading text.
    if (modelsResult.spawnError) {
      return { ok: false, reason: `grok models spawn error: ${modelsResult.spawnError}`, invocation, version };
    }
    if (modelsResult.timedOut) {
      return { ok: false, reason: appendStderrHint("grok models timed out", modelsResult.stderr), invocation, version };
    }
    if (modelsResult.exitCode !== 0) {
      return { ok: false, reason: appendStderrHint(`grok models exit ${modelsResult.exitCode}`, modelsResult.stderr), invocation, version };
    }
    const modelsText = modelsResult.stdout.toString("utf8");
    if (!modelsText.includes(seat.model)) {
      return { ok: false, reason: appendStderrHint(`model ${seat.model} not listed by grok models`, modelsResult.stderr), invocation, version };
    }
  }

  return { ok: true, version, invocation };
}

/**
 * grok-only baseline-beyond-transport check. `grok --output-format json`
 * exits 0 with non-empty stdout even when the seat's own agent loop was
 * cancelled before it produced a final answer (observed live, 2026-09-02:
 * `stopReason: "cancelled"`, findings text never reaches `.text`, only
 * partial progress narration does). Root is separately probing why plan
 * mode cancels grok's read; until a corrected argv ships, exit0+non-empty
 * stdout is necessary but not sufficient for a grok attempt — the parsed
 * JSON's `stopReason` must also be `"end_turn"`.
 */
function grokStopReasonOf(stdoutBuffer) {
  try {
    const parsed = JSON.parse(stdoutBuffer.toString("utf8"));
    return typeof parsed.stopReason === "string" ? parsed.stopReason : "unparsable";
  } catch {
    return "unparsable";
  }
}

/** Pure. No I/O. Grok's parsed `.text`, or null if unparsable / not a string. */
function grokParsedTextOf(stdoutBuffer) {
  try {
    const parsed = JSON.parse(stdoutBuffer.toString("utf8"));
    return typeof parsed.text === "string" ? parsed.text : null;
  } catch {
    return null;
  }
}

/** Not pure (reads filesystem). File text if it exists and is non-whitespace, else null. */
function readLastMessageIfNonEmpty(filePath) {
  try {
    const text = fs.readFileSync(filePath, "utf8");
    return text.trim().length > 0 ? text : null;
  } catch {
    return null;
  }
}

/**
 * Pure. No I/O. The text that will actually land in the seat's canonical
 * `.log` for this attempt if it succeeds — grok's parsed `.text` (raw
 * stdout when empty/unparsable), codex's last-message file text, otherwise
 * raw stdout (B7). Shared by `computeLogBytes` and the INC content-floor /
 * usage-limit-on-success checks so all three agree on exactly what text is
 * being judged.
 */
function computeLogText(seat, result, lastMessageText) {
  let text;
  if (seat.doorSlug === "grok") {
    const parsedText = grokParsedTextOf(result.stdout);
    text = parsedText != null ? parsedText : result.stdout.toString("utf8");
  } else if (seat.doorSlug === "codex") {
    text = lastMessageText != null ? lastMessageText : result.stdout.toString("utf8");
  } else {
    text = result.stdout.toString("utf8");
  }
  // Scrubbed here so `log_bytes` measures exactly what lands on disk.
  return scrubSecrets(text);
}

/** Pure. No I/O. Bytes of `computeLogText(...)`, UTF-8. */
function computeLogBytes(seat, result, lastMessageText) {
  return Buffer.byteLength(computeLogText(seat, result, lastMessageText), "utf8");
}

// INC: frozen assignment requires a line-start [SEVERITY] finding with a
// location payload, or an explicit "no findings" line with no unread-refusal
// veto. A prose mention is not a completed read (observed live: an unread-repo
// refusal containing "no findings" scored shape_ok). A bare token or a
// quoted format list is not a finding. Payload is same-line (`[ \t]+\S`);
// a newline must not supply the next line as payload.
const FINDINGS_TAG_RE = /^\s*(?:[-*]\s+|[0-9]+[.)]\s+)?\[(?:CRITICAL|MODERATE|MINOR)\][ \t]+\S/m;
// Own line, or a check-name line whose remainder is only that phrase.
// The prefix is bounded so a paragraph cannot swallow the match.
const NO_FINDINGS_LINE_RE = /^\s*(?:.{1,80}[:\u2013\u2014-]\s*)?no findings\.?\s*$/im;
// Veto is after the tag check: unread/blocked body is not a clean read.
const UNREAD_REFUSAL_RE = /\b(?:unverified|could not read|blocked by policy)\b/i;

/** Pure. No I/O. Frozen findings-shape floor (INC). */
export function hasFindingsShape(text) {
  if (typeof text !== "string") return false;
  if (FINDINGS_TAG_RE.test(text)) return true;
  if (UNREAD_REFUSAL_RE.test(text)) return false;
  return NO_FINDINGS_LINE_RE.test(text);
}

/**
 * Pure. No I/O. `data` (a stdout Buffer or a string) with any recognizable
 * secret shape redacted. Returns `data` itself — byte-exact — when nothing
 * matched, so a clean stdout is never re-encoded through UTF-8.
 */
function scrubbedArtifact(data) {
  const text = Buffer.isBuffer(data) ? data.toString("utf8") : String(data);
  const scrubbed = scrubSecrets(text);
  return scrubbed === text ? data : scrubbed;
}

/**
 * H3: writes one attempt artifact through `fs.writeFileSync`, catching any
 * failure into `artifactErrors` instead of throwing — a lost raw-evidence
 * copy (disk full, permission) must not discard an otherwise-successful
 * attempt's real transport result. Returns whether the write landed; the
 * caller only records a filename in the attempt/receipt when it did (M12).
 * Every payload is scrubbed on the way through.
 */
function writeAttemptArtifact(outDir, fileName, data, artifactErrors) {
  try {
    fs.writeFileSync(path.join(outDir, fileName), scrubbedArtifact(data));
    return true;
  } catch (err) {
    artifactErrors.push(`${fileName}: ${err && err.message ? err.message : String(err)}`);
    return false;
  }
}

/** Retry-once dispatch for one already-preflighted seat. Mutates `seat`. */
async function dispatchSeat(seat, ctx) {
  const invocation = seat._invocation;
  const base = baseNameFor(seat);

  // M12: a reused --out dir cannot be allowed to carry over stale canonical
  // findings from a prior run into this run's receipt — unlink whatever
  // this seat's canonical names would resolve to before attempting anything.
  for (const staleName of [seat.log, seat.raw, `${base}.last.md`]) {
    if (!staleName) continue;
    try { fs.unlinkSync(path.join(ctx.outDir, staleName)); } catch { /* not present */ }
  }

  seat.attempts = [];
  let success = false;
  let lastResult = null;
  let lastGrokStopReason = null;
  let lastGrokEmptyText = false;
  let lastLogBytes = 0;
  // Set when an attempt's failure means a second attempt would be waste
  // (usage/rate limit, timeout, output overflow) — the loop stops (B3).
  let terminalReason = null;

  for (let attemptNum = 1; attemptNum <= 2 && !success && !terminalReason; attemptNum++) {
    // H2: codex's -o/--output-last-message target is per-attempt
    // (`<base>.attempt<N>.last.md`) so a retry never overwrites the prior
    // attempt's evidence before this loop decides which attempt won; the
    // per-attempt and canonical last-message files are unlinked first so a
    // reused out dir cannot leave a stale one behind if this attempt's
    // process never writes it.
    if (seat.doorSlug === "codex") {
      seat._doorArgv = buildArgvForSeat(seat, { cwd: ctx.cwd, absAssignmentPath: ctx.absAssignmentPath, outDir: ctx.outDir, attemptNum });
      try { fs.unlinkSync(seat._lastMessagePath); } catch { /* not present */ }
      try { fs.unlinkSync(path.join(ctx.outDir, `${base}.last.md`)); } catch { /* not present */ }
    }
    const args = [...invocation.argsPrefix, ...seat._doorArgv];
    const wantsStdin = seat.doorSlug === "codex" || seat.doorSlug === "claude";
    // eslint-disable-next-line no-await-in-loop -- attempt 2 only fires after attempt 1 fails
    const result = await spawnCapture({
      command: invocation.command,
      args,
      cwd: ctx.cwd,
      env: ctx.env,
      shell: invocation.shell,
      input: wantsStdin ? ctx.assignmentBytes : null,
      timeoutMs: ctx.timeoutMs,
      maxBytes: MAX_OUTPUT_BYTES,
    });
    lastResult = result;
    const bytes = result.stdout.length;

    // Codex streams its transcript to stderr and writes the final message to
    // the `-o` file (B2) — stdout alone is not reliable transport evidence
    // for that door, so a non-empty last-message file also counts.
    const lastMessageText = seat.doorSlug === "codex" && seat._lastMessagePath
      ? readLastMessageIfNonEmpty(seat._lastMessagePath)
      : null;
    const artifactErrors = [];
    // Codex writes its `-o` file itself — the one stdout-derived artifact
    // that bypasses writeAttemptArtifact — so it is scrubbed in place.
    if (lastMessageText != null && scrubSecrets(lastMessageText) !== lastMessageText) {
      writeAttemptArtifact(ctx.outDir, path.basename(seat._lastMessagePath), lastMessageText, artifactErrors);
    }
    // M13: a stdin write/EPIPE error means codex/claude may have run against
    // a truncated or absent prompt — never counted as transport success even
    // if the process happened to exit 0 with some bytes.
    const transportOk = !result.stdinError && result.exitCode === 0 && (bytes > 0 || lastMessageText != null);

    let stopReason = null;
    if (transportOk && seat.doorSlug === "grok") stopReason = grokStopReasonOf(result.stdout);

    // H3/M7: every attempt's raw stdout/stderr is written under a
    // per-attempt name the next attempt never overwrites, with each write
    // wrapped so a failing copy is recorded (`artifact_error`) rather than
    // thrown — losing a raw-evidence copy must not discard a real transport
    // result. stderr is scrubbed before it ever touches disk (M7). Grok's
    // raw stdout is additionally JSON, saved under both the generic `.log`
    // name and a `.json` name, and under the canonical `seat.raw` name
    // (always the LAST attempt, overwritten each time — grok's own read may
    // still be diagnostic evidence even when the overall seat ends up
    // omitted). Codex's last-message file is written by codex itself at the
    // per-attempt `-o` path.
    const stdoutLogName = `${base}.attempt${attemptNum}.log`;
    const stdoutWritten = writeAttemptArtifact(ctx.outDir, stdoutLogName, result.stdout, artifactErrors);
    let jsonLogName = null;
    if (seat.doorSlug === "grok") {
      const candidateJsonName = `${base}.attempt${attemptNum}.json`;
      if (writeAttemptArtifact(ctx.outDir, candidateJsonName, result.stdout, artifactErrors)) jsonLogName = candidateJsonName;
      // S1: `seat.raw` is overwritten every attempt (last attempt wins) — the
      // write's success/failure must also be tracked per attempt so a failed
      // last write does not leave the receipt pointing at a stale/missing
      // file (same principle as `log: null` for a non-ok seat).
      seat.raw_written = writeAttemptArtifact(ctx.outDir, seat.raw, result.stdout, artifactErrors);
    }
    let stderrLogName = null;
    if (result.stderr && result.stderr.length > 0) {
      const candidateStderrName = `${base}.attempt${attemptNum}.stderr.log`;
      const scrubbedStderr = scrubSecrets(result.stderr.toString("utf8"));
      if (writeAttemptArtifact(ctx.outDir, candidateStderrName, scrubbedStderr, artifactErrors)) stderrLogName = candidateStderrName;
    }

    const logText = computeLogText(seat, result, lastMessageText);
    const logBytes = computeLogBytes(seat, result, lastMessageText);
    lastLogBytes = logBytes;

    // Tentative per-door success determination (transport + grok
    // stopReason/text), unchanged from before INC.
    let attemptOk = false;
    lastGrokStopReason = null;
    lastGrokEmptyText = false;
    if (transportOk && seat.doorSlug === "grok") {
      if (stopReason === "end_turn") {
        // Transport + stopReason are necessary but not sufficient (B7) — an
        // `end_turn` with empty/whitespace `.text` is still a failed attempt.
        const parsedText = grokParsedTextOf(result.stdout);
        if (parsedText != null && parsedText.trim().length > 0) attemptOk = true;
        else lastGrokEmptyText = true;
      } else {
        lastGrokStopReason = stopReason;
      }
    } else if (transportOk) {
      attemptOk = true;
    }

    // INC: content floor — transport success still has to look like findings
    // (line-start [SEVERITY] plus payload, or a "no findings" line without
    // unread-refusal words); a transport-clean refusal or chatter does not count.
    let shapeOk = null;
    if (attemptOk) {
      shapeOk = hasFindingsShape(logText);
      if (!shapeOk) attemptOk = false;
    }

    // INC: usage-limit detection runs on EVERY attempt, not just failed
    // ones — a quota message mid-answer makes an otherwise "successful"
    // transport a failed, terminal attempt (the seat hit its limit and the
    // text is a refusal, not real findings).
    const usageLine = detectUsageLimit(result.stdout.toString("utf8"), result.stderr.toString("utf8"));
    if (usageLine) attemptOk = false;

    success = attemptOk;

    const attemptRecord = {
      attempt: attemptNum,
      started_at: result.startedAt,
      ended_at: result.endedAt,
      exit_code: result.exitCode,
      bytes,
      timed_out: result.timedOut,
      output_limited: result.outputLimited,
      stdout_log: stdoutWritten ? stdoutLogName : null,
      stderr_log: stderrLogName,
      log_bytes: logBytes,
    };
    if (jsonLogName) attemptRecord.json = jsonLogName;
    // S1: only record the -o filename when codex actually wrote a non-empty
    // file there (`lastMessageText != null`) — recording the name
    // unconditionally left a receipt pointing at a file that may not exist.
    if (seat.doorSlug === "codex" && lastMessageText != null) attemptRecord.last_message = `${base}.attempt${attemptNum}.last.md`;
    if (result.stderrTruncated) attemptRecord.stderr_truncated = true;
    if (result.killedUnconfirmed) attemptRecord.killed_unconfirmed = true;
    if (result.stdinError) attemptRecord.stdin_error = scrubSecrets(result.stdinError);
    if (stopReason != null) attemptRecord.stop_reason = stopReason;
    if (shapeOk != null) attemptRecord.shape_ok = shapeOk;
    if (artifactErrors.length) attemptRecord.artifact_error = scrubSecrets(artifactErrors.join("; "));
    seat.attempts.push(attemptRecord);

    if (!success) {
      if (usageLine) {
        terminalReason = `usage limit: ${scrubSecrets(usageLine)}`;
      } else if (result.timedOut) {
        terminalReason = "timed out — not retried (a second attempt against a genuinely slow read or a runaway stream is waste)";
      } else if (result.outputLimited) {
        terminalReason = "output limit exceeded — not retried (a second attempt against a runaway stream is waste)";
      }
    }
  }

  if (!success) {
    seat.status = "omitted";
    const last = seat.attempts[seat.attempts.length - 1];
    if (last.stderr_log) seat.stderr_log = last.stderr_log;
    if (terminalReason) seat.reason = terminalReason;
    else if (lastResult && lastResult.spawnError) seat.reason = `spawn error: ${lastResult.spawnError}`;
    else if (last.stdin_error) seat.reason = `stdin error: ${last.stdin_error}`;
    else if (seat.doorSlug === "grok" && lastGrokEmptyText) seat.reason = "grok returned no text";
    else if (seat.doorSlug === "grok" && lastGrokStopReason) seat.reason = `grok stopReason=${lastGrokStopReason}`;
    else if (last.shape_ok === false) seat.reason = "output lacks the findings shape";
    else if (last.timed_out) seat.reason = `timed out after ${seat.attempts.length} attempt(s)`;
    else if (last.output_limited) seat.reason = "output limit exceeded";
    else if (last.bytes === 0) seat.reason = `empty stdout (exit ${last.exit_code})`;
    else seat.reason = `exit code ${last.exit_code}`;
    return;
  }

  seat.status = "ok";
  seat.log_bytes = lastLogBytes;
  if (lastResult.stderr && lastResult.stderr.length > 0) {
    const candidateStderrLog = `${base}.stderr.log`;
    const scrubbedStderr = scrubSecrets(lastResult.stderr.toString("utf8"));
    const written = writeAttemptArtifact(ctx.outDir, candidateStderrLog, scrubbedStderr, []);
    if (written) seat.stderr_log = candidateStderrLog;
    else seat.canonical_stderr_error = "could not write canonical stderr log";
  }

  // The canonical `seat.log` write below is the seat's actual deliverable —
  // deliberately NOT wrapped: a failure here propagates out of
  // `dispatchSeat`, caught by the `try/catch` around its call site in
  // `main()` (H3), which marks the seat "omitted" with a named
  // "artifact write failed" reason rather than reporting a false "ok" whose
  // log never landed.
  if (seat.doorSlug === "grok") {
    // seat.raw was already written for this (successful) attempt above,
    // inside the loop — reuse the in-memory bytes rather than re-read.
    // Success already required non-empty parsed text (B7), so this is
    // guaranteed non-null here — the raw_unparsed branch is defensive.
    const text = grokParsedTextOf(lastResult.stdout);
    if (text != null) {
      fs.writeFileSync(path.join(ctx.outDir, seat.log), scrubbedArtifact(text), "utf8");
    } else {
      fs.writeFileSync(path.join(ctx.outDir, seat.log), scrubbedArtifact(lastResult.stdout));
      seat.raw_unparsed = true;
    }
  } else if (seat.doorSlug === "codex") {
    const text = seat._lastMessagePath ? readLastMessageIfNonEmpty(seat._lastMessagePath) : null;
    if (text != null) {
      fs.writeFileSync(path.join(ctx.outDir, seat.log), scrubbedArtifact(text), "utf8");
      // H2: best-effort copy of the winning attempt's last-message file to
      // the canonical `<base>.last.md` name — supplementary to `seat.log`
      // (the real deliverable, already written above), so a copy failure is
      // recorded, not thrown or hidden.
      try {
        fs.writeFileSync(path.join(ctx.outDir, `${base}.last.md`), scrubbedArtifact(text), "utf8");
      } catch (err) {
        seat.canonical_copy_error = err && err.message ? err.message : String(err);
      }
    } else {
      fs.writeFileSync(path.join(ctx.outDir, seat.log), scrubbedArtifact(lastResult.stdout));
    }
  } else {
    fs.writeFileSync(path.join(ctx.outDir, seat.log), scrubbedArtifact(lastResult.stdout));
  }
}

function buildReceipt({ assignmentArg, assignmentSha256, cwd, startedAt, endedAt, seats }) {
  return {
    version: 1,
    assignment: assignmentArg,
    assignment_sha256: assignmentSha256,
    cwd,
    started_at: startedAt,
    ended_at: endedAt,
    seats: seats.map((seat) => {
      const preflight = { ok: !!(seat.preflight && seat.preflight.ok) };
      if (seat.preflight && seat.preflight.version) preflight.version = scrubSecrets(seat.preflight.version);
      if (seat.preflight && seat.preflight.reason) preflight.reason = scrubSecrets(seat.preflight.reason);

      // M12: `log`/`raw` must point only at files that actually exist.
      // `seat.log` is a filename resolved at seat-resolution time — it is
      // only ever written when `dispatchSeat` reaches its success branch, so
      // any non-"ok" status (including preflight-failed, which never calls
      // dispatchSeat at all) means the file was never written. `seat.raw`
      // (grok only) IS legitimately written even on a failed dispatch — it
      // is diagnostic evidence of the last attempt — but only when
      // `dispatchSeat` actually ran; a preflight-failed seat's `seat.raw`
      // name is otherwise just as stale as its `seat.log` name. S1: the LAST
      // attempt's raw write can itself fail (disk error) — `seat.raw_written`
      // (set from `writeAttemptArtifact`'s return value on every grok
      // attempt) gates this the same way `dispatched` gates it.
      const dispatched = Array.isArray(seat.attempts) && seat.attempts.length > 0;
      const entry = {
        id: seat.id,
        door: seat.door,
        doorSlug: seat.doorSlug,
        model: seat.model,
        log: seat.status === "ok" ? seat.log : null,
        argv: (seat._doorArgv || []).map((a) => scrubSecrets(a)),
        shell: !!(seat._invocation && seat._invocation.shell),
        preflight,
        attempts: seat.attempts || [],
        status: seat.status,
      };
      if (dispatched && seat.raw && seat.raw_written) entry.raw = seat.raw;
      if (seat.stderr_log) entry.stderr_log = seat.stderr_log;
      if (seat.reason) entry.reason = scrubSecrets(seat.reason);
      if (seat.raw_unparsed) entry.raw_unparsed = true;
      if (seat.log_bytes != null) entry.log_bytes = seat.log_bytes;
      if (seat.canonical_copy_error) entry.canonical_copy_error = scrubSecrets(seat.canonical_copy_error);
      if (seat.canonical_stderr_error) entry.canonical_stderr_error = scrubSecrets(seat.canonical_stderr_error);
      return entry;
    }),
  };
}

/** Builds and writes the `dispatch.json` receipt. Returns nothing. */
function writeReceipt(outDir, receiptArgs) {
  const receipt = buildReceipt(receiptArgs);
  fs.writeFileSync(path.join(outDir, "dispatch.json"), JSON.stringify(receipt, null, 2));
}

/** Runs `action`; on throw, prints a PLANCHECK_DISPATCH_ERR line and exits 1. */
function tryOrExit(label, action) {
  try {
    return action();
  } catch (err) {
    console.error(`PLANCHECK_DISPATCH_ERR ${label}: ${err.message}`);
    process.exit(1);
  }
}

async function main() {
  const assignmentArg = arg("assignment");
  const seatsArg = arg("seats");
  const outArg = arg("out");
  const cwdArg = arg("cwd", process.cwd());
  const timeoutMs = Number(arg("timeout", "3600000")) || 3_600_000;
  const dryRun = hasFlag("dry-run");
  const preflightOnly = hasFlag("preflight-only");

  if (!assignmentArg || !seatsArg || !outArg) {
    console.error("PLANCHECK_DISPATCH_ERR missing required --assignment/--seats/--out");
    process.exit(1);
  }

  const absAssignmentPath = path.resolve(assignmentArg);
  const assignmentBytes = tryOrExit("cannot read --assignment", () => fs.readFileSync(absAssignmentPath));
  const assignmentSha256 = crypto.createHash("sha256").update(assignmentBytes).digest("hex");
  console.log(`PLANCHECK_DISPATCH_ASSIGNMENT_SHA256=${assignmentSha256}`);

  const seatsFile = tryOrExit("cannot read/parse --seats", () => JSON.parse(fs.readFileSync(path.resolve(seatsArg), "utf8")));

  const roster = tryOrExit("cannot read/parse roster", () => JSON.parse(fs.readFileSync(ROSTER_PATH, "utf8")));

  const resolution = resolveSeats(seatsFile, roster);
  if (!resolution.ok) {
    console.error(`PLANCHECK_DISPATCH_ERR ${resolution.reason}`);
    process.exit(1);
  }
  const seats = resolution.seats;

  const cwd = path.resolve(cwdArg);
  const outDir = path.resolve(outArg);
  tryOrExit("cannot create --out dir", () => fs.mkdirSync(outDir, { recursive: true }));

  const env = process.env;
  const startedAt = new Date().toISOString();

  // H3: `dispatch.json` must survive a throw or an interrupt, not just the
  // clean-exit path. `writeReceiptOnce` is the single place that writes it;
  // both the normal end-of-main path and the SIGINT/SIGTERM handler below
  // funnel through it, guarded so a receipt is never written twice.
  let receiptWritten = false;
  function writeReceiptOnce(seatsSnapshot) {
    if (receiptWritten) return;
    receiptWritten = true;
    const endedAt = new Date().toISOString();
    writeReceipt(outDir, { assignmentArg, assignmentSha256, cwd, startedAt, endedAt, seats: seatsSnapshot });
  }
  function handleInterrupt(signal) {
    // S3: kill every in-flight child FIRST — a programmatic SIGTERM to this
    // process (e.g. a caller's own timeout) must not leave a spawned CLI
    // (an OpenRouter seat's underlying process, in particular) running and
    // spending after dispatch itself has exited. `killTree` is best-effort
    // (win32: synchronous taskkill /T /F; else SIGTERM then a scheduled
    // SIGKILL that a subsequent process.exit below may cut off) — same
    // caveat as every other killTree call site in this file.
    for (const { killTree } of LIVE_CHILDREN) {
      try { killTree(); } catch { /* best effort */ }
    }
    // Any seat that hasn't reached a terminal status yet was in flight —
    // preflight-failed / dry-run / already-dispatched seats already have
    // `seat.status` set and are left untouched.
    for (const seat of seats) {
      if (!seat.status) {
        seat.status = "interrupted";
        seat.reason = `dispatch interrupted by ${signal}`;
        if (!Array.isArray(seat.attempts)) seat.attempts = [];
      }
    }
    writeReceiptOnce(seats);
    console.log("PLANCHECK_DISPATCH_INTERRUPTED");
    process.exit(130);
  }
  process.once("SIGINT", () => handleInterrupt("SIGINT"));
  process.once("SIGTERM", () => handleInterrupt("SIGTERM"));

  await Promise.all(seats.map(async (seat) => {
    seat.preflight = await runPreflight(seat, { env, cwd });
    seat._invocation = seat.preflight.invocation;
    // M6: preflight.reason can carry a scrubbed-but-still-worth-double-checking
    // stderr hint (M5) — scrub again defensively before it ever reaches stdout.
    const pfLine = seat.preflight.ok ? "ok" : `fail: ${scrubSecrets(seat.preflight.reason)}`;
    console.log(`PLANCHECK_SEAT ${seat.id} ${seat.doorSlug} ${seat.model} preflight=${pfLine}`);
  }));

  for (const seat of seats) {
    seat._doorArgv = buildArgvForSeat(seat, { cwd, absAssignmentPath, outDir });
  }

  if (dryRun || preflightOnly) {
    for (const seat of seats) {
      // B10: --preflight-only reports "preflight-ok" (no dispatch attempted,
      // so "dry-run" would be a misnomer); --dry-run keeps "dry-run".
      seat.status = seat.preflight.ok ? (dryRun ? "dry-run" : "preflight-ok") : "omitted";
      seat.attempts = [];
      if (!seat.preflight.ok) seat.reason = seat.preflight.reason;
      if (dryRun) {
        const scrubbedArgv = seat._doorArgv.map((a) => scrubSecrets(a));
        console.log(`PLANCHECK_SEAT ${seat.id} ${seat.doorSlug} ${seat.model} argv: ${JSON.stringify(scrubbedArgv)}`);
      }
    }
    writeReceiptOnce(seats);

    if (dryRun) {
      console.log(`PLANCHECK_DISPATCH_DRY_RUN ${seats.length}`);
      process.exit(0);
    }
    // --preflight-only: not spec'd a pass/fail sentinel (no dispatch attempted
    // to pass/fail) — report the preflight tally under the established
    // PLANCHECK_DISPATCH_* naming convention and always exit 0.
    const okCount = seats.filter((s) => s.preflight.ok).length;
    console.log(`PLANCHECK_DISPATCH_PREFLIGHT_ONLY ${okCount}/${seats.length}`);
    process.exit(0);
  }

  try {
    await Promise.all(seats.map(async (seat) => {
      if (!seat.preflight.ok) {
        seat.status = "omitted";
        seat.reason = seat.preflight.reason;
        seat.attempts = [];
        return;
      }
      // H3: an uncaught throw from dispatchSeat (most likely its own
      // canonical `seat.log` write failing) must not vanish into an
      // unhandled rejection — it is caught here, the seat is marked omitted
      // with a named reason, and whatever attempts already ran are kept.
      try {
        await dispatchSeat(seat, { cwd, outDir, env, timeoutMs, assignmentBytes, absAssignmentPath });
      } catch (err) {
        seat.status = "omitted";
        seat.reason = `artifact write failed: ${scrubSecrets(err && err.message ? err.message : String(err))}`;
        if (!Array.isArray(seat.attempts)) seat.attempts = [];
      }
    }));
  } finally {
    // H3: written here too (not only after the print loop below) so a
    // throw that somehow escapes the per-seat try/catch above still leaves
    // a receipt on disk.
    writeReceiptOnce(seats);
  }

  for (const seat of seats) {
    const last = seat.attempts && seat.attempts.length ? seat.attempts[seat.attempts.length - 1] : null;
    const ms = last ? (new Date(last.ended_at).getTime() - new Date(last.started_at).getTime()) : 0;
    const bytes = last ? last.bytes : 0;
    // M6: seat.reason is scrubbed before it reaches stdout — it can carry a
    // preflight/attempt stderr hint (M5) that survived into a failure
    // reason.
    const reasonSuffix = seat.reason ? ` — ${scrubSecrets(seat.reason)}` : "";
    // I2: the printed log name must agree with the receipt — the receipt's
    // `log` field is only ever non-null for status "ok" (M12 above). A
    // non-ok seat still has diagnostic evidence (the last attempt's raw
    // stdout capture), so fall back to that instead of `seat.log`, which
    // for a non-ok seat names a file that was never written.
    const logLabel = seat.status === "ok" ? seat.log : ((last && last.stdout_log) || "—");
    console.log(`PLANCHECK_SEAT ${seat.id} ${seat.doorSlug} ${seat.model} → ${seat.status} (${ms} ms, ${bytes} B) ${logLabel}${reasonSuffix}`);
  }

  const okCount = seats.filter((s) => s.status === "ok").length;
  if (okCount === 0) {
    console.log(`PLANCHECK_DISPATCH_NONE 0/${seats.length}`);
    process.exit(3);
  }
  console.log(`PLANCHECK_DISPATCH_OK ${okCount}/${seats.length}`);
  process.exit(0);
}

if (isMainModule()) {
  main().catch((err) => {
    console.error(`PLANCHECK_DISPATCH_ERR ${err && err.message ? err.message : String(err)}`);
    process.exit(1);
  });
}
