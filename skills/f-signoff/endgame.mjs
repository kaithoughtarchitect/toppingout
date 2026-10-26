#!/usr/bin/env node
/**
 * endgame.mjs: the two locks around a job close.
 *
 *   node endgame.mjs verify-merge --repo <target repo> --merge <sha> [--main <remote>/<main>]
 *        Lock 1, run by /f-signoff before it writes anything: a build job closes only on a merge
 *        commit that exists and is reachable from <remote>/<main> (default origin/main). Fetch first.
 *
 *   node endgame.mjs open  --job <id> [--root <records root>]
 *   node endgame.mjs tick  <step> --file <path> [--opener <path>, handover only] [--root <records root>]
 *   node endgame.mjs check [--root <records root>]
 *   node endgame.mjs clear [--root <records root>]
 *        Lock 2, the end-game: /f-signoff opens foreman/ENDGAME-PENDING.md listing the steps the job
 *        still owes; each step ticks its line with the file it wrote (it must exist; the board step's is the
 *        project's BOARD.json: every project has a board, no step is skippable); the handover step clears
 *        it once every line is ticked. /f-survey,
 *        /f-blueprint, /f-schedule, /f-shift and work order 1 run `check` first and stop while it exists.
 *
 *   node endgame.mjs hash <job file>
 *        f-signoff's job-file hash: the checkpoint block removed, CRLF to LF, blank-line runs collapsed (job files
 *        only; other close targets are plain sha256).
 *
 *   node endgame.mjs --self-test
 *
 * Steps, in order: dev-report, next-ticket-decision, ground-investigation, board, handover. The decision must name
 * the board version it chose from ("board v<n>"); the ground investigation ticks a JOB-<next>-GROUND-INVESTIGATION.md
 * (METHOD.md §10 step 7b). When the decision says "Topping out: yes" (the board's head is reached, METHOD.md §11b),
 * the same steps take the topping-out files instead: the report (TOPPING-OUT-REPORT.md) in place of the
 * ground investigation, a topped-out BOARD.json, and NEXT-HEADS.md in place of the handover (no opener).
 * The ground-investigation, board and handover ticks also need
 * the decision's filled "Owner confirmed:" line (step 7a: the owner's words, or the standing goal's under a /goal).
 * Exit codes: 0 ok (check: nothing pending) · 1 refused (pending steps, unmerged, untickable) ·
 * 2 bad usage · 3 error (git or file failure). An error is never read as "nothing pending".
 */
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

export const STEPS = ["dev-report", "next-ticket-decision", "ground-investigation", "board", "handover"];
// a lock opened before a step existed reads that step as done, so an end game in flight is never blocked by an upgrade
const ADDED_LATER = ["ground-investigation"];
const LOCK = (root) => join(root, "foreman", "ENDGAME-PENDING.md");
const LINE = /^- \[( |x)\] ([a-z-]+)(?: · (.*))?$/;
// step 7a: the next-ticket decision carries the owner's confirmation (or the standing goal's words); the template's "<…>" placeholder doesn't count
export function confirmed(text) {
  const line = text.split(/\r?\n/).map((l) => l.replace(/\*/g, "").trim()).find((l) => l.startsWith("Owner confirmed:"));
  const value = line ? line.slice("Owner confirmed:".length).trim() : "";
  return value !== "" && !value.startsWith("<");
}

class Refused extends Error {}
class Usage extends Error {}

// Same contract as cross-review-dispatch.mjs's arg(): a repeated or empty flag is refused, never guessed.
// Each skill carries its own copy because each installs on its own (a skill can't import from scripts/).
function arg(name, fallback, argv = process.argv) {
  const flag = `--${name}`;
  const at = argv.flatMap((a, i) => (a === flag ? [i] : []));
  if (at.length === 0) return fallback;
  if (at.length > 1) throw new Usage(`${flag} was supplied ${at.length} times`);
  const v = argv[at[0] + 1];
  if (v === undefined || v === "" || v.startsWith("--")) throw new Usage(`${flag} needs a non-empty value`);
  return v;
}

