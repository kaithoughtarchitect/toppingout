// .loose-endsignore: folders and files the loose-ends check skips entirely, e.g. an
// archive of copy-pasted experiment scripts. A skipped file is never offered as a
// copy or a reuse candidate.
//
// One pattern per line, relative to the repo root; `#` starts a comment.
//   old/experiments/                    a folder (and everything in it)
//   scripts/old-*.mjs                    `*` = any characters within one folder
//   **/fixtures/                         `**` = any number of folders
// Case-insensitive.
import { readFileSync } from "node:fs";
import { join } from "node:path";

const cache = new Map();

function toRegex(pattern) {
  let p = pattern.trim().replace(/\\/g, "/").replace(/^\.\//, "").replace(/^\//, "");
  const dir = p.endsWith("/");
  if (dir) p = p.slice(0, -1);
  const body = p.split("**").map((part) => part.replace(/[.+^${}()|[\]]/g, "\\$&").replace(/\*/g, "[^/]*").replace(/\?/g, "[^/]")).join(".*");
  // A folder pattern matches everything under it; a plain one matches itself or, if it is a folder, its contents.
  return new RegExp(`^${body}${dir ? "/" : "(?:$|/)"}`, "i");
}

/** (repo-relative path) => true when .loose-endsignore in `root` skips it. */
export function ignoredBy(root) {
  if (cache.has(root)) return cache.get(root);
  let rules = [];
  try {
    rules = readFileSync(join(root, ".loose-endsignore"), "utf8").split(/\r?\n/)
      .map((l) => l.replace(/#.*$/, "").trim()).filter(Boolean).map(toRegex);
  } catch {}
  const fn = rules.length ? (rel) => rules.some((re) => re.test(String(rel).replace(/\\/g, "/"))) : () => false;
  cache.set(root, fn);
  return fn;
}
