#!/usr/bin/env node
// The site walk's outside grader (METHOD.md §2 step 1a): a model from the other family grades the new session's cold
// site-walk answers against the answer key and the handover, so the session doesn't mark its own quiz alone.
//
//   node site_walk_grade.mjs --host <the foreman's model or family> --handover <file> --key <file> --answers <file> --out <file>
//                            [--job J<n>] [--timeout <seconds, default 900>]
//   node site_walk_grade.mjs --self-test
//
// Seat rule (the same as scripts/cross-review-dispatch.mjs): a claude foreman is graded by codex, a codex foreman by
// claude; any other host family is refused (an independent grader can't be proven). Both run read-only and headless.
// It grades only the COLD answers (the first answer to each question; never a re-answer or the session's own score).
// Writes the grader's full output to --out, then prints one line:
//   GRADED J<n>: right <a>, partial <b>, wrong <c>, missing <d>; blocking not right: [..]; key wrong: [..]
// and, below it, every question that isn't right with what was missed, for the session to re-answer.
// Exit: 0 graded (partials are re-learned, never a stop) · 3 a blocking question is wrong or missing (the site walk's
// stop) · 2 not graded (no seat, the CLI failed, no verdict line): the session records "not graded: <why>" and carries on.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

export function hostFamily(host) {
  if (typeof host !== "string") return null;
  let id = host.trim().toLowerCase();
  if (id.startsWith("openrouter/")) id = id.slice("openrouter/".length);
  if (!id) return null;
  const slash = id.indexOf("/");
  if (slash !== -1) { const v = id.slice(0, slash); return v === "anthropic" ? "claude" : v === "openai" ? "codex" : null; }
  if (id === "anthropic" || id === "claude" || id.startsWith("claude-") || /^(opus|sonnet|haiku|fable)/.test(id)) return "claude";
  if (id === "openai" || /^(gpt-|chatgpt|codex)/.test(id) || /^o[134](-|$)/.test(id)) return "codex";
  return null;
}

export function graderFor(host) {
  const f = hostFamily(host);
  return f === "claude" ? "codex" : f === "codex" ? "claude" : null;
}

export function prompt({ job, handover, key, answers }) {
  return `You are an independent grader of a coding agent's handover comprehension quiz (the site walk). Read three files:
HANDOVER: ${handover}  (its quiz questions are in the section numbered 8, or headed site walk / questions)
KEY: ${key}  (the expected answers; questions marked with the warning sign are blocking)
ANSWERS: ${answers}  (the new session's answers)
Grade only the COLD answers: the first answer the session gave to each quiz question. Ignore anything the file says was written after opening the key, any re-answers, and any score the session gave itself.
For each question write one line: Q<n> | right / partial / wrong / missing | blocking yes/no | what key point was missed, or 'ok'.
A partial means a point the key treats as essential is absent or vague; a wrong answer contradicts the key on substance. Be strict but fair: a different correct reading the key would accept is right. If the answer is better than the key (the key is wrong or stale, checked against the handover and the repo), mark it right and write KEY-WRONG and why.
Then on the very last line, alone, a JSON object:
{"job":"${job}","questions":N,"right":N,"partial":N,"wrong":N,"missing":N,"blocking_not_right":[question numbers],"blocking_wrong":[blocking questions that are wrong or missing],"key_wrong":[question numbers]}`;
}

export function parse(text) {
  const lines = String(text).trim().split(/\r?\n/);
  for (let i = lines.length - 1; i >= 0 && i >= lines.length - 5; i--) {
    const l = lines[i].trim().replace(/^```(json)?|```$/g, "").trim();
    if (!l.startsWith("{")) continue;
    try {
      const d = JSON.parse(l);
      if (typeof d.questions === "number" && Array.isArray(d.blocking_not_right)) {
        d.blocking_wrong = Array.isArray(d.blocking_wrong) ? d.blocking_wrong : [];
        d.key_wrong = Array.isArray(d.key_wrong) ? d.key_wrong : [];
        return d;
      }
    } catch {}
  }
  return null;
}

export function notRight(text) {
  return String(text).split(/\r?\n/).map((l) => l.replace(/^[*\s-]+/, "").trim())
    .filter((l) => /^Q\d+\s*\|\s*(partial|wrong|missing)\b/i.test(l) || /KEY-WRONG/.test(l));
}

function run(grader, text, timeoutS) {
  const cmd = process.env.SITE_WALK_GRADER_CMD; // tests: a stand-in grader
  const [bin, args] = cmd ? [process.execPath, [cmd, grader]]
    : grader === "codex" ? ["codex", ["exec", "--sandbox", "read-only", "--skip-git-repo-check", "-c", "model_reasoning_effort=medium", "-"]]
    : ["claude", ["-p", "--permission-mode", "plan", "--tools", "Read,Grep,Glob", "--disallowedTools", "Edit,Write,NotebookEdit,Bash", "--no-session-persistence", "--output-format", "text"]];
  return spawnSync(bin, args, { input: text, encoding: "utf8", timeout: timeoutS * 1000, maxBuffer: 1 << 26, shell: !cmd && process.platform === "win32" });
}