/** Pure. Parse the lock file into {job, steps:{name:{done, note}}}; throws on a malformed file. */
export function parseLock(text) {
  const job = (text.match(/^job: (.+)$/m) || [])[1];
  if (!job) throw new Error("ENDGAME-PENDING.md has no 'job:' line");
  const steps = {};
  for (const l of text.split(/\r?\n/)) {
    const m = LINE.exec(l);
    if (m) steps[m[2]] = { done: m[1] === "x", note: m[3] || "" };
  }
  for (const s of ADDED_LATER) if (!steps[s]) steps[s] = { done: true, note: "(lock opened before this step existed)" };
  for (const s of STEPS) if (!steps[s]) throw new Error(`ENDGAME-PENDING.md is missing the step '${s}'`);
  return { job, steps };
}

/** Pure. The lock file's text for {job, steps}. */
export function renderLock({ job, steps }) {
  return [
    "# End-game pending",
    "",
    `job: ${job}`,
    "",
    "Written by /f-signoff. No survey, blueprint, schedule, shift or work order 1 runs until every",
    "line is ticked and the handover step clears this file (`skills/f-signoff/endgame.mjs`).",
    "",
    ...STEPS.map((s) => `- [${steps[s].done ? "x" : " "}] ${s}${steps[s].note ? ` · ${steps[s].note}` : ""}`),
    "",
  ].join("\n");
}

function read(root) {
  const p = LOCK(root);
  return existsSync(p) ? parseLock(readFileSync(p, "utf8")) : null;
}

export function open(root, job) {
  const cur = read(root);
  if (cur) throw new Refused(`an end-game is already pending for job ${cur.job}; finish it first`);
  mkdirSync(join(root, "foreman"), { recursive: true });
  const steps = Object.fromEntries(STEPS.map((s) => [s, { done: false, note: "" }]));
  writeFileSync(LOCK(root), renderLock({ job, steps }));
  return `opened the end-game for job ${job}: ${STEPS.join(" -> ")}`;
}

// the next-ticket decision names the board version it was chosen from (the template's "v<n>" doesn't count)
export function citesBoard(text) {
  return /board\W{0,8}v\d+/i.test(text);
}

