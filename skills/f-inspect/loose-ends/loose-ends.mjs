#!/usr/bin/env node
// Review-time sibling check. For a branch (or any range), list:
//   1. other places that repeat the lines it replaced and that it did NOT touch,
//   2. new functions that look like an existing one (call it instead?),
//   3. test files whose checks got weaker (assertions removed, expected values changed).
// No model call and nothing leaves the machine: the reader (the lens-loose-ends agent,
// or a person) decides which candidates carry the same rule.
//
//   node skills/f-inspect/loose-ends/loose-ends.mjs [base | base..head] [--repo <dir>]
//        [--json] [--max <n>] [--max-new <n>] [--exclude <regex>]
//
// base defaults to the merge-base with origin/main (then main, origin/master, master).
// The diff is base -> working tree, so uncommitted changes count as part of the branch.
// Known limit: a hunk that only ADDS lines has nothing to match on, so a new rule that
// should also go somewhere else is not found.
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { CODE_FILE, SKIP_PATH, buildIndex, candidates, loadTs } from "./detect.mjs";
import { isPython } from "./python.mjs";
import { addedFunctions, buildFunctionIndex, reuseCandidates, usesExisting } from "./reuse.mjs";
import { ignoredBy } from "./ignore.mjs";
import { TEST_FILE, weakeningTriggers } from "./tests.mjs";

const gitRoot = (dir) => execFileSync("git", ["-C", dir, "rev-parse", "--show-toplevel"], { encoding: "utf8" }).trim();
const norm = (t) => t.replace(/\r\n/g, "\n");

const args = process.argv.slice(2);
const flag = (name) => { const i = args.indexOf(name); return i < 0 ? null : args.splice(i, 2)[1]; };
const repoArg = flag("--repo"), max = +(flag("--max") ?? 40), maxNew = +(flag("--max-new") ?? 50), excludeArg = flag("--exclude");
const asJson = args.includes("--json");
const root = gitRoot(repoArg ?? process.cwd());
const git = (...a) => execFileSync("git", ["-C", root, ...a], { encoding: "utf8", maxBuffer: 1 << 28, stdio: ["ignore", "pipe", "ignore"] });
const tryGit = (...a) => { try { return git(...a).trim(); } catch { return null; } };
/** `rev:path` for many paths with one `git cat-file --batch` (a process per file is slow). */
function catFiles(rev, ps) {
  const out = new Map();
  if (!ps.length) return out;
  const buf = execFileSync("git", ["-C", root, "cat-file", "--batch"], { input: ps.map((p) => `${rev}:${p}`).join("\n") + "\n", maxBuffer: 1 << 30 });
  let at = 0;
  for (const p of ps) {
    const nl = buf.indexOf(10, at), header = buf.toString("utf8", at, nl);
    if (header.endsWith(" missing")) { at = nl + 1; continue; }
    const size = +header.split(" ")[2];
    out.set(p, buf.toString("utf8", nl + 1, nl + 1 + size));
    at = nl + 1 + size + 1;
  }
  return out;
}

// "A..B" reviews a finished range (e.g. a merged commit); a bare base compares with the working tree.
const spec = args.find((a) => !a.startsWith("--"));
const [base, head] = spec?.includes("..") ? spec.split("..") : [spec
  ?? ["origin/main", "main", "origin/master", "master"].map((b) => tryGit("merge-base", "HEAD", b)).find(Boolean), null];
if (!base) { console.error("loose-ends: no base given and no main/master branch to compare with"); process.exit(1); }

// Hunks of base -> working tree, old and new line ranges plus their text.
const files = new Map(); // path -> { deleted, hunks: [{ os, oe, ns, ne, old: [], new: [] }] }
let cur = null, hunk = null;
for (const line of git("diff", "-U0", "--no-renames", "--no-color", base, ...(head ? [head] : [])).split("\n")) {
  let m;
  if ((m = line.match(/^diff --git a\/(.+) b\/(.+)$/))) { cur = { path: m[1], deleted: false, hunks: [] }; files.set(cur.path, cur); hunk = null; }
  else if (line === "+++ /dev/null" && cur) cur.deleted = true;
  else if ((m = line.match(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/)) && cur) {
    const os = +m[1], ob = m[2] === undefined ? 1 : +m[2], ns = +m[3], nb = m[4] === undefined ? 1 : +m[4];
    hunk = { os, oe: os + ob - 1, ob, ns, ne: ns + nb - 1, nb, old: [], new: [] };
    cur.hunks.push(hunk);
  } else if (hunk && line.startsWith("-") && !line.startsWith("---")) hunk.old.push(line.slice(1));
  else if (hunk && line.startsWith("+") && !line.startsWith("+++")) hunk.new.push(line.slice(1));
}

