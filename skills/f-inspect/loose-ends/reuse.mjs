// New functions that may repeat an existing one. Two local finders, no network:
//   vocabulary   BM25 over each function's words (name parts, identifiers, string
//                words). Survives a rewrite with different code.
//   renamed copy name-blind token shingles (identifiers -> ID). Catches a copy that
//                was only renamed.
// The scores do not separate real duplicates from new code: the reader judges.
import { tokenize } from "./detect.mjs";
import { isPython, pyBlocks } from "./python.mjs";

const K = 5;
const KEYWORDS = new Set("if else for while do return const let var function async await new typeof instanceof in of switch case break continue throw try catch finally class extends null undefined true false this default import export from yield delete void def elif lambda pass raise with as is not and or None True False self global nonlocal assert del except".split(" "));
const IDENT = /^[A-Za-z_$][\w$]*$/;
const STOP = new Set("const let var function return if else for while new typeof instanceof null undefined true false this async await throw error string number boolean unknown void type interface export import from readonly value values length".split(" "));
const MIN_LINES = 4, MAX_LINES = 80;

/** Named functions of MIN..MAX lines in one file: { name, s, e, code }. */
export function functionsIn(ts, path, text) {
  if (isPython(path)) {
    return pyBlocks(text).filter((b) => b.kind === "function" && b.e - b.s + 1 >= MIN_LINES && b.e - b.s + 1 <= MAX_LINES)
      .map(({ name, s, e, code }) => ({ name, s, e, code }));
  }
  let sf; try { sf = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true, /x$/.test(path) ? ts.ScriptKind.TSX : ts.ScriptKind.TS); } catch { return []; }
  const L = (pos) => sf.getLineAndCharacterOfPosition(pos).line + 1;
  const out = [];
  (function walk(n) {
    let name = null, node = n;
    if ((ts.isFunctionDeclaration(n) || ts.isMethodDeclaration(n)) && n.name) name = n.name.getText(sf);
    else if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer && (ts.isArrowFunction(n.initializer) || ts.isFunctionExpression(n.initializer))) name = n.name.text;
    if (name) {
      const s = L(node.getStart(sf)), e = L(node.getEnd());
      if (e - s + 1 >= MIN_LINES && e - s + 1 <= MAX_LINES) out.push({ name, s, e, code: node.getText(sf) });
    }
    ts.forEachChild(n, walk);
  })(sf);
  return out;
}

const escRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
/**
 * Does this file (after the change) use the existing function `name`: import it, or
 * call it without defining its own copy? Then it is already reused.
 */
export function usesExisting(name, fileText) {
  if (!name || !fileText) return false;
  const n = escRe(name);
  const imported = new RegExp(
    "import\\s*\\{[^}]*\\b" + n + "\\b[^}]*\\}\\s*from|import\\s+" + n + "\\s+from|from\\s+[\\w.]+\\s+import\\s+[^\\n]*\\b" + n + "\\b|\\{[^}]*\\b" + n + "\\b[^}]*\\}\\s*=\\s*require",
  ).test(fileText);
  if (imported) return true;
  const definesOwn = new RegExp("(?:^|\\n)\\s*(?:export\\s+)?(?:async\\s+)?(?:function\\s*\\*?\\s*" + n + "\\s*\\(|(?:const|let|var)\\s+" + n + "\\s*=|def\\s+" + n + "\\s*\\()").test(fileText);
  return !definesOwn && new RegExp("(?<![\\w$.])" + n + "\\s*\\(").test(fileText);
}

/** Functions in the whole file after an edit whose names the whole file before did not have. */
export function addedFunctions(ts, path, fileBefore, fileAfter) {
  const had = new Set(functionsIn(ts, path, fileBefore).map((f) => f.name));
  return functionsIn(ts, path, fileAfter).filter((f) => !had.has(f.name));
}

const words = (code) => [...code.matchAll(/[A-Za-z][A-Za-z0-9]*/g)]
  .flatMap((m) => m[0].replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2").split(/\s+/))
  .map((w) => w.toLowerCase()).filter((w) => w.length > 2 && !STOP.has(w));
const normToks = (ts, text, path = "") => tokenize(ts, text, path).map((t) => IDENT.test(t.t) && !KEYWORDS.has(t.t) ? "ID" : t.t);
const shingles = (toks) => { const s = new Set(); for (let i = 0; i + K <= toks.length; i++) s.add(toks.slice(i, i + K).join("\u0001")); return s; };

/** Function-level index over the repo (optionally skipping paths, e.g. tests). */
export function buildFunctionIndex(ts, files, { skip = null } = {}) {
  const fns = [];
  for (const [p, text] of files) {
    if (skip && skip.test(p)) continue;
    for (const f of functionsIn(ts, p, text)) fns.push({ path: p, ...f });
  }
  return indexFromFns(ts, fns);
}

/**
 * Same index, but the per-file function lists are cached on disk and only files
 * whose size or mtime changed are re-parsed. First run ~4 s; later runs ~1 s.
 */
function indexFromFns(ts, fns) {
  const tf = fns.map((f) => { const m = new Map(); for (const w of words(f.code)) m.set(w, (m.get(w) ?? 0) + 1); return m; });
  const lens = tf.map((m) => [...m.values()].reduce((a, b) => a + b, 0));
  const avg = lens.reduce((a, b) => a + b, 0) / Math.max(1, lens.length);
  const df = new Map(); for (const m of tf) for (const w of m.keys()) df.set(w, (df.get(w) ?? 0) + 1);
  return { ts, fns, tf, lens, avg, df, sh: new Map() };
}

/** Top candidates for one new function: BM25 top `bm` plus name-blind token hits. */
export function reuseCandidates(ix, code, { bm = 5, exclude = null, path = "" } = {}) {
  const { ts, fns, tf, lens, avg, df } = ix;
  const skip = (f) => exclude && f.path === exclude.path && f.s <= exclude.e && f.e >= exclude.s;
  const qw = [...new Set(words(code))];
  const scored = [];
  fns.forEach((f, i) => {
    if (skip(f)) return;
    let sc = 0;
    for (const w of qw) {
      const n = tf[i].get(w); if (!n) continue;
      const idf = Math.log(1 + (fns.length - df.get(w) + 0.5) / (df.get(w) + 0.5));
      sc += idf * (n * 2.2) / (n + 1.2 * (0.25 + 0.75 * lens[i] / avg));
    }
    if (sc > 0) scored.push({ f, sc });
  });
  const out = scored.sort((a, b) => b.sc - a.sc).slice(0, bm).map(({ f, sc }) => ({ ...f, via: "vocabulary", score: +sc.toFixed(1) }));
  // Renamed copies: same token shape once names are blanked.
  let S; try { S = shingles(normToks(ts, code, path)); } catch { S = new Set(); }
  if (S.size >= 8) {
    fns.forEach((f, i) => {
      if (skip(f) || out.some((o) => o.path === f.path && o.s === f.s)) return;
      if (!ix.sh.has(i)) { try { ix.sh.set(i, shingles(normToks(ts, f.code, f.path))); } catch { ix.sh.set(i, new Set()); } }
      const T = ix.sh.get(i); let hit = 0; for (const x of S) if (T.has(x)) hit++;
      if (hit / S.size >= 0.6) out.push({ ...f, via: "renamed copy", score: +(hit / S.size).toFixed(2) });
    });
  }
  return out;
}