// the decision says the board's head is reached: "Topping out: yes" (the template's "no | yes" doesn't count)
export function toppingOut(text) {
  return text.split(/\r?\n/).map((l) => l.replace(/\*/g, "").replace(/^[-#>\s]+/, "").trim()).some((l) => /^Topping out:\s*yes\b/i.test(l));
}

// f-signoff's job-file hash: drop the "## Close Mutation Checkpoints" block (to the next "## " heading or the end),
// CRLF -> LF, collapse every run of blank lines to one, then sha256 (so rewriting the block never changes the hash)
export function jobFileHash(text) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let skipping = false;
  for (const l of lines) {
    if (/^## Close Mutation Checkpoints\b/.test(l)) { skipping = true; continue; }
    if (skipping && /^## /.test(l)) skipping = false;
    if (!skipping) out.push(l);
  }
  const body = out.join("\n").replace(/\n{3,}/g, "\n\n");
  return createHash("sha256").update(body, "utf8").digest("hex");
}

// an opener still carrying a template blank ("<N>", "<absolute path to …>") isn't ready to paste
export function openerBlanks(text) {
  return [...text.matchAll(/<[^<>\r\n]{1,80}>/g)].map((m) => m[0]);
}

export function tick(root, step, { file, na, opener }) {
  const cur = read(root);
  if (!cur) throw new Refused("no end-game is pending");
  if (!STEPS.includes(step)) throw new Usage(`unknown step '${step}' (one of ${STEPS.join(", ")})`);
  const before = STEPS.slice(0, STEPS.indexOf(step)).filter((s) => !cur.steps[s].done);
  if (before.length) throw new Refused(`'${step}' is out of order: still owed first: ${before.join(", ")}`);
  if (cur.steps[step].done) throw new Refused(`'${step}' is already ticked (${cur.steps[step].note}): a ticked step is never re-ticked, so the end game keeps the branch it started on`);
  if (na !== undefined) throw new Refused("--na is retired: every project has a board. Record the close on it (render_board.py <project>/BOARD.json close …), then tick board --file <project>/BOARD.json; no board yet: start one (render_board.py <project>/BOARD.json init)");
  if (!file) throw new Usage("tick needs --file <path>");
  if (!existsSync(resolve(root, file))) throw new Refused(`'${file}' doesn't exist: write it before ticking '${step}'`);
  // the branch is fixed when the decision is ticked (its note ends " (topping out)"), never re-read from a file that may have changed
  const ntdNote = cur.steps["next-ticket-decision"].note;
  const ntdPath = ntdNote.replace(/ \(topping out\)$/, "");
  const topping = / \(topping out\)$/.test(ntdNote);
  if (step !== "dev-report" && step !== "next-ticket-decision" && ntdPath && existsSync(resolve(root, ntdPath))
      && toppingOut(readFileSync(resolve(root, ntdPath), "utf8")) !== topping)
    throw new Refused(`${ntdPath} changed since it was ticked (it ${topping ? "topped out" : "named a next job"} then, and doesn't now): the end game keeps the branch it started on`);
  if (step === "ground-investigation" && topping && !/TOPPING-OUT-REPORT\.md$/i.test(file))
    throw new Refused(`the decision tops the project out: this step ticks the TOPPING-OUT-REPORT.md (METHOD.md §11b), not '${file}'`);
  if (step === "ground-investigation" && !topping && !/GROUND-INVESTIGATION\.md$/i.test(file))
    throw new Refused(`the ground-investigation step ticks the next job's JOB-<N>-GROUND-INVESTIGATION.md (METHOD.md §10 step 7b), not '${file}' (a topping out needs "Topping out: yes" in the decision when it is ticked)`);
  if (step === "board" && !/(^|[\\/])BOARD\.json$/.test(file))
    throw new Refused(`the board step ticks the project's BOARD.json, not '${file}': every project has a board (render_board.py <project>/BOARD.json init starts one)`);
  const text = readFileSync(resolve(root, file), "utf8");
  if (step === "next-ticket-decision" && !citesBoard(text))
    throw new Refused(`'${file}' doesn't say which board version it chose from: write "board v<n>" (render_board.py <project>/BOARD.json check)`);
  const note = step === "next-ticket-decision" && toppingOut(text) ? `${file} (topping out)` : file;
  if (step === "board") {
    let top = null;
    try { top = JSON.parse(text).topped_out || null; } catch { top = null; }
    if (topping && !(top && top.date && top.version && top.report))
      throw new Refused(`the decision tops the project out, but '${file}' isn't topped out: close the job, then render_board.py <project>/BOARD.json topout --report <report>`);
    if (!topping && top)
      throw new Refused(`'${file}' is topped out, but the decision named a next job: a topped-out board takes no next job`);
  }
  if (step === "handover" && topping) {
    if (!/NEXT-HEADS\.md$/i.test(file)) throw new Refused(`the decision tops the project out: the last step ticks NEXT-HEADS.md (the candidate next heads, METHOD.md §11b), not '${file}'`);
  } else if (step === "handover") {
    if (!opener) throw new Usage("the handover step also needs --opener foreman/handovers/OPENER-JOB-<next>.txt (the next session's opener, every blank filled)");
    if (!existsSync(resolve(root, opener))) throw new Refused(`'${opener}' doesn't exist: write the next session's opener from templates/SESSION-OPENER.txt before ticking the handover`);
    const blanks = openerBlanks(readFileSync(resolve(root, opener), "utf8"));
    if (blanks.length) throw new Refused(`'${opener}' still has template blanks: ${blanks.slice(0, 4).join(" ")}; fill every one before ticking the handover`);
  }
  if (step === "ground-investigation" || step === "board" || step === "handover") {
    if (!confirmed(readFileSync(resolve(root, ntdPath), "utf8")))
      throw new Refused(`'${step}' waits for step 7a: ${ntdPath} has no filled "Owner confirmed:" line (the owner's words, or the standing goal's)`);
  }
  cur.steps[step] = { done: true, note };
  writeFileSync(LOCK(root), renderLock(cur));
  return `ticked ${step} for job ${cur.job}`;
}

export function check(root) {
  const cur = read(root);
  if (!cur) return { pending: [] };
  return { job: cur.job, pending: STEPS.filter((s) => !cur.steps[s].done) };
}

export function clear(root) {
  const cur = read(root);
  if (!cur) throw new Refused("no end-game is pending");
  const owed = STEPS.filter((s) => !cur.steps[s].done);
  if (owed.length) throw new Refused(`can't clear job ${cur.job}: still owed: ${owed.join(", ")}`);
  rmSync(LOCK(root));
  return `end-game complete for job ${cur.job}; lock cleared`;
}

export function verifyMerge(repo, merge, main) {
  if (!/^[0-9a-f]{7,40}$/i.test(merge || "")) throw new Usage("--merge must be a 7-40 character commit sha");
  const git = (...a) => execFileSync("git", ["-C", repo, ...a], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
  let full;
  try { full = git("rev-parse", "--verify", `${merge}^{commit}`); }
  catch { throw new Refused(`merge ${merge} is not a commit in ${repo}: a build job closes only after its PR is merged (open the PR first)`); }
  try { git("rev-parse", "--verify", main); } catch { throw new Error(`can't read ${main} in ${repo} (fetch first)`); }
  try { git("merge-base", "--is-ancestor", full, main); }
  catch (e) {
    if (e.status === 1) throw new Refused(`commit ${full.slice(0, 7)} is not on ${main}: the job isn't merged yet`);
    throw e;
  }
  return `merge ${full.slice(0, 7)} is on ${main}`;
}

function selfTest() {
  const root = mkdtempSync(join(tmpdir(), "endgame-"));
  const results = [];
  const t = (name, fn) => { let ok; try { ok = fn() !== false; } catch (e) { ok = false; name += ` (${e.message})`; } results.push([ok, name]); };
  const refuses = (fn) => { try { fn(); return false; } catch (e) { return e instanceof Refused; } };
  try {
    t("nothing pending at the start", () => check(root).pending.length === 0);
    t("open writes the lock", () => open(root, "04") && existsSync(LOCK(root)));
    t("check names every step owed", () => check(root).pending.join() === STEPS.join());
    t("a second open is refused", () => refuses(() => open(root, "05")));
    t("ticking out of order is refused", () => refuses(() => tick(root, "next-ticket-decision", { file: "x" })));
    t("ticking with a missing file is refused", () => refuses(() => tick(root, "dev-report", { file: "nope.md" })));
    for (const f of ["dev.md", "ntd.md", "ho.md", "BOARD.json", "JOB-05-GROUND-INVESTIGATION.md"]) writeFileSync(join(root, f), "x");
    t("tick dev-report with its file", () => !!tick(root, "dev-report", { file: "dev.md" }));
    t("no step can be skipped", () => { try { tick(root, "next-ticket-decision", {}); return false; } catch (e) { return e instanceof Usage; } });
    t("clearing early is refused", () => refuses(() => clear(root)));
    t("a decision that names no board version is refused", () => refuses(() => tick(root, "next-ticket-decision", { file: "ntd.md" })));
    writeFileSync(join(root, "ntd.md"), "# decision\n\nChosen from the project board **v<n>**.\n");
    t("the template's board placeholder doesn't count", () => refuses(() => tick(root, "next-ticket-decision", { file: "ntd.md" })));
    writeFileSync(join(root, "ntd.md"), "# decision\n\nChosen from the project board **v6**.\n");
    t("tick next-ticket-decision citing board v6", () => !!tick(root, "next-ticket-decision", { file: "ntd.md" }));
    t("the board waits for the ground investigation", () => refuses(() => tick(root, "board", { file: "BOARD.json" })));
    t("the ground investigation waits for the owner's confirmation (7a)", () => refuses(() => tick(root, "ground-investigation", { file: "JOB-05-GROUND-INVESTIGATION.md" })));
    writeFileSync(join(root, "ntd.md"), "# decision\n\nChosen from the project board **v6**.\n\n**Owner confirmed:** <\"the owner's words\">\n");
    t("the template placeholder doesn't count as confirmed", () => refuses(() => tick(root, "ground-investigation", { file: "JOB-05-GROUND-INVESTIGATION.md" })));
    writeFileSync(join(root, "ntd.md"), "# decision\n\nChosen from the project board **v6**.\n\n**Owner confirmed:** decided under the standing goal \"run the demos through demo 6\"\n");
    t("the ground investigation only takes its own file", () => refuses(() => tick(root, "ground-investigation", { file: "ho.md" })));
    t("tick ground-investigation with its file", () => !!tick(root, "ground-investigation", { file: "JOB-05-GROUND-INVESTIGATION.md" }));
    t("--na is retired", () => refuses(() => tick(root, "board", { na: "hand-maintained project" })));
    t("the board step only takes the project's BOARD.json", () => refuses(() => tick(root, "board", { file: "ho.md" })));
    t("tick board with the board file", () => !!tick(root, "board", { file: "BOARD.json" }));
    t("the handover needs the next session's opener", () => { try { tick(root, "handover", { file: "ho.md" }); return false; } catch (e) { return e instanceof Usage; } });
    t("a missing opener is refused", () => refuses(() => tick(root, "handover", { file: "ho.md", opener: "OPENER-JOB-05.txt" })));
    writeFileSync(join(root, "OPENER-JOB-05.txt"), "You are the foreman for job <N> of <product>.\n");
    t("an opener with template blanks is refused", () => refuses(() => tick(root, "handover", { file: "ho.md", opener: "OPENER-JOB-05.txt" })));
    writeFileSync(join(root, "OPENER-JOB-05.txt"), "You are the foreman for job 05 of Demo: TICKET-05, the next thing.\n1. Run /f-shift.\n");
    t("tick handover with a filled opener", () => !!tick(root, "handover", { file: "ho.md", opener: "OPENER-JOB-05.txt" }));
    t("the ticked file parses back", () => parseLock(readFileSync(LOCK(root), "utf8")).steps.board.note === "BOARD.json");
    t("clear removes the lock", () => !!clear(root) && !existsSync(LOCK(root)));
    // the topping-out branch
    open(root, "09");
    writeFileSync(join(root, "dev9.md"), "x");
    tick(root, "dev-report", { file: "dev9.md" });
    writeFileSync(join(root, "ntd9.md"), "# decision\n\nChosen from the project board **v9**.\n\n**Topping out:** yes\n\n**Owner confirmed:** \"top it out\"\n");
    tick(root, "next-ticket-decision", { file: "ntd9.md" });
    writeFileSync(join(root, "TOPPING-OUT-REPORT.md"), "x");
    t("topping out: the investigation step refuses a ground investigation", () => refuses(() => tick(root, "ground-investigation", { file: "JOB-05-GROUND-INVESTIGATION.md" })));
    t("topping out: the report ticks the investigation step", () => !!tick(root, "ground-investigation", { file: "TOPPING-OUT-REPORT.md" }));
    mkdirSync(join(root, "p"), { recursive: true });
    writeFileSync(join(root, "p", "BOARD.json"), JSON.stringify({ next: null }));
    t("topping out: a board that isn't topped out is refused", () => refuses(() => tick(root, "board", { file: "p/BOARD.json" })));
    writeFileSync(join(root, "p", "BOARD.json"), JSON.stringify({ next: null, topped_out: {} }));
    t("topping out: an empty topped_out is refused", () => refuses(() => tick(root, "board", { file: "p/BOARD.json" })));
    writeFileSync(join(root, "p", "BOARD.json"), JSON.stringify({ next: null, topped_out: { date: "2026-10-13", version: 9, report: "r", carried: [] } }));
    t("topping out: a topped-out board ticks", () => !!tick(root, "board", { file: "p/BOARD.json" }));
    writeFileSync(join(root, "NEXT-HEADS.md"), "x");
    t("topping out: a handover file is refused (NEXT-HEADS.md instead)", () => refuses(() => tick(root, "handover", { file: "ho.md" })));
    t("topping out: NEXT-HEADS.md ticks the last step, no opener needed", () => !!tick(root, "handover", { file: "NEXT-HEADS.md" }));
    t("topping out: the lock clears", () => !!clear(root) && !existsSync(LOCK(root)));
    t("the template's 'Topping out: no | yes' doesn't count as yes", () => !toppingOut("**Topping out:** no | yes (the board's head is reached)"));
    t("the job-file hash ignores the checkpoint block, CRLF and blank-line runs", () => {
      const a = "# Job\n\nbody\n\n## Close Mutation Checkpoints\n- stage: pending\n\n## Phase 7\nend\n";
      const b = "# Job\r\n\r\n\r\nbody\r\n\r\n## Close Mutation Checkpoints\r\n- stage: complete\r\n- current: x\r\n\r\n## Phase 7\r\nend\r\n";
      return jobFileHash(a) === jobFileHash(b) && jobFileHash(a) !== jobFileHash(a.replace("body", "BODY"));
    });
    t("a bullet, heading or quote yes-line counts", () => toppingOut("- **Topping out:** yes") && toppingOut("## Topping out: yes") && toppingOut("> Topping out: yes"));
    // the branch is fixed at the decision tick
    open(root, "10");
    writeFileSync(join(root, "dev10.md"), "x");
    tick(root, "dev-report", { file: "dev10.md" });
    writeFileSync(join(root, "ntd10.md"), "# decision\n\nChosen from the project board **v10**.\n\n**Owner confirmed:** \"go on\"\n");
    tick(root, "next-ticket-decision", { file: "ntd10.md" });
    writeFileSync(join(root, "ntd10.md"), "# decision\n\nChosen from the project board **v10**.\n\n**Topping out:** yes\n\n**Owner confirmed:** \"go on\"\n");
    t("a decision changed after its tick is refused", () => refuses(() => tick(root, "ground-investigation", { file: "TOPPING-OUT-REPORT.md" })));
    t("re-ticking the decision is refused (no switching branch by a second tick)", () => refuses(() => tick(root, "next-ticket-decision", { file: "ntd10.md" })));
    writeFileSync(join(root, "ntd10.md"), "# decision\n\nChosen from the project board **v10**.\n\n**Owner confirmed:** \"go on\"\n");
    tick(root, "ground-investigation", { file: "JOB-05-GROUND-INVESTIGATION.md" });
    t("a next-job decision refuses a topped-out board", () => refuses(() => tick(root, "board", { file: "p/BOARD.json" })));
    t("re-ticking a done step after later ones is refused", () => refuses(() => tick(root, "next-ticket-decision", { file: "ntd10.md" })) && refuses(() => tick(root, "ground-investigation", { file: "TOPPING-OUT-REPORT.md" })));
    writeFileSync(join(root, "p", "half.json"), JSON.stringify({ topped_out: {} }));
    rmSync(LOCK(root));
    t("a lock from before the ground-investigation step still parses, with it done", () => {
      const old = parseLock("job: 09\n\n- [x] dev-report · d.md\n- [x] next-ticket-decision · n.md\n- [ ] board\n- [ ] handover\n");
      return old.steps["ground-investigation"].done && !old.steps.board.done;
    });
    t("a malformed lock is an error, not 'nothing pending'", () => {
      writeFileSync(LOCK(root), "# End-game pending\n");
      try { check(root); return false; } catch (e) { return !(e instanceof Refused); }
    });
    rmSync(LOCK(root));
    t("a repeated flag is refused", () => { try { arg("root", undefined, ["--root", "a", "--root", "b"]); return false; } catch (e) { return e instanceof Usage; } });
    // lock 1 against a throwaway repo
    const repo = join(root, "repo");
    mkdirSync(repo);
    const g = (...a) => execFileSync("git", ["-C", repo, ...a], { stdio: "ignore" });
    g("init", "-q", "-b", "main"); g("config", "user.email", "t@t"); g("config", "user.name", "t");
    writeFileSync(join(repo, "a"), "1"); g("add", "a"); g("commit", "-q", "-m", "a");
    g("checkout", "-q", "-b", "job"); writeFileSync(join(repo, "b"), "1"); g("add", "b"); g("commit", "-q", "-m", "b");
    const jobHead = execFileSync("git", ["-C", repo, "rev-parse", "HEAD"], { encoding: "utf8" }).trim();
    t("an unmerged job head is refused", () => refuses(() => verifyMerge(repo, jobHead, "main")));
    t("an unknown sha is refused", () => refuses(() => verifyMerge(repo, "deadbeefdeadbeef", "main")));
    g("checkout", "-q", "main"); g("merge", "-q", "--no-ff", "-m", "merge job", "job");
    const m = execFileSync("git", ["-C", repo, "rev-parse", "HEAD"], { encoding: "utf8" }).trim();
    t("a merge on main passes", () => !!verifyMerge(repo, m, "main"));
    t("an unreadable main is an error, not a pass", () => { try { verifyMerge(repo, m, "nosuch/main"); return false; } catch (e) { return !(e instanceof Refused); } });
  } finally { rmSync(root, { recursive: true, force: true }); }
  const failed = results.filter(([ok]) => !ok);
  for (const [ok, name] of results) console.log(`${ok ? "ok  " : "FAIL"} ${name}`);
  console.log(failed.length ? `ENDGAME_SELFTEST_FAIL ${failed.length}/${results.length}` : `ENDGAME_SELFTEST_OK ${results.length}/${results.length}`);
  process.exit(failed.length ? 1 : 0);
}

function main() {
  const argv = process.argv.slice(2);
  if (argv.includes("--self-test")) return selfTest();
  const cmd = argv[0];
  try {
    const root = resolve(arg("root", ".", argv));
    let out;
    if (cmd === "verify-merge") out = verifyMerge(arg("repo", ".", argv), arg("merge", undefined, argv), arg("main", "origin/main", argv));
    else if (cmd === "open") { const job = arg("job", undefined, argv); if (!job) throw new Usage("open needs --job"); out = open(root, job); }
    else if (cmd === "tick") out = tick(root, argv[1], { file: arg("file", undefined, argv), na: arg("na", undefined, argv), opener: arg("opener", undefined, argv) });
    else if (cmd === "clear") out = clear(root);
    else if (cmd === "check") {
      const r = check(root);
      if (r.pending.length) { console.log(`ENDGAME_PENDING job ${r.job}: still owed: ${r.pending.join(", ")}. Finish the end-game first (METHOD §10).`); process.exit(1); }
      out = "ENDGAME_CLEAR nothing pending";
    } else if (cmd === "hash") {
      const f = argv[1];
      if (!f || f.startsWith("--")) throw new Usage("hash needs a job file path");
      out = `${jobFileHash(readFileSync(resolve(f), "utf8"))}  ${f}`;
    } else throw new Usage("usage: endgame.mjs verify-merge|open|tick|check|clear|hash <job file>|--self-test (see the header)");
    console.log(out);
  } catch (e) {
    if (e instanceof Refused) { console.log(`ENDGAME_REFUSED ${e.message}`); process.exit(1); }
    if (e instanceof Usage) { console.error(`ENDGAME_USAGE ${e.message}`); process.exit(2); }
    console.error(`ENDGAME_ERROR ${String(e.stderr || e.message).trim().slice(0, 300)}`);
    process.exit(3);
  }
}

main();