// Index the repo as it was at base. Against the working tree, a file the diff leaves
// alone is the same on disk; for a finished range, today's disk is NOT base, so every
// file comes from git.
const ignored = ignoredBy(root);
// Folders that hold copies, not the product: vendored or reference code and saved work
// records and their helper scripts (probe copies, captures): one new function can match
// dozens of saved probe copies of its own file. --exclude <regex> adds more.
const NOT_PRODUCT = /(^|\/)(vendor|vendored|third_party|third-party|external|[\w.-]+-ref|work-sessions|foreman|scratch|captures?|fixtures?|snapshots?)\//i;
const exclude = excludeArg ? new RegExp(excludeArg) : null;
// Without the `typescript` package only Python is parsed; JS/TS files are then reported
// as not scanned.
const ts = loadTs(root);
const CODE = ts ? CODE_FILE : /\.pyi?$/;
const indexable = (p) => CODE.test(p) && !SKIP_PATH.test(p) && !NOT_PRODUCT.test(p) && !exclude?.test(p) && !ignored(p);
const texts = new Map();
const paths = git("ls-tree", "-r", "--name-only", base).split("\n").filter(indexable);
const fromGit = paths.filter((p) => head || files.has(p));
for (const p of paths) if (!head && !files.has(p) && existsSync(join(root, p))) texts.set(p, norm(readFileSync(join(root, p), "utf8")));
for (const [p, t] of catFiles(base, fromGit)) texts.set(p, norm(t));
const ix = buildIndex(ts, texts);

// A base line in a changed file -> its line now (shifted by the hunks above it).
const toNow = (path, line) => {
  let shift = 0;
  for (const h of files.get(path)?.hunks ?? []) if (h.ob === 0 ? h.os < line : h.oe < line) shift += h.nb - h.ob;
  return line + shift;
};
const touched = (path, s, e) => {
  const f = files.get(path);
  return f && (f.deleted || f.hunks.some((h) => h.ob > 0 && h.os <= e && s <= h.oe));
};

const HUNK_LINES = 20;
const clip = (ls) => ls.slice(0, HUNK_LINES).join("\n") + (ls.length > HUNK_LINES ? `\n… (${ls.length - HUNK_LINES} more lines: git diff the range to see them)` : "");
const groups = [];
const listed = []; // every place listed so far, in base lines: each place is listed once
for (const [path, f] of files) {
  // Seeds come from code files that existed at base; test tables are not rule copies.
  if (!texts.has(path) || TEST_FILE.test(path)) continue;
  for (const h of f.hunks) {
    if (h.ob === 0) continue; // pure insertion: nothing to match on
    const hits = [];
    for (const c of candidates(ix, path, h.os, h.oe).hits) {
      if (touched(c.path, c.s, c.e)) continue;
      // Compare in base lines (both sides), across hunks too: each place is listed once.
      const seen = listed.find((x) => x.path === c.path && x.s <= c.e + 1 && c.s <= x.e + 1);
      if (seen) { if (seen.hit !== null && !seen.hit.alsoFor.includes(`${path}:${h.ns}`) && seen.group !== `${path}:${h.ns}`) seen.hit.alsoFor.push(`${path}:${h.ns}`); continue; }
      const lines = texts.get(c.path).split("\n");
      const hit = { path: c.path, s: toNow(c.path, c.s), e: toNow(c.path, c.e), via: c.via, cover: +(c.cover ?? 0).toFixed(2), code: lines.slice(c.s - 1, Math.min(c.e, c.s + 11)).join("\n"), alsoFor: [] };
      listed.push({ path: c.path, s: c.s, e: c.e, hit, group: `${path}:${h.ns}` });
      hits.push(hit);
    }
    if (hits.length) groups.push({ path, ns: h.ns, ne: Math.max(h.ns, h.ne), old: clip(h.old), new: clip(h.new), hits });
  }
}
// Changed files the script cannot read (config, docs, HTML, other languages): the
// reviewer checks these by hand; a missed change is often in one of them.
const unscanned = [...files.keys()].filter((p) => !CODE.test(p));
// Strongest matches first; cap the total so the list stays reviewable.
groups.sort((a, b) => Math.max(...b.hits.map((h) => h.cover)) - Math.max(...a.hits.map((h) => h.cover)));
let left = max;
for (const g of groups) { g.hits = g.hits.sort((a, b) => b.cover - a.cover).slice(0, Math.max(0, left)); left -= g.hits.length; }
const shown = groups.filter((g) => g.hits.length);

