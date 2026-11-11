#!/usr/bin/env node
// Self-test for loose-ends.mjs: a throwaway git repo with one change of each kind the
// check reports, plus the noise it must not report. Python files only, so it also
// passes where the `typescript` package is not installed.
//   node skills/f-inspect/loose-ends/loose-ends.test.mjs
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT = join(dirname(fileURLToPath(import.meta.url)), "loose-ends.mjs");
const dir = mkdtempSync(join(tmpdir(), "loose-ends-test-"));
const git = (...a) => execFileSync("git", ["-C", dir, ...a], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
const put = (p, text) => { mkdirSync(dirname(join(dir, p)), { recursive: true }); writeFileSync(join(dir, p), text); };

const GUARD = (limit) => `def check_upload(name, size):
    if size > ${limit}:
        raise ValueError("upload too large: the limit is ${limit} bytes per file")
    if not name.endswith((".png", ".jpg", ".gif")):
        raise ValueError("only png, jpg and gif uploads are accepted here")
    return True
`;
const PARSE = `def read_settings(path):
    values = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values
`;
const TEST = (body) => `from app.web import check_upload


def test_limit():
${body}
`;

let failed = 0;
const ok = (cond, what) => { console.log(`${cond ? "ok  " : "FAIL"} ${what}`); if (!cond) failed++; };
try {
  git("init", "-q");
  git("config", "user.email", "test@example.com");
  git("config", "user.name", "test");
  put("app/web.py", GUARD(5000000));
  put("app/api.py", GUARD(5000000)); // the mirror that should change too
  put("app/config.py", PARSE);
  put("tests/test_web.py", TEST("    assert check_upload(\"a.png\", 10)\n    assert check_upload(\"b.jpg\", 20)"));
  put("vendor/lib/config_copy.py", PARSE.replace("read_settings", "load_settings_vendored"));
  put("old/moved.py", PARSE.replace("read_settings", "parse_env_file"));
  git("add", "-A"); git("commit", "-qm", "base");
  const base = git("rev-parse", "HEAD").trim();

  put("app/web.py", GUARD(2000000)); // the rule changes in one place only
  put("app/tools.py", "import os\n\n\n" + PARSE.replace("read_settings", "load_config_file")); // a renamed copy
  put("tests/test_web.py", TEST("    assert check_upload(\"a.png\", 10)"));
  mkdirSync(join(dir, "new"), { recursive: true });
  git("mv", "old/moved.py", "new/moved.py"); // a move: its function must not count as existing
  git("add", "-A"); git("commit", "-qm", "change");

  const out = JSON.parse(execFileSync("node", [SCRIPT, `${base}..HEAD`, "--repo", dir, "--json"], { encoding: "utf8" }));
  const copies = out.groups.flatMap((g) => g.hits.map((h) => h.path));
  const fns = out.reuse.flatMap((r) => r.candidates.map((c) => `${r.name}->${c.name}@${c.path}`));
  ok(copies.includes("app/api.py"), "the untouched mirror of a changed rule is listed");
  ok(fns.some((f) => f.startsWith("load_config_file->read_settings@app/config.py")), "a renamed copy of an existing function is listed");
  ok(!fns.some((f) => f.includes("@vendor/")), "vendored code is not offered as an original");
  ok(!fns.some((f) => f.includes("@old/moved.py")), "a moved file's old copy is not offered as an original");
  ok(out.tests.some((t) => t.path === "tests/test_web.py" && t.reasons.some((r) => r.startsWith("removes"))), "a test that lost an assertion is listed");
  const excl = JSON.parse(execFileSync("node", [SCRIPT, `${base}..HEAD`, "--repo", dir, "--json", "--exclude", "^app/config\\.py$"], { encoding: "utf8" }));
  ok(!excl.reuse.some((r) => r.candidates.some((c) => c.path === "app/config.py")), "--exclude removes a path from the candidates");
} finally {
  rmSync(dir, { recursive: true, force: true });
}
if (failed) { console.log(`${failed} failed`); process.exit(1); }
console.log("all passed");
