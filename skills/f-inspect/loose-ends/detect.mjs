// Places that repeat some lines. Two detectors, both seeded with the changed lines,
// both returning EVERY matching region in the tree (not one earlier match each).
//
//   token   — 4-token shingles over TypeScript's scanner; comments and `{ } ;`
//             dropped, so `if (x) { return y; }` and `if (x) return y;` match.
//   literal — rare string literals shared with the seed, plus literals in the
//             declarations of names the seed uses. Catches copies the AI wrote
//             with different code but the same option names and messages.
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { join } from "node:path";
import { isPython, pyAssigns, pyBlocks, pyStrings, pyTokenize } from "./python.mjs";

const K = 4;
export const TOKEN_MIN_COVER = 0.5;
export const LITERAL_MIN_SCORE = 0.4;
const LITERAL_MAX_DF = 25; // a string in more files than this says nothing
const LONG_LITERAL = 20, LONG_LITERAL_MAX_DF = 3;
export const CODE_FILE = /\.(mjs|cjs|js|jsx|ts|tsx|mts|cts|py)$/;
export const SKIP_PATH = /(^|\/)(node_modules|dist|build|coverage|__pycache__|\.venv|venv|site-packages)\/|\.d\.ts$|\.min\./;

/**
 * The `typescript` package parses JS/TS. It is looked for in the reviewed repo, next to
 * this script, then in the global npm folder. null when none has it: the caller then
 * scans Python only and says so (`npm install -g typescript` enables JS/TS).
 */
export function loadTs(root) {
  const tries = [join(root, "package.json"), import.meta.url];
  try { tries.push(join(execFileSync("npm", ["root", "-g"], { encoding: "utf8", shell: process.platform === "win32", stdio: ["ignore", "pipe", "ignore"] }).trim(), "noop.js")); } catch {}
  for (const t of tries) { try { return createRequire(t)("typescript"); } catch {} }
  return null;
}

