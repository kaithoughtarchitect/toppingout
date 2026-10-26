// Env bootstrap: loads the repo's .env into process.env AT IMPORT.
//
// Used by scripts/speak.ts and scripts/speak-setup.ts (the voice add-on), so their
// keys (OPENROUTER_API_KEY, HUME_API_KEY, SPEAK_*) need not be exported by the shell.
// It must be the FIRST import in any script that reads those keys: ES modules evaluate
// imports in source order, so importing this first makes the values available before
// any later module reads them.
//
// Dependency-free (no dotenv) + fail-open + non-clobbering: a value already present in the
// environment (e.g. set by the shell or a client's `env` block) WINS — this only fills the
// gaps. A missing/unreadable .env is silently fine (the env may be provided another way;
// the consuming script still fails loudly if a key it needs ends up unset).
//
// The .env is the one at the repo root, one level up from this file when it lives in
// <repo>/scripts/. It is resolved relative to THIS module via import.meta.url, not the
// process cwd, so it works regardless of where the script is launched from.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

function loadDotEnv(): void {
  let text: string;
  try {
    const here = dirname(fileURLToPath(import.meta.url));
    text = readFileSync(resolve(here, "..", ".env"), "utf8");
  } catch {
    return; // no .env — fine; env may be supplied by the client config / shell
  }
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    // strip ONE layer of matching surrounding quotes (single or double)
    if (val.length >= 2 && ((val[0] === '"' && val[val.length - 1] === '"') || (val[0] === "'" && val[val.length - 1] === "'"))) {
      val = val.slice(1, -1);
    }
    if (key && process.env[key] === undefined) process.env[key] = val;
  }
}

loadDotEnv();