// ---- New functions that may duplicate an existing one.
// Vocabulary (BM25) + renamed-copy search over the repo at base, tests skipped.
// The scores do not separate real duplicates from new code, so only the top 2 per
// function are listed and the reader judges. A same-named function elsewhere stays:
// it is often the twin. At most --max-new functions per review, strongest first.
const head8 = (code) => code.split("\n").slice(0, 8).join("\n");
const nowText = (p) => head ? tryGit("show", `${head}:${p}`) : (existsSync(join(root, p)) ? readFileSync(join(root, p), "utf8") : null);
const fnIndex = buildFunctionIndex(ts, texts, { skip: TEST_FILE });
// A candidate must still exist after the change. A moved or deleted file, or a function
// the change renamed or removed, is the old copy of the new code, not something to reuse.
const headCache = new Map();
const stillThere = (p, name) => {
  const f = files.get(p);
  if (!f) return true; // untouched file
  if (f.deleted) return false;
  if (!headCache.has(p)) headCache.set(p, nowText(p) ?? "");
  return new RegExp(`(^|[^\\w$])${name.replace(/[$]/g, "\\$")}\\s*[(=:<]`, "m").test(headCache.get(p));
};
const reuse = [];
for (const [path, f] of files) {
  if (f.deleted || !indexable(path) || TEST_FILE.test(path)) continue;
  const after = nowText(path);
  if (after === null) continue;
  const now = norm(after);
  for (const fn of addedFunctions(ts, path, texts.get(path) ?? "", now)) {
    const cands = reuseCandidates(fnIndex, fn.code, { path, bm: 2 })
      .filter((c) => isPython(c.path) === isPython(path) && !usesExisting(c.name, now) && stillThere(c.path, c.name))
      .map(({ path: p, name, s: cs, e: ce, via, score, code }) => ({ path: p, name, s: toNow(p, cs), e: toNow(p, ce), via, score, code: head8(code) }));
    if (cands.length) reuse.push({ path, name: fn.name, s: fn.s, e: fn.e, code: head8(fn.code), candidates: cands });
  }
}

const newFns = reuse.length;
// Strongest first: a renamed copy, then the highest vocabulary score.
const strength = (r) => Math.max(...r.candidates.map((c) => (c.via === "renamed copy" ? 1000 : 0) + c.score));
reuse.sort((a, b) => strength(b) - strength(a));
reuse.splice(maxNew);

// ---- Test files whose checks got weaker: assertions removed (net), expected values
// changed, assertions commented out, skips added (plain triggers, no judge).
const tests = [];
for (const [path, f] of files) {
  if (!TEST_FILE.test(path) || !texts.has(path)) continue;
  const after = f.deleted ? "" : nowText(path);
  if (after === null) continue;
  const reasons = f.deleted ? ["deletes the test file"] : weakeningTriggers(texts.get(path), norm(after));
  // Rewrites alone (same number of assertions, new shape) are not listed: they are
  // nearly always a test following the code or getting stricter.
  if (reasons.some((r) => !r.startsWith("rewrites"))) tests.push({ path, reasons, hunks: f.hunks.filter((h) => h.old.length).map((h) => `${h.ns}`).slice(0, 8) });
}

const total = shown.reduce((n, g) => n + g.hits.length, 0);
const tsNote = ts ? null : "JS/TS files were not scanned: the `typescript` package was not found (npm install -g typescript).";
if (asJson) { console.log(JSON.stringify({ root, base, head: head ?? "working tree", changedFiles: files.size, groups: shown, newFunctions: newFns, reuse, tests, unscanned, note: tsNote }, null, 2)); process.exit(0); }
if (tsNote) console.log(`Note: ${tsNote}\n`);
console.log(`loose-ends: ${root}\n${base.slice(0, 10)} -> ${head ? head.slice(0, 10) : "working tree"} · ${files.size} file(s) changed · ${total} untouched copy candidate(s) · ${newFns} new function(s) with look-alikes${newFns > reuse.length ? ` (first ${reuse.length} listed)` : ""} · ${tests.length} test file(s) with weaker checks\n`);
if (shown.length) console.log("## Copies the change did not touch\n");
for (const g of shown) {
  console.log(`== changed ${g.path}:${g.ns}-${g.ne}`);
  if (g.old) console.log(g.old.split("\n").map((l) => `  - ${l}`).join("\n"));
  if (g.new) console.log(g.new.split("\n").map((l) => `  + ${l}`).join("\n"));
  for (const h of g.hits) {
    console.log(`\n  -> ${h.path}:${h.s}-${h.e}  (found by ${h.via}, match ${h.cover})${h.alsoFor.length ? `  · also matches the change at ${h.alsoFor.join(", ")}` : ""}`);
    console.log(h.code.split("\n").map((l) => `     | ${l}`).join("\n"));
  }
  console.log("");
}
if (reuse.length) console.log("## New functions that may duplicate existing ones\n");
for (const r of reuse) {
  console.log(`== new ${r.name}() ${r.path}:${r.s}-${r.e}`);
  console.log(r.code.split("\n").map((l) => `     | ${l}`).join("\n"));
  for (const c of r.candidates) {
    console.log(`\n  -> ${c.name}() ${c.path}:${c.s}-${c.e}  (found by ${c.via}, score ${c.score})`);
    console.log(c.code.split("\n").map((l) => `     | ${l}`).join("\n"));
  }
  console.log("");
}
if (tests.length) console.log("## Test files whose checks got weaker\n");
for (const t of tests) console.log(`== ${t.path}: ${t.reasons.join("; ")}${t.hunks.length ? `  (changed near lines ${t.hunks.join(", ")})` : ""}`);
if (unscanned.length) console.log(`\n## Changed files the script cannot read (check by hand)\n\n${unscanned.slice(0, 30).map((p) => `  ${p}`).join("\n")}${unscanned.length > 30 ? `\n  … and ${unscanned.length - 30} more` : ""}`);
if (!total && !reuse.length && !tests.length) console.log("Nothing found: no untouched copies, no look-alike new functions, no weaker tests. (Rules added from scratch are not checked.)");
