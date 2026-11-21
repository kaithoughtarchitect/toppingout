// Lightweight, zero-dependency .env loader (fail-open, non-clobbering).
// Never logs or prints secret values, never overrides an already-set env var (even ""),
// and never loads keys under Node's test runner (respects RULES.md money guard).
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

let loaded = false;

export function isNodeTestEnv(
  env: NodeJS.ProcessEnv = process.env,
  execArgv: string[] = process.execArgv,
  argv: string[] = process.argv
): boolean {
  if (env.NODE_TEST_CONTEXT || env.NODE_TEST) return true;
  if (execArgv.includes("--test") || argv.includes("--test")) return true;
  return false;
}

export interface LoadEnvOptions {
  env?: NodeJS.ProcessEnv;
  candidates?: string[];
  force?: boolean;
  respectTestGuard?: boolean;
}

export function loadEnv(opts: LoadEnvOptions = {}): void {
  const env = opts.env ?? process.env;
  const respectTestGuard = opts.respectTestGuard ?? true;
  if (respectTestGuard && (isNodeTestEnv(process.env) || isNodeTestEnv(env))) return;

  if (!opts.force && env === process.env) {
    if (loaded) return;
    loaded = true;
  }

  const here = dirname(fileURLToPath(import.meta.url));
  const candidates = opts.candidates ?? [
    resolve(here, ".env"),
    resolve(here, "..", "..", ".env"),
    resolve(process.cwd(), ".env"),
  ];

  for (const filePath of candidates) {
    let text: string;
    try {
      text = readFileSync(filePath, "utf8");
    } catch {
      continue;
    }
    for (const raw of text.split(/\r?\n/)) {
      const line = raw.trim();
      if (!line || line.startsWith("#")) continue;
      const eq = line.indexOf("=");
      if (eq === -1) continue;
      const key = line.slice(0, eq).trim();
      let val = line.slice(eq + 1).trim();
      if (
        val.length >= 2 &&
        ((val[0] === '"' && val[val.length - 1] === '"') ||
          (val[0] === "'" && val[val.length - 1] === "'"))
      ) {
        val = val.slice(1, -1);
      }
      // Never override a variable that is already present in env, even if set to "" (stripped).
      if (key && !Object.prototype.hasOwnProperty.call(env, key)) {
        env[key] = val;
      }
    }
  }
}

export function gafferEnv(
  suffix: string,
  env: NodeJS.ProcessEnv = process.env
): string | undefined {
  if (Object.prototype.hasOwnProperty.call(env, `GAFFER_${suffix}`)) {
    return env[`GAFFER_${suffix}`];
  }
  return env[`ORCA_VOICE_${suffix}`];
}

loadEnv();