export function tokenize(ts, text, path = "") {
  if (isPython(path)) return pyTokenize(text);
  const sc = ts.createScanner(ts.ScriptTarget.Latest, true, ts.LanguageVariant.Standard, text);
  const starts = ts.computeLineStarts(text);
  const lineOf = (pos) => { let lo = 0, hi = starts.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (starts[m] <= pos) lo = m; else hi = m - 1; } return lo + 1; };
  const out = [], braces = [];
  for (let k = sc.scan(), n = 0; k !== ts.SyntaxKind.EndOfFileToken && n < 5e6; k = sc.scan(), n++) {
    // The scanner cannot tell `/` from a regex without a parser.
    if (k === ts.SyntaxKind.SlashToken || k === ts.SyntaxKind.SlashEqualsToken) {
      const prev = out[out.length - 1]?.t;
      if (!prev || /^[([{,;:!&|?=+\-*%<>~^]$|^(return|typeof|case|=>|&&|\|\||\?\?|===|!==|==|!=)$/.test(prev)) k = sc.reScanSlashToken();
    }
    // A `}` that closes `${` continues the template literal.
    if (k === ts.SyntaxKind.OpenBraceToken) braces.push("b");
    else if (k === ts.SyntaxKind.TemplateHead) braces.push("t");
    else if (k === ts.SyntaxKind.CloseBraceToken && braces.pop() === "t") {
      k = sc.reScanTemplateToken(false);
      if (k === ts.SyntaxKind.TemplateMiddle) braces.push("t");
    }
    const t = sc.getTokenText();
    if (t === "{" || t === "}" || t === ";") continue;
    out.push({ t, line: lineOf(sc.getTokenStart()) });
  }
  return out;
}

const shingles = (toks) => { const s = []; for (let i = 0; i + K <= toks.length; i++) s.push(toks.slice(i, i + K).map((x) => x.t).join("\u0001")); return s; };

// Uniform shape for both languages: string literals, where each name is defined,
// and which names are used on which line.
function parse(ts, path, text) {
  if (isPython(path)) {
    const decls = pyAssigns(text);
    for (const b of pyBlocks(text)) if (!decls.has(b.name)) decls.set(b.name, { s: b.s, e: b.e });
    const idents = pyTokenize(text).filter((t) => /^[A-Za-z_]\w*$/.test(t.t)).map((t) => ({ name: t.t, line: t.line }));
    return { lits: pyStrings(text), decls, idents };
  }
  const sf = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true, /x$/.test(path) ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const L = (pos) => sf.getLineAndCharacterOfPosition(pos).line + 1;
  const lits = [], decls = new Map(), idents = [];
  (function walk(n) {
    if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) lits.push({ v: n.text, line: L(n.getStart(sf)) });
    if ((ts.isVariableDeclaration(n) || ts.isFunctionDeclaration(n)) && n.name && ts.isIdentifier(n.name) && !decls.has(n.name.text)) decls.set(n.name.text, { s: L(n.getStart(sf)), e: L(n.getEnd()) });
    if (ts.isIdentifier(n)) idents.push({ name: n.text, line: L(n.getStart(sf)) });
    ts.forEachChild(n, walk);
  })(sf);
  return { lits, decls, idents };
}

/** Build once per tree. files: Map<repo-relative path, text>. */
export function buildIndex(ts, files) {
  const tokens = new Map(), parsed = new Map(), df = new Map();
  for (const [p, text] of files) {
    try { tokens.set(p, tokenize(ts, text, p)); } catch { continue; }
    try {
      const r = parse(ts, p, text); parsed.set(p, r);
      for (const v of new Set(r.lits.map((x) => x.v))) df.set(v, (df.get(v) ?? 0) + 1);
    } catch {}
  }
  return { ts, files, tokens, parsed, df, N: parsed.size };
}

function tokenQuery(ix, seedFile, s0, e0) {
  const seed = (ix.tokens.get(seedFile) ?? []).filter((x) => x.line >= s0 && x.line <= e0);
  const S = new Set(shingles(seed));
  const hits = [];
  if (S.size === 0) return { seedTokens: seed.length, hits };
  for (const [path, toks] of ix.tokens) {
    const sh = shingles(toks);
    let cur = null;
    const flush = () => {
      if (!cur) return;
      const cover = cur.set.size / S.size, s = toks[cur.a].line, e = toks[cur.b + K - 1].line;
      if (cover >= TOKEN_MIN_COVER && !(path === seedFile && s <= e0 && e >= s0)) hits.push({ path, s, e, cover: +cover.toFixed(2), via: "token" });
      cur = null;
    };
    for (let i = 0; i < sh.length; i++) {
      if (!S.has(sh[i])) continue;
      if (cur && i - cur.b > K) flush();
      if (!cur) cur = { a: i, b: i, set: new Set() };
      cur.b = i; cur.set.add(sh[i]);
    }
    flush();
  }
  return { seedTokens: seed.length, hits };
}

function literalQuery(ix, seedFile, s0, e0) {
  const { parsed, df, N } = ix;
  const seed = parsed.get(seedFile);
  if (!seed) return [];
  const vals = seed.lits.filter((x) => x.line >= s0 && x.line <= e0).map((x) => x.v);
  const exclude = [{ s: s0, e: e0 }];
  // Names used on the seed lines that are defined in this file -> their literals.
  for (const id of seed.idents) {
    if (id.line < s0 || id.line > e0) continue;
    const d = seed.decls.get(id.name);
    if (!d || d.e - d.s > 40 || (d.s <= e0 && d.e >= s0) || exclude.some((x) => x.s === d.s)) continue;
    vals.push(...seed.lits.filter((x) => x.line >= d.s && x.line <= d.e).map((x) => x.v));
    exclude.push({ s: d.s, e: d.e });
  }
  const w = new Map();
  for (const v of new Set(vals)) { const d = df.get(v) ?? 1; if (v.length >= 2 && d <= LITERAL_MAX_DF) w.set(v, Math.log(N / d)); }
  const total = [...w.values()].reduce((a, b) => a + b, 0);
  // One long string found in almost no other file (a usage line, an error
  // message) is enough on its own: a one-line rule often has nothing else.
  const telling = new Set([...w.keys()].filter((v) => v.length >= LONG_LITERAL && (df.get(v) ?? 1) <= LONG_LITERAL_MAX_DF));
  if ((w.size < 2 && telling.size === 0) || total === 0) return [];
  const hits = [];
  for (const [path, r] of parsed) {
    let cur = null;
    const flush = () => {
      if (!cur) return;
      const score = [...cur.set].reduce((a, v) => a + w.get(v), 0) / total;
      const self = path === seedFile && exclude.some((x) => cur.s <= x.e && cur.e >= x.s);
      const enough = (cur.set.size >= 2 && score >= LITERAL_MIN_SCORE) || [...cur.set].some((v) => telling.has(v));
      if (enough && !self) hits.push({ path, s: cur.s, e: cur.e, cover: +score.toFixed(2), via: "literal" });
      cur = null;
    };
    for (const x of r.lits.filter((x) => w.has(x.v)).sort((a, b) => a.line - b.line)) {
      if (cur && x.line - cur.e > 3) flush();
      if (!cur) cur = { s: x.line, e: x.line, set: new Set() };
      cur.e = x.line; cur.set.add(x.v);
    }
    flush();
  }
  return hits;
}

const overlaps = (a, b) => a.path === b.path && a.s <= b.e + 1 && b.s <= a.e + 1;

/** Every region that repeats the seed lines, both detectors merged. */
export function candidates(ix, seedFile, s0, e0) {
  const { seedTokens, hits } = tokenQuery(ix, seedFile, s0, e0);
  for (const h of literalQuery(ix, seedFile, s0, e0)) {
    const dup = hits.find((x) => overlaps(x, h));
    if (dup) dup.via = "both"; else hits.push(h);
  }
  hits.sort((a, b) => b.cover - a.cover);
  return { seedTokens, hits };
}
