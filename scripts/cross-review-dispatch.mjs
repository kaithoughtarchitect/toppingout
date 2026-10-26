#!/usr/bin/env node
/**
 * Headless triad dispatcher for the unattended cross-model gate (the seat rule + the unattended
 * apply rule).
 *
 * `pack-review` and `adjudicate` run IN the session that did the work (the "host") — the triad
 * sets `disable-model-invocation: false` on all three skills so that host can invoke them itself
 * without a human typing the slash command. `xreview`, the reviewer half, must never run in that
 * same session (a model that can summon its own reviewer can summon a friendly one — R3). This
 * file is what actually enforces the separation: it seats the reviewer on a DIFFERENT CLI vendor
 * by the deterministic seat rule (no picker, no operator judgment call) and spawns it headless, so
 * independence is structural — a different process, a different vendor family, a blind brief —
 * never a hand-carried convention. The hand-carried loop (described in the `pack-review` /
 * `xreview` / `adjudicate` skills) stays valid when a human drives; this script is the unattended
 * alternative, not a replacement.
 *
 * The xreview contract is read from `.claude/skills/xreview/SKILL.md` under the directory ABOVE
 * this script (i.e. install this file as `<repo>/scripts/cross-review-dispatch.mjs` next to
 * `<repo>/.claude/skills/xreview/SKILL.md`). `--self-test` does not read it.
 *
 * Seat rule (deterministic, no picker). `--host` is first normalised to a vendor FAMILY by
 * `hostFamily()` — `anthropic`, `claude`, `claude-*`, `opus*`, `sonnet*`, `haiku*`, `fable*` ->
 * claude; `openai`, `codex*`, `gpt-*`, `chatgpt*`, `o1`/`o3`/`o4` (alone or followed by `-`) -> codex;
 * a `vendor/model` id is judged by its vendor alone (`anthropic/` -> claude, `openai/` -> codex,
 * any other vendor -> unknown), after stripping a leading `openrouter/`. Then:
 *   host family claude -> reviewer codex
 *   host family codex  -> reviewer claude
 *   host family unknown (e.g. "pi", "grok", "", an unrecognised id) -> REFUSED, no seat (exit 2).
 *     An unknown host is never defaulted to claude: the dispatcher cannot prove the reviewer is a
 *     different family from a host it cannot identify, so it refuses rather than guess. Pass the
 *     family of the model actually doing the work (a Pi-hosted foreman passes its model's family).
 * If the picked reviewer would be the SAME family as the host, or the picked reviewer's CLI does
 * not resolve (e.g. host claude, codex unavailable; host codex, claude unavailable), there is no
 * independent seat — dispatch refuses rather than seat a reviewer that already knows the answer.
 *
 * Apply-list filtering (the unattended apply rule, matches `adjudicate`'s existing contract
 * exactly — invents no new rule): ACCEPT and PARTIAL claims are applied unattended; REJECT is
 * dropped; CANNOT VERIFY claims, together with the reviewer's own "Questions for a human" section,
 * are routed to the human-questions channel (whatever the unattended run already reports through)
 * rather than applied or silently dropped. Any
 * verdict token this repo's `adjudicate` contract does not define is ALSO routed to that channel,
 * never applied — an unattended run must fail closed on an unrecognized verdict, not guess.
 *
 * Mirrors `.claude/skills/f-plancheck/plancheck-dispatch.mjs`: seat preflight via `--version`,
 * Windows `.cmd`/`.bat` shim resolution (that file's `resolveCli`, adapted here, not imported —
 * this is a production dispatch path, not a dependent of a skill's internal script), secret scrubbing
 * before anything touches disk, one retry on a failed attempt, and per-attempt artifacts. Simpler
 * than that file throughout: exactly one seat is ever dispatched (never up to five in parallel),
 * and only the `claude` / `codex` subscription CLI doors exist in the seat rule — no grok, no
 * OpenRouter door is ever a legal reviewer seat here.
 *
 * The reviewer is dispatched by reading the target skill's SKILL.md text in full and embedding it
 * in the prompt with an explicit instruction to follow it, rather than relying on slash-command
 * parsing or model-invocation auto-routing inside a spawned, non-interactive CLI process (unproven
 * for a piped `-p`/`exec -` prompt). If the repo mirrors skills into other agent folders (e.g.
 * `.agents/`), keep the `xreview` copies identical: the `.claude` copy is the one embedded,
 * regardless of which door is dispatched.
 *
 * ceiling: no quota/rate-limit detection (f-plancheck's `detectUsageLimit`) — a failed attempt
 * always gets exactly one retry unless it timed out. This dispatcher only ever runs a single
 * reviewer seat per gate, so the repeated-quota-thrash risk that motivated that detector in the
 * five-seat f-plancheck dispatcher is much smaller here; upgrade: port `detectUsageLimit` from
 * plancheck-dispatch.mjs if a live run shows a quota message being retried into a second one.
 *
 * Usage:
 *   node scripts/cross-review-dispatch.mjs --host <claude|codex|a model id of either family> --brief <path> --out <dir> \
 *     [--cwd <repo>] [--timeout <ms>]
 *   node scripts/cross-review-dispatch.mjs --self-test
 *
 * Exit codes (real dispatch): 0 ok, 1 usage error (includes a malformed --flag: empty/missing
 * value, a value that looks like another option, or a duplicated flag — see `arg()`), 2 no
 * independent reviewer seat (seat rule — including a `--host` whose family `hostFamily()` cannot
 * identify: a well-formed flag naming an unknown family is a seat refusal, not a usage error), 3 reviewer dispatch failed after retry, 4 internal error (e.g. a
 * filesystem failure reaching `dispatchReviewer` — never usage error's 1, which this file's own
 * contract reserves for a bad invocation, not an unexpected fault). Exit codes (--self-test): 0
 * every check passed, 1 otherwise.
 */
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { delimiter, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const XREVIEW_SKILL_PATH = join(REPO_ROOT, ".claude", "skills", "xreview", "SKILL.md");

const PREFLIGHT_TIMEOUT_MS = 20_000;
const DEFAULT_DISPATCH_TIMEOUT_MS = 3_600_000;
const MAX_OUTPUT_BYTES = 32 * 1024 * 1024;

// Same detector list as `.claude/skills/f-plancheck/plancheck-dispatch.mjs`'s `SECRET_DETECTORS`,
// duplicated here rather than imported (this is a production dispatch path, not a dependent of a
// skill's internal script).
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

/**
 * Pure. No I/O (argv is injectable for `--self-test`; defaults to `process.argv`). Reads a
 * `--name value` pair off argv.
 *
 * B5 fix: a present-but-empty (or otherwise malformed) value must NEVER collapse onto the
 * "flag was not supplied at all" branch — that collapse is the exact defect shape this codebase
 * has already been bitten by once (`receipt ? receipt.plan || receipt : null`). Concretely: `--cwd ""` — trivially produced by an
 * unset shell variable, e.g. `--cwd "$REPO_DIR"` — must not silently resolve to
 * `process.cwd()` (the dispatcher's own directory) and spawn the reviewer against the wrong tree.
 * So: PRESENCE and VALUE are handled separately.
 *   - Absent entirely -> `fallback` (the only case that may use it).
 *   - Present but the next token is missing, empty, or itself looks like another option
 *     (`--`-prefixed — this also closes `--brief --out /x` silently binding
 *     `briefPath = "--out"`) -> throw, refusing rather than guessing.
 *   - Present more than once -> throw. `indexOf` alone would silently take the first occurrence;
 *     rather than let a duplicate flag decide "first wins" with no record of the discard, this
 *     refuses so a duplicated flag is a loud invocation bug, not a quiet coin flip.
 * The caller (this file's own `main()`) treats a thrown error here as a usage error (exit 1) —
 * consistent with this file's documented exit-code contract for a malformed invocation.
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

function hasFlag(name) {
  return process.argv.includes(`--${name}`);
}

function isMainModule() {
  try {
    return join(fileURLToPath(import.meta.url)) === join(process.argv[1] || "");
  } catch {
    return false;
  }
}

/**
 * Pure. No I/O. Normalises a `--host` value to the vendor family of the session that did the work:
 * "claude", "codex", or null when the family cannot be identified. Accepts vendor names
 * (`anthropic`, `openai`), CLI names (`claude`, `codex`), and bare model ids (`claude-*`, `opus*`,
 * `sonnet*`, `haiku*`, `fable*` -> claude; `gpt-*`, `chatgpt*`, `codex*`, `o1`/`o3`/`o4` alone or
 * followed by `-` -> codex). A `vendor/model` id resolves by its vendor alone: `anthropic/` ->
 * claude, `openai/` -> codex, any other vendor -> null (so `eleutherai/gpt-j-6b` and
 * `nomic/gpt4all` are refused, not seated as codex). A leading `openrouter/` is stripped first, so
 * `openrouter/<vendor>/<model>` resolves by the inner vendor. Anything else — "pi", "grok", "",
 * a non-string — is null: never guessed.
 * @param {unknown} host
 * @returns {"claude" | "codex" | null}
 */
export function hostFamily(host) {
  if (typeof host !== "string") return null;
  let id = host.trim().toLowerCase();
  if (id.startsWith("openrouter/")) id = id.slice("openrouter/".length);
  if (!id) return null;
  const slash = id.indexOf("/");
  if (slash !== -1) {
    const vendor = id.slice(0, slash);
    if (vendor === "anthropic") return "claude";
    if (vendor === "openai") return "codex";
    return null;
  }
  if (id === "anthropic" || id === "claude" || id.startsWith("claude-")) return "claude";
  if (/^(opus|sonnet|haiku|fable)/.test(id)) return "claude";
  if (id === "openai") return "codex";
  if (/^(gpt-|chatgpt|codex)/.test(id) || /^o[134](-|$)/.test(id)) return "codex";
  return null;
}

/**
 * Pure. No I/O. The seat rule. `host` is the raw `--host` value; it is normalised by
 * `hostFamily()`. Returns `{ ok: true, reviewer }` or `{ ok: false, reviewer: null, reason }`.
 * An unidentifiable host family is refused (never defaulted to claude). Never returns a reviewer
 * whose family equals the host's family — that would be the host reviewing itself, which no
 * fallback in the seat rule is meant to produce, and is refused explicitly rather than silently seated.
 * @param {{ host: unknown, claudeAvailable: boolean, codexAvailable: boolean }} input
 */
export function selectReviewerSeat({ host, claudeAvailable, codexAvailable }) {
  const family = hostFamily(host);
  if (family === null) {
    return {
      ok: false,
      reviewer: null,
      reason:
        `host ${JSON.stringify(host)} did not resolve to a known family (claude or codex) — cannot ` +
        `prove an independent reviewer, so this refuses rather than guessing`,
    };
  }
  const reviewer = family === "claude" ? "codex" : "claude";

  if (reviewer === family) {
    return {
      ok: false,
      reviewer: null,
      reason:
        `reviewer would be the same family as host "${host}" — no independent seat available ` +
        `(claudeAvailable=${!!claudeAvailable}, codexAvailable=${!!codexAvailable})`,
    };
  }
  if (reviewer === "claude" && !claudeAvailable) {
    return { ok: false, reviewer: null, reason: `reviewer seat "claude" is unavailable` };
  }
  if (reviewer === "codex" && !codexAvailable) {
    return {
      ok: false,
      reviewer: null,
      reason:
        `reviewer seat "codex" is unavailable ` +
        `(claudeAvailable=${!!claudeAvailable}, codexAvailable=${!!codexAvailable})`,
    };
  }
  return { ok: true, reviewer, reason: null };
}

const APPLY_VERDICTS = new Set(["ACCEPT", "PARTIAL"]);
const DROP_VERDICTS = new Set(["REJECT"]);
const HUMAN_VERDICTS = new Set(["CANNOT VERIFY"]);

/**
 * Pure. No I/O. The unattended apply rule, matching `adjudicate`'s existing contract exactly:
 * ACCEPT + PARTIAL are applied, REJECT is dropped, CANNOT VERIFY is routed to the human-questions
 * channel (never applied). `claims` is the parsed verdict table (each entry carrying at least a
 * `verdict` field); a claim whose verdict is not one of the four defined tokens is fail-closed
 * into `unrecognized` — never applied, never silently dropped, so an unattended run cannot invent
 * a fifth rule for a token `adjudicate` never produces. `questionsForHuman` (the reviewer's own
 * "Questions for a human" strings, verbatim) are appended to `humanQuestions` unchanged.
 * @param {Array<{verdict?: unknown}>} claims
 * @param {string[]} [questionsForHuman]
 */
export function partitionAdjudication(claims, questionsForHuman) {
  const apply = [];
  const dropped = [];
  const needsHuman = [];
  const unrecognized = [];
  for (const claim of Array.isArray(claims) ? claims : []) {
    const verdict =
      claim && typeof claim.verdict === "string" ? claim.verdict.trim().toUpperCase() : "";
    if (APPLY_VERDICTS.has(verdict)) apply.push(claim);
    else if (DROP_VERDICTS.has(verdict)) dropped.push(claim);
    else if (HUMAN_VERDICTS.has(verdict)) needsHuman.push(claim);
    else unrecognized.push(claim);
  }
  const humanQuestions = Array.isArray(questionsForHuman)
    ? questionsForHuman.filter((q) => typeof q === "string" && q.trim().length > 0)
    : [];
  return { apply, dropped, needsHuman, unrecognized, humanQuestions };
}

// Column separator: ASCII `|` OR the box-drawing verticals real reviewers actually emit. A seat
// rendering its claim table with `│` (U+2502) is producing a perfectly valid review, and matching
// only `|` would reject it — turning this content floor from a false-accept into a false-reject,
// which halts the gate on good work. Observed live: a hand-carried review of this very PR used
// U+2502 throughout.
const COL = "[|\\u2502\\u2503]";
// A REAL claim row: `C<n>` (n >= 1), a separator, then payload — at line start, optional leading
// border. The `### Claim table` HEADING is deliberately not sufficient; see the veto note below.
const CLAIM_ROW_RE = new RegExp(`^\\s*${COL}?\\s*C[1-9][0-9]*\\s*${COL}[ \\t]*\\S`, "m");
const NO_FINDINGS_ROW_RE = new RegExp(`^\\s*${COL}?\\s*C0\\s*${COL}\\s*No findings\\b`, "im");
// Veto, tested AFTER the claim-table check and BEFORE the no-findings row: a seat that could not
// read the repository and therefore reports nothing is NOT a clean review. This exact failure was
// observed live ("the dispatcher scores it green") — on Windows the codex door had `git show` and
// `git grep` rejected by execution policy, read zero files, exited 0, and was recorded
// `status: "ok"`. Ported from the proven fix in `.claude/skills/f-plancheck/plancheck-dispatch.mjs`
// (`UNREAD_REFUSAL_RE`): same bug class, same ordering.
// Without it, "I could not read the repository, so: C0 | No findings" satisfies the MANDATORY
// cross-model gate, the apply rule applies an empty apply-list, and publication proceeds having reviewed
// nothing — strictly worse than the f-plancheck case this was copied from.
const UNREAD_REFUSAL_RE = /\b(?:unverified|could not read|blocked by policy)\b/i;

/**
 * Pure. No I/O. Content floor for a completed `xreview` attempt — transport success (exit 0,
 * non-empty stdout) is necessary but not sufficient; the output must actually carry the skill's
 * claim table (or its explicit no-findings row), not chatter or a refusal.
 */
export function hasXreviewShape(text) {
  if (typeof text !== "string") return false;
  // A real finding row is self-evidencing: a seat that could not read the repo cannot produce one.
  if (CLAIM_ROW_RE.test(text)) return true;
  // Everything else must survive the veto. The `### Claim table` HEADING is deliberately not
  // checked here: `xreview` REQUIRES that section, so a refusing seat that follows the skill emits
  // it too. Short-circuiting on the heading made this veto unreachable in the exact case it exists
  // for — the first version of this fix did that, and the fixtures missed it because they omitted
  // the heading a compliant reviewer always sends.
  if (UNREAD_REFUSAL_RE.test(text)) return false;
  return NO_FINDINGS_ROW_RE.test(text);
}

/**
 * Win32-aware CLI executable resolution. Not pure (reads PATH + filesystem). Returns
 * `{ command, argsPrefix, reason? }`; `command` is null (with `reason`) when nothing on PATH
 * matches `name`. Adapted from `.claude/skills/f-plancheck/plancheck-dispatch.mjs`'s `resolveCli`
 * (same `.cmd`/`.bat` shim problem: Node refuses to spawn a `.cmd`/`.bat` shim with
 * `shell:false`, CVE-2024-27980 mitigation, so a resolved npm shim is unwrapped to the
 * `node_modules` target it invokes rather than reached via `shell:true`).
 */
export function resolveCliOnPath(name, env = process.env) {
  const pathValue = env.PATH ?? env.Path ?? env.path ?? "";
  const isWin = process.platform === "win32";
  const exts = isWin ? [".exe", ".cmd", ".bat", ""] : [""];

  let found = null;
  for (const dir of pathValue.split(delimiter).filter(Boolean)) {
    for (const ext of exts) {
      const candidate = join(dir, `${name}${ext}`);
      try {
        if (existsSync(candidate) && statSync(candidate).isFile()) {
          found = candidate;
          break;
        }
      } catch {
        // Inaccessible PATH entry — skip it, keep searching.
      }
    }
    if (found) break;
  }
  if (!found) return { command: null, argsPrefix: [], reason: `executable not found: ${name}` };

  if (isWin && /\.cmd$/i.test(found)) {
    let text = "";
    try {
      text = readFileSync(found, "utf8");
    } catch {
      text = "";
    }
    const dir0 = dirname(found);
    const match = text.match(/node_modules[\\/][^\r\n"]*?\.(js|exe)\b/i);
    if (match) {
      const resolved = join(dir0, match[0]);
      if (/\.js$/i.test(resolved)) return { command: process.execPath, argsPrefix: [resolved] };
      if (/\.exe$/i.test(resolved)) return { command: resolved, argsPrefix: [] };
    }
    return { command: null, argsPrefix: [], reason: `unresolvable .cmd shim: ${found}` };
  }
  return { command: found, argsPrefix: [] };
}

/** Not pure (spawns a bounded `--version` probe). `{ available, reason?, resolved, version? }`. */
function probeCliAvailable(name) {
  const resolved = resolveCliOnPath(name);
  if (!resolved.command) return { available: false, reason: resolved.reason, resolved };
  const result = spawnSync(resolved.command, [...resolved.argsPrefix, "--version"], {
    windowsHide: true,
    shell: false,
    encoding: "utf8",
    timeout: PREFLIGHT_TIMEOUT_MS,
  });
  if (result.error) return { available: false, reason: `spawn error: ${result.error.message}`, resolved };
  if (result.status !== 0) {
    return { available: false, reason: `version check exited ${result.status}`, resolved };
  }
  return { available: true, resolved, version: (result.stdout || "").split(/\r?\n/)[0].trim() };
}

/** Exact argv per reviewer door — the same read-only headless shape `plancheck-dispatch.mjs` uses
 * for its claude / codex doors (minus the model and effort pins). */
function argvForDoor(door) {
  if (door === "claude") {
    return [
      "-p",
      "--permission-mode",
      "plan",
      "--tools",
      "Read,Grep,Glob,Bash",
      "--disallowedTools",
      "Edit,Write,NotebookEdit",
      "--no-session-persistence",
      "--output-format",
      "text",
    ];
  }
  if (door === "codex") {
    return ["exec", "--sandbox", "read-only", "--skip-git-repo-check", "-"];
  }
  throw new Error(`argvForDoor: unknown door ${door}`);
}

/** Pure. No I/O. The prompt piped to the reviewer's stdin. */
export function buildXreviewPromptText({ skillText, briefText }) {
  return [
    "You are the REVIEWER seat in a cross-model gate, dispatched headlessly and blind by",
    "`scripts/cross-review-dispatch.mjs`. You do not know which model or session produced the",
    "artifact below, and you must not guess or name one. Follow the `xreview` skill contract",
    "reproduced in full below EXACTLY — output its five sections, in order, and nothing else.",
    "",
    "--- xreview SKILL.md (follow exactly) ---",
    skillText,
    "--- end SKILL.md ---",
    "",
    "--- pasted review brief (from /pack-review) ---",
    briefText,
    "--- end review brief ---",
  ].join("\n");
}

/**
 * Pure. No I/O. The audit fields that must appear on EVERY receipt this file writes, success or
 * refusal alike (B5). Before this, the receipt recorded `host`/`reviewer`/`log`/`attempts` but
 * never the `cwd` the reviewer actually ran against or the `--brief` it actually read — so a
 * `--cwd ""` collapse onto the dispatcher's own directory produced a well-formed `ok: true`
 * receipt with nothing in it to show the substitution happened. Carrying `cwd`/`brief` on every
 * branch (including seat refusal, before any file is even read) makes a wrong-tree or wrong-brief
 * review detectable after the fact instead of just less likely.
 * @param {{ host: unknown, cwd: string, briefPath: string }} input
 */
export function buildReceiptBase({ host, cwd, briefPath }) {
  return { host, cwd, brief: briefPath };
}

/**
 * Not pure — the real dispatch: preflight both doors, apply the seat rule, spawn the reviewer
 * headless with one retry, write per-attempt artifacts plus a receipt. Returns the receipt object
 * (also written to `<outDir>/cross-review-dispatch.json`).
 */
function dispatchReviewer({ host, briefPath, outDir, cwd, timeoutMs }) {
  mkdirSync(outDir, { recursive: true });
  const receiptBase = buildReceiptBase({ host, cwd, briefPath });

  const claudeProbe = probeCliAvailable("claude");
  const codexProbe = probeCliAvailable("codex");
  console.log(
    `CROSS_REVIEW_PREFLIGHT claude=${claudeProbe.available ? "ok" : `fail: ${scrubSecrets(claudeProbe.reason)}`} ` +
      `codex=${codexProbe.available ? "ok" : `fail: ${scrubSecrets(codexProbe.reason)}`}`,
  );

  const seat = selectReviewerSeat({
    host,
    claudeAvailable: claudeProbe.available,
    codexAvailable: codexProbe.available,
  });
  if (!seat.ok) {
    const receipt = {
      ...receiptBase,
      ok: false,
      reviewer: null,
      reason: seat.reason,
      claude_available: claudeProbe.available,
      codex_available: codexProbe.available,
    };
    writeFileSync(join(outDir, "cross-review-dispatch.json"), JSON.stringify(receipt, null, 2));
    return receipt;
  }

  const reviewerProbe = seat.reviewer === "claude" ? claudeProbe : codexProbe;
  let skillText;
  let briefText;
  try {
    skillText = readFileSync(XREVIEW_SKILL_PATH, "utf8");
  } catch (err) {
    const receipt = {
      ...receiptBase,
      ok: false,
      reviewer: seat.reviewer,
      reason: `could not read xreview SKILL.md: ${err.message}`,
    };
    writeFileSync(join(outDir, "cross-review-dispatch.json"), JSON.stringify(receipt, null, 2));
    return receipt;
  }
  try {
    briefText = readFileSync(briefPath, "utf8");
  } catch (err) {
    const receipt = {
      ...receiptBase,
      ok: false,
      reviewer: seat.reviewer,
      reason: `could not read --brief: ${err.message}`,
    };
    writeFileSync(join(outDir, "cross-review-dispatch.json"), JSON.stringify(receipt, null, 2));
    return receipt;
  }

  const prompt = buildXreviewPromptText({ skillText, briefText });
  const argv = [...reviewerProbe.resolved.argsPrefix, ...argvForDoor(seat.reviewer)];

  const attempts = [];
  let winningText = null;
  for (let attemptNum = 1; attemptNum <= 2 && winningText == null; attemptNum++) {
    const result = spawnSync(reviewerProbe.resolved.command, argv, {
      cwd,
      input: prompt,
      encoding: "utf8",
      windowsHide: true,
      shell: false,
      timeout: timeoutMs,
      maxBuffer: MAX_OUTPUT_BYTES,
    });
    const scrubbedStdout = scrubSecrets(result.stdout || "");
    const scrubbedStderr = scrubSecrets(result.stderr || "");
    const stdoutLogName = `xreview-${seat.reviewer}.attempt${attemptNum}.log`;
    writeFileSync(join(outDir, stdoutLogName), scrubbedStdout);
    let stderrLogName = null;
    if (scrubbedStderr) {
      stderrLogName = `xreview-${seat.reviewer}.attempt${attemptNum}.stderr.log`;
      writeFileSync(join(outDir, stderrLogName), scrubbedStderr);
    }

    const timedOut = !!result.error && result.error.code === "ETIMEDOUT";
    const transportOk = !result.error && result.status === 0 && scrubbedStdout.trim().length > 0;
    const shapeOk = transportOk && hasXreviewShape(scrubbedStdout);
    attempts.push({
      attempt: attemptNum,
      exit_code: result.status,
      timed_out: timedOut,
      spawn_error: result.error ? result.error.message : null,
      bytes: Buffer.byteLength(scrubbedStdout, "utf8"),
      stdout_log: stdoutLogName,
      stderr_log: stderrLogName,
      transport_ok: transportOk,
      shape_ok: shapeOk,
    });

    if (transportOk && shapeOk) {
      winningText = scrubbedStdout;
    } else if (timedOut) {
      // A second attempt against a genuinely slow reviewer is waste (f-plancheck's same reasoning).
      break;
    }
  }

  if (winningText == null) {
    const last = attempts[attempts.length - 1];
    const reason = !last.transport_ok
      ? `reviewer transport failed (exit ${last.exit_code}, timed_out=${last.timed_out})`
      : "reviewer output lacks the xreview shape (no claim table, no no-findings row)";
    const receipt = {
      ...receiptBase,
      ok: false,
      reviewer: seat.reviewer,
      reason,
      attempts,
      claude_available: claudeProbe.available,
      codex_available: codexProbe.available,
    };
    writeFileSync(join(outDir, "cross-review-dispatch.json"), JSON.stringify(receipt, null, 2));
    return receipt;
  }

  const logName = `xreview-${seat.reviewer}.log`;
  writeFileSync(join(outDir, logName), winningText);
  const receipt = {
    ...receiptBase,
    ok: true,
    reviewer: seat.reviewer,
    log: logName,
    attempts,
    claude_available: claudeProbe.available,
    codex_available: codexProbe.available,
  };
  writeFileSync(join(outDir, "cross-review-dispatch.json"), JSON.stringify(receipt, null, 2));
  return receipt;
}

// ── self-test (offline, no CLI probe, no spawn, no model call) ─────────────────────────────────

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

  // Seat rule — every documented host case.
  check(
    "seat rule: host claude, both available -> codex",
    selectReviewerSeat({ host: "claude", claudeAvailable: true, codexAvailable: true }).reviewer === "codex",
  );
  check(
    "seat rule: host codex, both available -> claude",
    selectReviewerSeat({ host: "codex", claudeAvailable: true, codexAvailable: true }).reviewer === "claude",
  );
  check(
    "seat rule: any other host (grok), both available -> refused, never defaulted to claude",
    (() => {
      const r = selectReviewerSeat({ host: "grok", claudeAvailable: true, codexAvailable: true });
      return r.ok === false && r.reviewer === null;
    })(),
  );
  check(
    "seat rule: unrecognized/undefined host, both available -> refused",
    (() => {
      const r = selectReviewerSeat({ host: undefined, claudeAvailable: true, codexAvailable: true });
      return r.ok === false && r.reviewer === null;
    })(),
  );
  check(
    "seat rule: host claude, codex unavailable -> no seat (ok:false)",
    selectReviewerSeat({ host: "claude", claudeAvailable: true, codexAvailable: false }).ok === false,
  );
  check(
    "seat rule: host codex, claude unavailable -> refuses same-family fallback, not codex-reviews-codex",
    (() => {
      const r = selectReviewerSeat({ host: "codex", claudeAvailable: false, codexAvailable: true });
      return r.ok === false && r.reviewer === null;
    })(),
  );
  check(
    "seat rule: neither CLI available -> no seat (ok:false)",
    selectReviewerSeat({ host: "claude", claudeAvailable: false, codexAvailable: false }).ok === false,
  );
  check(
    "seat rule: host is case-insensitive",
    selectReviewerSeat({ host: "Claude", claudeAvailable: true, codexAvailable: true }).reviewer === "codex",
  );

  // F11: host-family normalisation — vendor names and model ids map to a family; unknowns refuse.
  for (const [host, want] of [
    ["anthropic", "codex"],
    ["claude-opus-5", "codex"],
    ["anthropic/claude-sonnet-4", "codex"],
    ["opus-5", "codex"],
    ["gpt-6-astra", "claude"],
    ["codex", "claude"],
    ["openai", "claude"],
    ["o3-mini", "claude"],
  ]) {
    check(
      `seat rule: host ${JSON.stringify(host)}, both available -> reviewer ${want}`,
      (() => {
        const r = selectReviewerSeat({ host, claudeAvailable: true, codexAvailable: true });
        return r.ok === true && r.reviewer === want;
      })(),
    );
  }
  for (const [host, want] of [
    ["openrouter/openai/gpt-5", "claude"],
    ["openrouter/anthropic/claude-opus-5", "codex"],
    ["chatgpt-4o-latest", "claude"],
    ["o1", "claude"],
  ]) {
    check(
      `seat rule: host ${JSON.stringify(host)}, both available -> reviewer ${want}`,
      (() => {
        const r = selectReviewerSeat({ host, claudeAvailable: true, codexAvailable: true });
        return r.ok === true && r.reviewer === want;
      })(),
    );
  }
  for (const host of [
    "pi", "grok", "", "   ", "x-ai/grok-build-0.1", "some-unknown-model", null, 42,
    "eleutherai/gpt-j-6b", "nomic/gpt4all", "openrouter/eleutherai/gpt-j-6b", "gpt4all", "o3x", "openrouter/",
  ]) {
    check(
      `seat rule: unknown host ${JSON.stringify(host)} -> refused (ok:false, reviewer:null)`,
      (() => {
        const r = selectReviewerSeat({ host, claudeAvailable: true, codexAvailable: true });
        return r.ok === false && r.reviewer === null && hostFamily(host) === null;
      })(),
    );
  }
  check(
    "hostFamily: anthropic -> claude, gpt-6-astra -> codex, pi -> null",
    hostFamily("anthropic") === "claude" && hostFamily("gpt-6-astra") === "codex" && hostFamily("pi") === null,
  );

  // Unattended apply-rule filter.
  {
    const claims = [
      { id: "C1", verdict: "ACCEPT" },
      { id: "C2", verdict: "PARTIAL" },
      { id: "C3", verdict: "REJECT" },
      { id: "C4", verdict: "CANNOT VERIFY" },
    ];
    const partition = partitionAdjudication(claims, ["Is X safe to do unattended?"]);
    check("apply rule: ACCEPT is applied", partition.apply.some((c) => c.id === "C1"));
    check("apply rule: PARTIAL is applied", partition.apply.some((c) => c.id === "C2"));
    check("apply rule: apply list is exactly ACCEPT+PARTIAL", partition.apply.length === 2);
    check("apply rule: REJECT is dropped, not applied", partition.dropped.length === 1 && partition.dropped[0].id === "C3");
    check(
      "apply rule: CANNOT VERIFY is routed to the human-questions channel, not applied",
      partition.needsHuman.length === 1 &&
        partition.needsHuman[0].id === "C4" &&
        !partition.apply.some((c) => c.id === "C4"),
    );
    check(
      "apply rule: reviewer's Questions for a human pass through verbatim",
      partition.humanQuestions.includes("Is X safe to do unattended?"),
    );
  }
  check(
    "apply rule: lowercase verdict tokens still match (defensive normalization)",
    partitionAdjudication([{ id: "C5", verdict: "accept" }]).apply.length === 1,
  );
  check(
    "apply rule: an unrecognized verdict is fail-closed — never applied, never silently dropped",
    (() => {
      const p = partitionAdjudication([{ id: "C6", verdict: "MAYBE" }]);
      return p.apply.length === 0 && p.dropped.length === 0 && p.unrecognized.length === 1;
    })(),
  );
  check("apply rule: empty claim list is empty everywhere", (() => {
    const p = partitionAdjudication([]);
    return p.apply.length === 0 && p.dropped.length === 0 && p.needsHuman.length === 0 && p.unrecognized.length === 0;
  })());
  check(
    "apply rule: non-array claims degrades to empty rather than throwing",
    partitionAdjudication(undefined).apply.length === 0,
  );

  // hasXreviewShape content floor.
  check("shape: a real claim row counts", hasXreviewShape("### Claim table\n\n| C1 | a finding | bug | major | file:1 | fix it | high |\n"));
  check("shape: C0 no-findings row counts", hasXreviewShape("C0 | No findings | — | — | reviewed x | none | high"));
  // The heading ALONE is not a review. `xreview` mandates that section, so a refusing seat emits
  // it too; accepting it was the bug the first version of this veto shipped with.
  check("shape: the bare '### Claim table' heading is NOT enough", !hasXreviewShape("### Claim table"));
  check(
    "shape: heading + an empty table with no rows is NOT enough",
    !hasXreviewShape("### Claim table\n\n| ID | Claim | Bucket | Severity |\n|---|---|---|---|\n"),
  );
  check("shape: chatter with no table is not shape-ok", !hasXreviewShape("Sure, I can help with that!"));
  check("shape: non-string is not shape-ok", !hasXreviewShape(null));
  // Unread-seat veto: an unread seat that reports "no findings" must NOT score green. These four are the
  // real shapes that door produced on Windows, not invented ones.
  check(
    "shape: unread veto — 'could not read' + a no-findings row is VETOED, never a clean review",
    !hasXreviewShape("I could not read the plan or repository.\n\nC0 | No findings | — | — | — | none | high"),
  );
  check(
    "shape: unread veto — 'blocked by policy' + a no-findings row is VETOED",
    !hasXreviewShape("The execution policy rejected git show: blocked by policy.\n\nC0 | No findings"),
  );
  check(
    "shape: unread veto — an 'unverified' scope report with a no-findings row is VETOED",
    !hasXreviewShape("Files, Patterns, Deps, APIs, Scope, Risk — unverified.\n\nC0 | No findings"),
  );
  check(
    "shape: veto never suppresses a REAL finding (a claim row wins over the veto word)",
    hasXreviewShape("### Claim table\n\n| C1 | some finding | bug | major | unverified by me | fix | high |\n"),
  );
  // THE case the first version of this veto let through: a refusing seat that follows the skill
  // format, so its refusal arrives WITH the mandated heading and a C0 row.
  // Real reviewers render the claim table with box-drawing borders, not ASCII pipes. Matching only
  // `|` would reject a genuine review and halt the gate on good work.
  check(
    "shape: a box-drawn (U+2502) claim row is a REAL review, not a false reject",
    hasXreviewShape("### Claim table\n\n│ ID │ Claim │\n│ C1 │ a real bug │\n"),
  );
  check(
    "shape: a box-drawn refusal + C0 is still VETOED",
    !hasXreviewShape("I could not read the repository.\n\n│ C0 │ No findings │"),
  );
  check(
    "shape: unread veto — a skill-compliant refusal (heading + C0 + 'could not read') is VETOED",
    !hasXreviewShape(
      "### Independence\nI could not read the repository; blocked by policy.\n\n### Claim table\n\n| ID | Claim |\n| C0 | No findings | — | — | unverified | — | — |",
    ),
  );

  // scrubSecrets.
  check(
    "scrub: redacts an OpenRouter-shaped key",
    scrubSecrets("key=sk-or-v1-abcdefghijklmnopqrstuvwxyz0123456789").includes("[REDACTED]"),
  );
  check("scrub: leaves ordinary text untouched", scrubSecrets("hello world") === "hello world");
  check("scrub: non-string passes through unchanged", scrubSecrets(null) === null);

  // resolveCliOnPath sanity — resolves a guaranteed-present executable (this very process's own
  // node binary's directory is on PATH in every environment that can run this script) without
  // requiring claude/codex to be installed, so --self-test stays offline everywhere.
  {
    const nodeDir = dirname(process.execPath);
    const env = { PATH: nodeDir };
    const resolved = resolveCliOnPath(process.platform === "win32" ? "node" : "node", env);
    check("resolveCliOnPath: finds node on a PATH containing it", !!resolved.command);
  }
  check(
    "resolveCliOnPath: reports a reason when nothing resolves",
    resolveCliOnPath("definitely-not-a-real-executable-xyz", { PATH: "" }).command === null,
  );

  // buildXreviewPromptText carries both inputs through untouched.
  {
    const prompt = buildXreviewPromptText({ skillText: "SKILL_MARKER", briefText: "BRIEF_MARKER" });
    check("prompt: carries the skill text", prompt.includes("SKILL_MARKER"));
    check("prompt: carries the brief text", prompt.includes("BRIEF_MARKER"));
  }

  // arg() presence-vs-value (B5): a present-but-empty/missing/option-shaped value must refuse,
  // never collapse onto the "not supplied" fallback branch. All calls below inject a fake argv so
  // this stays offline and independent of the real process.argv.
  check(
    "arg: flag absent entirely returns the fallback",
    arg("nope", "fallback-value", ["node", "script"]) === "fallback-value",
  );
  check(
    "arg: flag present with a real value returns that value",
    arg("host", "fallback", ["node", "script", "--host", "claude"]) === "claude",
  );
  check(
    'arg: --cwd "" refuses rather than silently defaulting to process.cwd() (B5 repro)',
    (() => {
      try {
        arg("cwd", process.cwd(), ["node", "script", "--cwd", ""]);
        return false;
      } catch (err) {
        return /non-empty value/.test(err.message);
      }
    })(),
  );
  check(
    "arg: flag present but missing a value (last argv token) refuses, not fallback",
    (() => {
      try {
        arg("cwd", "/default", ["node", "script", "--cwd"]);
        return false;
      } catch {
        return true;
      }
    })(),
  );
  check(
    'arg: a value that looks like another option (e.g. "--brief --out /x") refuses rather than swallowing it',
    (() => {
      try {
        arg("brief", undefined, ["node", "script", "--brief", "--out", "/tmp/x"]);
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

  // buildReceiptBase (B5): cwd + brief must be on every receipt so a wrong-tree/wrong-brief
  // review is detectable after the fact, without spawning a CLI or touching disk.
  check(
    "buildReceiptBase: carries host, cwd, and brief for audit",
    (() => {
      const base = buildReceiptBase({ host: "claude", cwd: "/repo/checkout", briefPath: "/tmp/brief.md" });
      return base.host === "claude" && base.cwd === "/repo/checkout" && base.brief === "/tmp/brief.md";
    })(),
  );

  console.log(
    failed === 0
      ? `\nCROSS_REVIEW_SELFTEST_OK ${passed}/${passed}`
      : `\nCROSS_REVIEW_SELFTEST_FAILED ${passed} passed, ${failed} failed`,
  );
  process.exit(failed === 0 ? 0 : 1);
}

function main() {
  if (hasFlag("self-test")) {
    selfTest();
    return;
  }

  // Each `arg()` call below can throw (B5: empty/missing/option-shaped value, or a duplicated
  // flag) — that is a malformed INVOCATION, so it belongs to this file's documented "1 usage
  // error" exit code, same as the pre-existing missing-required-flag check just below. Caught
  // here, deliberately narrow (only the flag-parsing calls), so a later internal fault (e.g.
  // `dispatchReviewer`'s `mkdirSync`/`writeFileSync`) is NOT mistaken for a usage error — that
  // case is handled by the `isMainModule()` wrapper's own error boundary at the bottom of this
  // file, which exits 4 instead.
  let host, briefPath, outArg, cwdArg, timeoutMs;
  try {
    host = arg("host");
    briefPath = arg("brief");
    outArg = arg("out");
    cwdArg = arg("cwd", process.cwd());
    timeoutMs = Number(arg("timeout", String(DEFAULT_DISPATCH_TIMEOUT_MS))) || DEFAULT_DISPATCH_TIMEOUT_MS;
  } catch (err) {
    console.error(`CROSS_REVIEW_DISPATCH_ERR ${err instanceof Error ? err.message : String(err)}`);
    process.exit(1);
    return;
  }

  if (!host || !briefPath || !outArg) {
    console.error("CROSS_REVIEW_DISPATCH_ERR missing required --host/--brief/--out");
    process.exit(1);
  }

  const cwd = resolve(cwdArg);
  const briefAbsPath = resolve(briefPath);
  const outDir = resolve(outArg);

  const receipt = dispatchReviewer({ host, briefPath: briefAbsPath, outDir, cwd, timeoutMs });

  if (!receipt.ok && receipt.reviewer === null) {
    console.log(`CROSS_REVIEW_NO_SEAT host=${host} — ${scrubSecrets(receipt.reason)}`);
    process.exit(2);
  }
  if (!receipt.ok) {
    console.log(`CROSS_REVIEW_DISPATCH_FAILED host=${host} reviewer=${receipt.reviewer} — ${scrubSecrets(receipt.reason)}`);
    process.exit(3);
  }
  console.log(`CROSS_REVIEW_DISPATCH_OK host=${host} reviewer=${receipt.reviewer} log=${receipt.log}`);
  process.exit(0);
}

// Error boundary: without it,
// an internal fault inside `dispatchReviewer` (e.g. `mkdirSync`/`writeFileSync` failing on a
// read-only or missing `--out` parent) surfaces as an uncaught stack and Node's default exit 1 —
// but this file's own documented contract reserves 1 for a USAGE error, not an internal one. Exit
// 4 keeps that contract honest while still failing loudly (stack on stderr, non-zero exit) rather
// than silently.
if (isMainModule()) {
  try {
    main();
  } catch (err) {
    process.stderr.write(
      `CROSS_REVIEW_DISPATCH_INTERNAL_ERR ${err instanceof Error ? err.stack || err.message : String(err)}\n`,
    );
    process.exit(4);
  }
}
