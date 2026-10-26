#!/usr/bin/env node
// The names check: finds the names kept out of records (the builders' model, vendor and tool names)
// in the records about to be committed. One script instead of a grep line: Git Bash's grep 3.0 aborts
// (exit 134, no output) on -i with several patterns, which reads as "no hits".
//
//   node names-check.mjs --names <names file> [--allow <allowed file>] --staged     every staged file (its staged content)
//   node names-check.mjs --names <names file> [--allow <allowed file>] <file>...    these files, as on disk
//   node names-check.mjs --self-test
//
// names file: one name per line, matched case-insensitively as a whole word (letters and digits are word
//   characters, so "pi" never matches "api" and "glm" never matches base64 noise). Blank lines are ignored.
// allowed file (optional): one context per line, e.g. a folder or a skill path that contains a name by design
//   (".pi/", "orca-pi-connect"). Each context is blanked out of a line before the names are matched, so the
//   rest of the line is still checked.
// Rendered board pages (board.html) are skipped: they are generated from BOARD.json, which is checked.
// A names line with regex characters (| ? * [ ] ( ) { } ^ $ \) is refused: older names files held grep patterns.
// Exit: 0 no hits; 1 hits (printed as path:line: text); 2 usage error, a missing or empty names file, or a read failure.

import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";

const fail = (msg) => { console.error(`names-check: ${msg}`); process.exit(2); };
const lines = (text) => text.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function scan(files, names, allowed) {
  const rx = names.map((n) => new RegExp(`(?<![A-Za-z0-9])${esc(n)}(?![A-Za-z0-9])`, "i"));
  const blank = allowed.map((a) => new RegExp(esc(a), "gi"));
  const hits = [];
  for (const [path, text] of files) {
    if (/(^|[\\/])board\.html$/i.test(path)) continue;
    text.split(/\r?\n/).forEach((line, i) => {
      let rest = line;
      for (const b of blank) rest = rest.replace(b, " ");
      if (rx.some((r) => r.test(rest))) hits.push(`${path}:${i + 1}: ${line.slice(0, 200)}`);
    });
  }
  return hits;
}

function selfTest() {
  const files = [
    ["a.md", "the pi builder ran\nsee orca-pi-connect\nskip .pi/ folder\napi call\nGLMx font\n.pi/ and the PI builder"],
    ["board.html", "data:abcglmzz pi"],
    ["b.md", "zz glm-4 here"],
  ];
  const got = scan(files, ["pi", "glm"], ["orca-pi-connect", ".pi/"]);
  const want = ["a.md:1: the pi builder ran", "a.md:6: .pi/ and the PI builder", "b.md:1: zz glm-4 here"];
  const ok = JSON.stringify(got) === JSON.stringify(want);
  const none = scan([["c.md", "nothing here"]], ["pi"], []).length === 0;
  // the CLI end to end, on a throwaway repo: staged content, exit codes
  const dir = mkdtempSync(join(tmpdir(), "names-check-"));
  let cli = false;
  try {
    const git = (...a) => execFileSync("git", ["-C", dir, ...a], { stdio: "pipe" });
    git("init", "-q");
    writeFileSync(join(dir, "names.txt"), "pi\n\nglm\n");
    writeFileSync(join(dir, "r.md"), "the pi builder\n");
    git("add", "r.md");
    writeFileSync(join(dir, "r.md"), "clean now\n"); // staged content still has the name
    const run = (...a) => { try { execFileSync(process.execPath, [process.argv[1], ...a], { cwd: dir, stdio: "pipe" }); return 0; } catch (e) { return e.status; } };
    cli = run("--names", "names.txt", "--staged") === 1 && run("--names", "names.txt", "r.md") === 0
      && run("--names", "missing.txt", "--staged") === 2
      && (writeFileSync(join(dir, "rx.txt"), "gpt-?4\n"), run("--names", "rx.txt", "r.md") === 2);
  } finally { rmSync(dir, { recursive: true, force: true }); }
  console.log(`${ok ? "ok" : "FAIL"} scan  ${none ? "ok" : "FAIL"} clean  ${cli ? "ok" : "FAIL"} cli`);
  if (!ok) console.log(JSON.stringify(got, null, 1));
  process.exit(ok && none && cli ? 0 : 1);
}

const argv = process.argv.slice(2);
if (argv[0] === "--self-test") selfTest();
else {
  let namesPath, allowPath, staged = false;
  const paths = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--names") namesPath = argv[++i];
    else if (argv[i] === "--allow") allowPath = argv[++i];
    else if (argv[i] === "--staged") staged = true;
    else paths.push(argv[i]);
  }
  if (!namesPath || (!staged && !paths.length) || (staged && paths.length)) fail("usage: --names <file> [--allow <file>] (--staged | <file>...)");
  let names, allowed = [];
  try { names = lines(readFileSync(namesPath, "utf8")); } catch { fail(`cannot read the names file ${namesPath}: create it (repo profile, "Names kept out of records")`); }
  if (!names.length) fail(`the names file ${namesPath} is empty`);
  const rxLine = names.find((n) => /[|?*[\](){}^$\\]/.test(n));
  if (rxLine) fail(`the names file holds a regex line (${JSON.stringify(rxLine)}): write one plain name per line`);
  if (allowPath) { try { allowed = lines(readFileSync(allowPath, "utf8")); } catch { fail(`cannot read the allowed file ${allowPath}`); } }
  const files = [];
  try {
    if (staged) {
      const list = execFileSync("git", ["diff", "--cached", "--name-only", "--diff-filter=d", "-z"], { encoding: "utf8" }).split("\0").filter(Boolean);
      for (const p of list) files.push([p, execFileSync("git", ["show", `:${p}`], { encoding: "utf8", maxBuffer: 1 << 28 })]);
    } else for (const p of paths) files.push([p, readFileSync(p, "utf8")]);
  } catch (e) { fail(`read failed: ${e.message.split("\n")[0]}`); }
  const hits = scan(files, names, allowed);
  for (const h of hits) console.log(h);
  console.error(`names-check: ${files.length} file(s), ${hits.length} hit(s)`);
  process.exit(hits.length ? 1 : 0);
}
