#!/usr/bin/env node
// The Topping Out installer: copies the package into a repo, or upgrades an existing install.
// One Node script instead of the old bash block, so it runs the same on Windows, macOS and Linux.
//
//   node install.mjs --repo <repo> [--pkg <package>] [--dry-run]      install: copy only what's missing, never overwrite
//   node install.mjs --repo <repo> [--pkg <package>] --upgrade        upgrade plan (writes nothing)
//   node install.mjs --repo <repo> [--pkg <package>] --upgrade --apply
//   node install.mjs --self-test
//   add --addon deep-agents to install with the Deep Agents add-on (addons/deep-agents/README.md), and --starter
//   for its agent skeleton in a new project
//
// --pkg defaults to the package this script sits in (skills/f-setup/install.mjs); an installed copy needs --pkg.
// Install: every package file the repo doesn't have yet is copied (mapping in dest()); an existing file may carry
//   the repo's adaptations, so it is never replaced. The Logbook's cards, index and links are never touched.
//   Writes foreman/INSTALL-RECEIPT.txt and adds scratch/ to .gitignore if git doesn't ignore it yet.
// Upgrade: needs the package as a git checkout and the receipt's revision. Per file: missing -> add; unchanged since
//   the receipt -> replace; differs from both the old and the new package (adapted) -> kept, listed for a hand merge;
//   removed from the package -> deleted if unadapted, else listed. Refuses while a job is open (foreman/jobs/JOB_*.md
//   or foreman/ENDGAME-PENDING.md). With --apply it writes, then rewrites the receipt's revision line.
// A git package must be clean: only its tracked files are copied, so the receipt's revision is exactly what was copied.
// Add-ons: recorded in the receipt's "addons:" line, so an upgrade includes them; the starter skeleton is copied once
//   and never upgraded (it becomes product code).
// Exit: 0 done (adapted files are reported, still exit 0); 1 refused because a job is open or an end game is owed;
//   2 usage error, a package checkout with uncommitted changes, or a read error.

import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, statSync, unlinkSync, appendFileSync, mkdtempSync, rmSync, copyFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join, dirname, resolve, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const fail = (msg) => { console.error(`f-setup: ${msg}`); process.exit(2); };
const SCRIPTS = new Set(["scripts/cross-review-dispatch.mjs", "scripts/speak.ts", "scripts/speak-setup.ts", "scripts/bootstrap-env.ts"]);
const SKIP = /(^|\/)(\.git|__pycache__|scratch|node_modules)(\/|$)|\.(pyc|tmp|part)$|(^|\/)(\.DS_Store|Thumbs\.db|[a-z-]*-pick\.json)$/;
const LOGBOOK_DATA = /^foreman\/logbook\/(logbook_index\.md|logbook_links\.md|entries\/(?!.*-TEMPLATE\.md$)|archived\/|sessions\/)/; // card templates stay installable
const DIRS = ["foreman/jobs", "foreman/completed-jobs", "foreman/ideas", "foreman/projects", "foreman/handovers", "foreman/blueprints/ready", "foreman/blueprints/deferred"];

export const ADDONS = new Set(["deep-agents"]);
const STARTER_IGNORES = [".venv/", ".env", "data/", "*.db", ".langgraph_api/", "__pycache__/", "*.pyc", ".pytest_cache/"];