export function grade(o, log = console.log) {
  for (const k of ["host", "handover", "key", "answers", "out"]) if (!o[k]) { log(`usage: --${k} is required`); return 2; }
  for (const k of ["handover", "key", "answers"]) if (!existsSync(o[k])) { log(`NOT GRADED: no ${k} file at ${o[k]}`); return 2; }
  const grader = graderFor(o.host);
  if (!grader) { log(`NOT GRADED: host ${JSON.stringify(o.host)} isn't a known family (claude or codex), so no independent grader can be seated`); return 2; }
  const job = o.job || (String(o.key).match(/J\d+/) || ["J?"])[0];
  const r = run(grader, prompt({ job, handover: o.handover, key: o.key, answers: o.answers }), Number(o.timeout) || 900);
  const out = `# ${job} site walk: outside grade\n\nGrader: ${grader} (host ${o.host}), ${new Date().toISOString()}. Cold answers only.\n\n${r.stdout || ""}\n`;
  writeFileSync(o.out, out);
  if (r.error || r.status !== 0) { log(`NOT GRADED: the ${grader} grader ${r.error ? "failed to start: " + r.error.message : "exited " + r.status}; see ${o.out}`); return 2; }
  const d = parse(r.stdout);
  if (!d) { log(`NOT GRADED: the ${grader} grader gave no verdict line; see ${o.out}`); return 2; }
  log(`GRADED ${job}: right ${d.right}, partial ${d.partial}, wrong ${d.wrong}, missing ${d.missing}; blocking not right: [${d.blocking_not_right.join(", ")}]; key wrong: [${d.key_wrong.join(", ")}]`);
  for (const l of notRight(r.stdout)) log("  " + l);
  return d.blocking_wrong.length ? 3 : 0;
}

function selfTest() {
  const res = [], check = (n, ok) => res.push(`${ok ? "ok" : "FAIL"} ${n}`);
  const tmp = mkdtempSync(join(tmpdir(), "swg-"));
  try {
    for (const f of ["h.md", "k.md", "a.md"]) writeFileSync(join(tmp, f), "x\n");
    const fake = join(tmp, "fake.mjs");
    const say = (body) => writeFileSync(fake, `process.stdin.resume();process.stdin.on("end",()=>{process.stdout.write(${JSON.stringify(body)})});`);
    const o = { host: "claude-opus-5-5", handover: join(tmp, "h.md"), key: join(tmp, "k.md"), answers: join(tmp, "a.md"), out: join(tmp, "g.md"), job: "J9" };
    process.env.SITE_WALK_GRADER_CMD = fake;
    check("seat: claude host -> codex grader, codex host -> claude, unknown -> none", graderFor("claude-opus-5-5") === "codex" && graderFor("gpt-6.1-sol") === "claude" && graderFor("pi") === null);
    say('Q1 | right | blocking yes | ok\nQ2 | partial | blocking yes | omits the cap stop\n{"job":"J9","questions":2,"right":1,"partial":1,"wrong":0,"missing":0,"blocking_not_right":[2],"blocking_wrong":[],"key_wrong":[]}\n');
    let logged = []; let code = grade(o, (l) => logged.push(l));
    check("partials grade and pass (exit 0) and list what to re-answer", code === 0 && logged[0].startsWith("GRADED J9: right 1, partial 1") && logged.some((l) => l.includes("Q2 | partial")) && readFileSync(o.out, "utf8").includes("omits the cap stop"));
    say('Q1 | wrong | blocking yes | contradicts the key\n{"job":"J9","questions":1,"right":0,"partial":0,"wrong":1,"missing":0,"blocking_not_right":[1],"blocking_wrong":[1],"key_wrong":[]}');
    check("a blocking wrong answer is the stop (exit 3)", grade(o, () => {}) === 3);
    say("no verdict here\n");
    check("no verdict line: not graded (exit 2), never a pass", grade(o, () => {}) === 2);
    say('Q3 | right | blocking no | KEY-WRONG: the key names the old file\n```json\n{"job":"J9","questions":1,"right":1,"partial":0,"wrong":0,"missing":0,"blocking_not_right":[],"key_wrong":[3]}\n```');
    logged = []; code = grade(o, (l) => logged.push(l));
    check("a fenced verdict parses; a wrong key is reported", code === 0 && logged[0].includes("key wrong: [3]") && logged.some((l) => l.includes("KEY-WRONG")));
    check("an unknown host family is refused, not defaulted", grade({ ...o, host: "pi" }, () => {}) === 2);
    check("a missing file is not graded", grade({ ...o, key: join(tmp, "none.md") }, () => {}) === 2);
  } catch (e) { res.push(`FAIL exception: ${e.message}`); }
  finally { delete process.env.SITE_WALK_GRADER_CMD; rmSync(tmp, { recursive: true, force: true }); }
  console.log(res.join("\n"));
  process.exit(res.every((r) => r.startsWith("ok")) ? 0 : 1);
}

const isMain = (() => { try { return fileURLToPath(import.meta.url) === (process.argv[1] && join(process.argv[1])); } catch { return false; } })();
if (isMain) {
  const a = process.argv.slice(2);
  if (a[0] === "--self-test") selfTest();
  else {
    const o = {};
    for (let i = 0; i < a.length; i++) { if (a[i].startsWith("--")) o[a[i].slice(2)] = a[++i]; else { console.log(`unknown argument ${a[i]}`); process.exit(2); } }
    process.exit(grade(o));
  }
}