// package path -> repo path, or null when the file is not installed (html pages, the wiki, the site, generators).
// Add-ons install only when asked: their files map into the repo, the starter skeleton only with starter.
export function dest(p, { addons = new Set(), starter = false } = {}) {
  const a = p.match(/^addons\/([^/]+)\/(.*)$/);
  if (a) {
    if (a[1] !== "deep-agents" || !addons.has(a[1])) return null;
    const r = a[2];
    if (r.startsWith("skill/deep/")) return ".claude/skills/deep/" + r.slice("skill/deep/".length);
    if (r.startsWith("deepagents-ref/")) return r;
    if (r === "mcp.json") return ".mcp.json";
    if (r.startsWith("starter/")) return starter ? r.slice("starter/".length) : null;
    return null; // the add-on's own README
  }
  if (["AGENTS.md", "CONTRIBUTING.md", "ROADMAP.md"].includes(p)) return null; // the package's own repo pages, never the project's
  if (p.startsWith("skills/") || p.startsWith("agents/")) return ".claude/" + p;
  if (SCRIPTS.has(p)) return p;
  if (p.startsWith("foreman/templates/") || p.startsWith("foreman/blueprints/") || p.startsWith("foreman/logbook/")) return p;
  if ((!p.includes("/") && p.endsWith(".md")) || /^(templates|snippets|examples)\//.test(p)) return "foreman/method/" + p;
  return null;
}

// the package's files: the tracked files of a clean git checkout, or every file of a plain folder (a download)
function packageFiles(pkg) {
  if (!revision(pkg)) return walk(pkg);
  if (git(pkg, "status", "--porcelain", "--untracked-files=no").toString().trim())
    fail(`the package at ${pkg} has uncommitted changes: commit or stash them first, so the receipt's revision matches what is copied`);
  return git(pkg, "ls-files", "-z").toString().split("\0").filter((p) => p && !SKIP.test(p));
}

function walk(root, base = root, out = []) {
  for (const name of readdirSync(root)) {
    const full = join(root, name), rel = relative(base, full).split(sep).join("/");
    if (SKIP.test(rel)) continue;
    if (statSync(full).isDirectory()) walk(full, base, out); else out.push(rel);
  }
  return out;
}

const norm = (b) => Buffer.from(b.toString("binary").replace(/\r\n/g, "\n"), "binary");
const same = (a, b) => norm(a).equals(norm(b));
const git = (cwd, ...a) => execFileSync("git", ["-C", cwd, ...a], { stdio: ["ignore", "pipe", "pipe"], maxBuffer: 1 << 28 });
const put = (file, data) => { mkdirSync(dirname(file), { recursive: true }); writeFileSync(file, data); };

function revision(pkg) {
  try { return git(pkg, "rev-parse", "HEAD").toString().trim(); } catch { return null; }
}
function origin(pkg) {
  try { return git(pkg, "remote", "get-url", "origin").toString().trim(); } catch { return null; }
}

export function install(pkg, repo, { dryRun = false, log = console.log, addons = [], starter = false } = {}) {
  const logbookExists = existsSync(join(repo, "foreman/logbook"));
  const opts = { addons: new Set(addons), starter };
  const receipt = join(repo, "foreman/INSTALL-RECEIPT.txt");
  if (addons.length && existsSync(receipt)) {
    // an add-on joins an existing install only at the package revision the receipt names, or its files would look
    // adapted at the next upgrade
    const r = readFileSync(receipt, "utf8").match(/^revision: ([0-9a-f]{7,40})\s*$/m), rev = revision(pkg);
    if (rev && r && r[1] !== rev) fail(`this install is at ${r[1].slice(0, 7)} and the package at ${rev.slice(0, 7)}: upgrade first (--upgrade --apply), then add the add-on`);
  }
  const added = [], skeleton = new Set(), kept = new Set();
  for (const p of packageFiles(pkg).sort()) {
    const d = dest(p, opts);
    if (!d) continue;
    if (logbookExists && LOGBOOK_DATA.test(p)) continue; // an existing Logbook keeps its own cards, index and links
    if (existsSync(join(repo, d))) {
      kept.add(d.match(/^\.claude\/(skills|agents)\/[^/]+/)?.[0] || dirname(d));
      if (d === ".mcp.json" && !dryRun) log("kept .mcp.json (the repo has one): add its docs-langchain entry by hand, from the package's addons/deep-agents/mcp.json");
      continue;
    }
    added.push(d);
    if (p.startsWith("addons/deep-agents/starter/")) skeleton.add(d);
    if (!dryRun) { mkdirSync(dirname(join(repo, d)), { recursive: true }); copyFileSync(join(pkg, p), join(repo, d)); }
  }
  for (const d of added) log(`${dryRun ? "would install" : "installed"} ${d}`);
  if (dryRun) {
    for (const k of [...kept].sort()) log(`kept ${k} (already here, never overwritten)`);
    log(`f-setup: ${added.length} file(s) would be installed; nothing written`);
    return added;
  }
  for (const d of DIRS) mkdirSync(join(repo, d), { recursive: true });
  const rev = revision(pkg), url = origin(pkg);
  if (!existsSync(receipt) || added.length) {
    const head = existsSync(receipt) ? "" : [`package: ${pkg}${url ? ` (${url})` : ""}`, `revision: ${rev || "no git: " + new Date(statSync(join(pkg, "METHOD.md")).mtime).toISOString().slice(0, 10)}`, `installed: ${new Date().toISOString().slice(0, 10)}`, ""].join("\n") + "\n";
    // skeleton files are "starter" lines: product code, never part of a removal
    appendFileSync(receipt, head + added.map((d) => `${skeleton.has(d) ? "starter" : "installed"} ${d}\n`).join(""));
  }
  if (addons.length) {
    const cur = readFileSync(receipt, "utf8");
    const all = [...new Set([...receiptAddons(cur), ...addons])].sort().join(", ");
    writeFileSync(receipt, /^addons: .*$/m.test(cur) ? cur.replace(/^addons: .*$/m, `addons: ${all}`)
      : /^installed: .*$/m.test(cur) ? cur.replace(/^(installed: .*)$/m, `$1\naddons: ${all}`)
      : cur + `${cur.endsWith("\n") ? "" : "\n"}addons: ${all}\n`);
    if (skeleton.size) appendFileSync(receipt, `starter: deep-agents skeleton copied ${new Date().toISOString().slice(0, 10)} (product code from here on: upgrades never touch it)\n`);
  }
  ignoreScratch(repo, log);
  if (starter) ignoreLines(repo, STARTER_IGNORES, "the agent skeleton's local files", log);
  log(`f-setup: ${added.length} file(s) installed`);
  return added;
}

export function receiptAddons(text) {
  const m = text.match(/^addons: (.*)$/m);
  return m ? m[1].split(",").map((s) => s.trim()).filter(Boolean) : [];
}

function ignoreLines(repo, lines, why, log) {
  const gi = join(repo, ".gitignore");
  const cur = existsSync(gi) ? readFileSync(gi, "utf8") : "";
  const have = new Set(cur.split(/\r?\n/).map((s) => s.trim()));
  const missing = lines.filter((l) => !have.has(l));
  if (!missing.length) return;
  appendFileSync(gi, `${cur && !cur.endsWith("\n") ? "\n" : ""}\n# ${why}\n${missing.join("\n")}\n`);
  log(`added ${missing.join(" ")} to .gitignore`);
}

function ignoreScratch(repo, log) {
  let ignored = false;
  try { git(repo, "check-ignore", "-q", "scratch/x"); ignored = true; } catch {}
  if (ignored) return;
  const gi = join(repo, ".gitignore");
  const cur = existsSync(gi) ? readFileSync(gi, "utf8") : "";
  appendFileSync(gi, `${cur && !cur.endsWith("\n") ? "\n" : ""}\n# Topping Out working files (plan checks, councils, the names files)\nscratch/\n`);
  log("added scratch/ to .gitignore");
}

export function openJob(repo) {
  if (existsSync(join(repo, "foreman/ENDGAME-PENDING.md"))) return "foreman/ENDGAME-PENDING.md exists (an end game is still owed)";
  const jobs = join(repo, "foreman/jobs");
  const open = existsSync(jobs) ? readdirSync(jobs).filter((f) => /^JOB_.*\.md$/.test(f)) : [];
  return open.length ? `a job is open (foreman/jobs/${open[0]})` : null;
}

export function upgradePlan(pkg, repo) {
  const receipt = join(repo, "foreman/INSTALL-RECEIPT.txt");
  if (!existsSync(receipt)) fail("no foreman/INSTALL-RECEIPT.txt: this repo has no install to upgrade (run without --upgrade)");
  const m = readFileSync(receipt, "utf8").match(/^revision: ([0-9a-f]{7,40})\s*$/m);
  if (!m) fail("the receipt has no git revision line, so there is no old package to diff against: upgrade by hand (SETUP.md §1)");
  const old = m[1];
  const opts = { addons: new Set(receiptAddons(readFileSync(receipt, "utf8"))), starter: false }; // the skeleton is product code: never upgraded
  let oldFiles;
  try { oldFiles = new Set(git(pkg, "ls-tree", "-r", "--name-only", old).toString().split("\n").filter(Boolean)); }
  catch { fail(`the package checkout doesn't have revision ${old} (fetch it, or upgrade by hand)`); }
  const oldBlob = (p) => git(pkg, "show", `${old}:${p}`);
  const plan = { add: [], replace: [], adapted: [], remove: [], removeAdapted: [], same: 0 };
  const now = packageFiles(pkg).filter((p) => dest(p, opts) && !LOGBOOK_DATA.test(p)).sort();
  for (const p of now) {
    const d = dest(p, opts), t = join(repo, d);
    if (!existsSync(t)) { plan.add.push([d, p]); continue; }
    const cur = readFileSync(t), neu = readFileSync(join(pkg, p));
    if (same(cur, neu)) { plan.same++; continue; }
    if (oldFiles.has(p) && same(oldBlob(p), neu)) { plan.same++; continue; } // the package didn't change it: the repo's version stands
    if (oldFiles.has(p) && same(cur, oldBlob(p))) plan.replace.push([d, p]); else plan.adapted.push([d, p]);
  }
  const nowSet = new Set(now);
  for (const p of [...oldFiles].sort()) {
    const d = dest(p, opts);
    if (!d || nowSet.has(p) || LOGBOOK_DATA.test(p) || !existsSync(join(repo, d))) continue;
    (same(readFileSync(join(repo, d)), oldBlob(p)) ? plan.remove : plan.removeAdapted).push(d);
  }
  return { old, plan };
}

export function upgrade(pkg, repo, { apply = false, log = console.log } = {}) {
  const busy = openJob(repo);
  if (busy) { log(`f-setup: REFUSED, ${busy}. Upgrade at a clean point: no job open, no end game owed.`); return 1; }
  const { old, plan } = upgradePlan(pkg, repo);
  const show = (k, label, list) => { log(`== ${label}: ${list.length}`); for (const x of list) log(`   ${Array.isArray(x) ? x[0] : x}`); };
  show("add", "add (new in the package)", plan.add);
  show("replace", "replace (unchanged here since the receipt)", plan.replace);
  show("adapted", "adapted here: kept, merge by hand (diff it against the package)", plan.adapted);
  show("remove", "remove (gone from the package, unadapted here)", plan.remove);
  show("removeAdapted", "gone from the package but adapted here: kept, decide by hand", plan.removeAdapted);
  log(`== unchanged: ${plan.same}`);
  const rev = revision(pkg);
  if (!apply) { log(`f-setup: upgrade plan ${old.slice(0, 7)} -> ${(rev || "?").slice(0, 7)}; nothing written (add --apply)`); return 0; }
  for (const [d, p] of [...plan.add, ...plan.replace]) put(join(repo, d), readFileSync(join(pkg, p)));
  for (const d of plan.remove) unlinkSync(join(repo, d));
  for (const d of DIRS) mkdirSync(join(repo, d), { recursive: true });
  const receipt = join(repo, "foreman/INSTALL-RECEIPT.txt");
  writeFileSync(receipt, readFileSync(receipt, "utf8").replace(/^revision: .*$/m, `revision: ${rev}`) + plan.add.map(([d]) => `installed ${d}\n`).join("") + `upgraded ${new Date().toISOString().slice(0, 10)}: ${old.slice(0, 7)} -> ${rev.slice(0, 7)}, ${plan.add.length} added, ${plan.replace.length} replaced, ${plan.remove.length} removed, ${plan.adapted.length + plan.removeAdapted.length} left for a hand merge\n`);
  log(`f-setup: upgraded to ${rev.slice(0, 7)}`);
  return 0;
}

function selfTest() {
  const results = [];
  const check = (name, ok) => results.push(`${ok ? "ok" : "FAIL"} ${name}`);
  const tmp = mkdtempSync(join(tmpdir(), "f-setup-"));
  const quiet = () => {};
  try {
    const pkg = join(tmp, "pkg"), repo = join(tmp, "repo");
    const files = {
      "METHOD.md": "method v1\n", "RULES.md": "rules v1\n", "templates/WORK-ORDER.txt": "wo v1\n",
      "skills/f-a/SKILL.md": "a v1\n", "skills/f-b/SKILL.md": "b v1\n", "agents/x.md": "x v1\n",
      "scripts/speak.ts": "speak\n", "scripts/build_site.py": "not installed\n", "docs/index.html": "not installed\n", "AGENTS.md": "not installed\n", "CONTRIBUTING.md": "not installed\n", "ROADMAP.md": "not installed\n",
      "foreman/templates/JOB-QUICK.md": "job v1\n", "foreman/logbook/logbook_index.md": "pkg index\n",
      "foreman/logbook/ARCHIVE-SYSTEM.md": "archive v1\n", "skills/f-a/__pycache__/c.pyc": "junk",
      "foreman/logbook/entries/insights/INSIGHT-TEMPLATE.md": "card template v1\n", "foreman/logbook/entries/insights/INSIGHT_a.md": "a card\n",
      "addons/deep-agents/README.md": "addon readme\n", "addons/deep-agents/skill/deep/SKILL.md": "deep v1\n",
      "addons/deep-agents/deepagents-ref/AGENTS.md": "ref v1\n", "addons/deep-agents/mcp.json": "{}\n",
      "addons/deep-agents/starter/src/agent/agent.py": "agent v1\n",
    };
    for (const [p, c] of Object.entries(files)) put(join(pkg, p), c);
    git(tmp, "init", "-q", pkg);
    git(pkg, "add", "-A"); git(pkg, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=", "commit", "-q", "-m", "v1");
    const v1 = revision(pkg);
    mkdirSync(repo); git(tmp, "init", "-q", repo);
    put(join(repo, ".claude/skills/f-b/SKILL.md"), "b adapted\n"); // an existing adapted skill

    const first = install(pkg, repo, { log: quiet });
    check("install copies what's missing", first.includes("foreman/method/METHOD.md") && first.includes(".claude/skills/f-a/SKILL.md") && first.includes("scripts/speak.ts") && first.includes("foreman/logbook/logbook_index.md"));
    check("install skips the site, generators and caches", !first.some((d) => /build_site|docs\/|pycache/.test(d)));
    check("install skips the package's own repo pages", ["AGENTS.md", "CONTRIBUTING.md", "ROADMAP.md"].every((n) => !first.includes(n) && !first.includes("foreman/method/" + n)));
    check("install never overwrites", readFileSync(join(repo, ".claude/skills/f-b/SKILL.md"), "utf8") === "b adapted\n");
    check("install writes the receipt and ignores scratch", readFileSync(join(repo, "foreman/INSTALL-RECEIPT.txt"), "utf8").includes(`revision: ${v1}`) && readFileSync(join(repo, ".gitignore"), "utf8").includes("scratch/"));
    check("a second install adds nothing", install(pkg, repo, { log: quiet }).length === 0 && readFileSync(join(repo, ".gitignore"), "utf8").match(/scratch\//g).length === 1);
    check("add-ons aren't installed unless asked", !first.some((d) => /deep|\.mcp\.json|agent\.py|addon/.test(d)));
    const withAddon = install(pkg, repo, { log: quiet, addons: ["deep-agents"] });
    check("--addon deep-agents installs the skill, the reference and .mcp.json, not the skeleton",
      withAddon.includes(".claude/skills/deep/SKILL.md") && withAddon.includes("deepagents-ref/AGENTS.md") && withAddon.includes(".mcp.json")
      && !withAddon.some((d) => /agent\.py|README/.test(d)) && /^addons: deep-agents$/m.test(readFileSync(join(repo, "foreman/INSTALL-RECEIPT.txt"), "utf8")));
    const withStarter = install(pkg, repo, { log: quiet, addons: ["deep-agents"], starter: true });
    check("--starter copies the skeleton once and ignores its local files", withStarter.length === 1 && withStarter[0] === "src/agent/agent.py" && /^starter src\/agent\/agent\.py$/m.test(readFileSync(join(repo, "foreman/INSTALL-RECEIPT.txt"), "utf8"))
      && readFileSync(join(repo, ".gitignore"), "utf8").includes(".venv/") && (readFileSync(join(repo, "foreman/INSTALL-RECEIPT.txt"), "utf8").match(/^addons: /gm) || []).length === 1);

    // v2 of the package: a changed file, an adapted file, a removed file, a new file, a changed logbook index
    put(join(repo, "foreman/method/RULES.md"), "rules adapted\n");
    put(join(repo, "foreman/logbook/logbook_index.md"), "repo index\n");
    put(join(pkg, "METHOD.md"), "method v2\n"); put(join(pkg, "RULES.md"), "rules v2\n");
    put(join(pkg, "skills/f-c/SKILL.md"), "c v2\n"); unlinkSync(join(pkg, "agents/x.md"));
    put(join(pkg, "foreman/logbook/logbook_index.md"), "pkg index v2\n");
    put(join(pkg, "foreman/logbook/entries/insights/INSIGHT-TEMPLATE.md"), "card template v2\n");
    put(join(pkg, "addons/deep-agents/deepagents-ref/AGENTS.md"), "ref v2\n");
    put(join(pkg, "addons/deep-agents/starter/src/agent/agent.py"), "agent v2\n");
    git(pkg, "add", "-A"); git(pkg, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=", "commit", "-q", "-m", "v2");
    const { plan } = upgradePlan(pkg, repo);
    const names = (l) => l.map((x) => (Array.isArray(x) ? x[0] : x));
    check("upgrade plan sorts every case", names(plan.replace).includes("foreman/method/METHOD.md") && names(plan.adapted).includes("foreman/method/RULES.md")
      && names(plan.add).includes(".claude/skills/f-c/SKILL.md") && plan.remove.includes(".claude/agents/x.md") && !names(plan.replace).concat(names(plan.adapted)).some((d) => d.includes("logbook_index")));
    check("an installed add-on upgrades, its skeleton never does", names(plan.replace).includes("deepagents-ref/AGENTS.md")
      && !names(plan.replace).concat(names(plan.add), names(plan.adapted)).some((d) => d.includes("agent.py")));
    check("card templates upgrade, cards don't", names(plan.replace).includes("foreman/logbook/entries/insights/INSIGHT-TEMPLATE.md") && !names(plan.add).concat(names(plan.replace)).some((d) => d.includes("INSIGHT_a")));
    // a package with uncommitted changes is refused; an untracked package file is never installed
    const cli = (...a) => { try { execFileSync(process.execPath, [fileURLToPath(import.meta.url), ...a], { stdio: "pipe" }); return 0; } catch (e) { return e.status; } };
    put(join(pkg, "METHOD.md"), "method dirty\n");
    check("a dirty package is refused", cli("--repo", repo, "--pkg", pkg, "--dry-run") === 2);
    git(pkg, "checkout", "--", "METHOD.md");
    check("an add-on is refused on an install older than the package", cli("--repo", repo, "--pkg", pkg, "--addon", "deep-agents") === 2);
    put(join(pkg, "skills/f-new/SKILL.md"), "untracked\n");
    check("untracked package files are not installed", !install(pkg, repo, { dryRun: true, log: quiet }).some((d) => d.includes("f-new")));
    rmSync(join(pkg, "skills/f-new"), { recursive: true });
    put(join(repo, "foreman/jobs/JOB_2026-01-01_x.md"), "open\n");
    check("upgrade refuses while a job is open", upgrade(pkg, repo, { apply: true, log: quiet }) === 1 && readFileSync(join(repo, "foreman/method/METHOD.md"), "utf8") === "method v1\n");
    unlinkSync(join(repo, "foreman/jobs/JOB_2026-01-01_x.md"));
    const applied = upgrade(pkg, repo, { apply: true, log: quiet });
    const read = (p) => readFileSync(join(repo, p), "utf8").replace(/\r\n/g, "\n"); // a checkout may write CRLF
    check("upgrade applies", applied === 0 && read("foreman/method/METHOD.md") === "method v2\n" && existsSync(join(repo, ".claude/skills/f-c/SKILL.md")) && !existsSync(join(repo, ".claude/agents/x.md")));
    check("upgrade keeps adaptations and the Logbook index", read("foreman/method/RULES.md") === "rules adapted\n" && read("foreman/logbook/logbook_index.md") === "repo index\n");
    check("upgrade rewrites the receipt", read("foreman/INSTALL-RECEIPT.txt").includes(`revision: ${revision(pkg)}`));
  } catch (e) { results.push(`FAIL exception: ${e.message.split("\n")[0]}`); }
  finally { rmSync(tmp, { recursive: true, force: true }); }
  console.log(results.join("\n"));
  process.exit(results.every((r) => r.startsWith("ok")) ? 0 : 1);
}

const argv = process.argv.slice(2);
if (argv[0] === "--self-test") selfTest();
else {
  let repo, pkg, dryRun = false, up = false, apply = false, starter = false;
  const addons = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--repo") repo = argv[++i];
    else if (argv[i] === "--pkg") pkg = argv[++i];
    else if (argv[i] === "--dry-run") dryRun = true;
    else if (argv[i] === "--upgrade") up = true;
    else if (argv[i] === "--apply") apply = true;
    else if (argv[i] === "--addon") { const a = argv[++i]; if (!ADDONS.has(a)) fail(`unknown add-on ${a}; known: ${[...ADDONS].join(", ")}`); addons.push(a); }
    else if (argv[i] === "--starter") starter = true;
    else fail(`unknown argument ${argv[i]}`);
  }
  if (!repo) fail("usage: --repo <repo> [--pkg <package>] [--dry-run] [--addon deep-agents [--starter]] | --upgrade [--apply] | --self-test");
  if (!pkg) pkg = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
  pkg = resolve(pkg); repo = resolve(repo);
  if (!existsSync(join(pkg, "METHOD.md")) || !existsSync(join(pkg, "skills"))) fail(`${pkg} is not the Topping Out package (no METHOD.md and skills/): pass --pkg`);
  if (!existsSync(repo)) fail(`no such repo folder: ${repo}`);
  if (pkg === repo) fail("--repo is the package itself");
  if (apply && !up) fail("--apply goes with --upgrade");
  if (starter && !addons.includes("deep-agents")) fail("--starter goes with --addon deep-agents");
  if (up && (addons.length || starter)) fail("an upgrade takes its add-ons from the receipt; add one with a plain install (--addon), then upgrade");
  process.exit(up ? upgrade(pkg, repo, { apply }) : (install(pkg, repo, { dryRun, addons, starter }), 0));
}
