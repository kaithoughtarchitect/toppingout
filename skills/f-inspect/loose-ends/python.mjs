// Python support for the finders: the same three things TypeScript gives the
// JS/TS path, done for Python with plain code.
//   pyTokenize  — tokens + line numbers (comments and whitespace dropped; a string,
//                 including triple-quoted and prefixed ones, is one token)
//   pyStrings   — string literal contents + line (for the rare-string detector)
//   pyBlocks    — def / async def / class blocks by indentation (+ decorators)
//   pyAssigns   — NAME = ... assignments (for "literals in what the seed uses")
export const isPython = (path) => /\.pyi?$/.test(String(path));

const STRING = /^(?:[rRbBuUfF]{0,2})("""|'''|"|')/;
const OPS = ["**=", "//=", ">>=", "<<=", "->", "**", "//", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", ":=", "<<", ">>"];

/** Scan a string literal starting at i (after any prefix). Returns end index. */
function stringEnd(text, i, q) {
  let j = i + q.length;
  while (j < text.length) {
    if (text[j] === "\\") { j += 2; continue; }
    if (text.startsWith(q, j)) return j + q.length;
    if (q.length === 1 && text[j] === "\n") return j; // unterminated single-line string
    j++;
  }
  return j;
}

export function pyTokenize(text) {
  const out = [];
  let i = 0, line = 1;
  while (i < text.length) {
    const c = text[i];
    if (c === "\n") { line++; i++; continue; }
    if (c === " " || c === "\t" || c === "\r" || c === "\\" || c === "\f") { i++; continue; }
    if (c === "#") { while (i < text.length && text[i] !== "\n") i++; continue; }
    const sm = text.slice(i, i + 5).match(STRING);
    if (sm) {
      const start = i, q = sm[1], afterPrefix = i + sm[0].length - q.length;
      const end = stringEnd(text, afterPrefix, q);
      const t = text.slice(start, end);
      out.push({ t, line }); line += (t.match(/\n/g) ?? []).length; i = end; continue;
    }
    const w = text.slice(i).match(/^[A-Za-z_][\w]*|^\d[\w.]*|^\.\d+/);
    if (w) { out.push({ t: w[0], line }); i += w[0].length; continue; }
    const op = OPS.find((o) => text.startsWith(o, i));
    if (op) { out.push({ t: op, line }); i += op.length; continue; }
    out.push({ t: c, line }); i++;
  }
  return out;
}

/** String literal contents with their line (prefix and quotes stripped). */
export function pyStrings(text) {
  return pyTokenize(text).filter((t) => STRING.test(t.t)).map((t) => {
    const m = t.t.match(/^(?:[rRbBuUfF]{0,2})("""|'''|"|')([\s\S]*?)\1$/);
    return { v: m ? m[2] : t.t, line: t.line };
  });
}

const indentOf = (l) => l.match(/^[ \t]*/)[0].replace(/\t/g, "    ").length;

/** def / async def / class blocks: [{ name, kind, s, e, code, indent }]. */
export function pyBlocks(text) {
  const lines = text.split("\n"), out = [];
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^([ \t]*)(?:async\s+)?(def|class)\s+([A-Za-z_]\w*)/);
    if (!m) continue;
    const ind = indentOf(lines[i]);
    let s = i; while (s > 0 && /^\s*@/.test(lines[s - 1]) && indentOf(lines[s - 1]) === ind) s--;
    // The header may span lines (long signatures): skip to the line ending in ':'.
    let h = i; while (h < lines.length - 1 && !/:\s*(#.*)?$/.test(lines[h])) h++;
    let e = h;
    for (let j = h + 1; j < lines.length; j++) {
      if (!lines[j].trim()) continue;
      if (indentOf(lines[j]) <= ind) break;
      e = j;
    }
    out.push({ name: m[3], kind: m[2] === "class" ? "class" : "function", s: s + 1, e: e + 1, indent: ind, code: lines.slice(s, e + 1).join("\n") });
  }
  return out;
}

/** NAME = value assignments (value may span bracketed lines): Map name -> { s, e }. */
export function pyAssigns(text) {
  const lines = text.split("\n"), out = new Map();
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^[ \t]*([A-Za-z_]\w*)\s*(?::[^=]+)?=(?!=)/);
    if (!m) continue;
    let depth = 0, e = i;
    for (let j = i; j < lines.length; j++) {
      for (const ch of lines[j].replace(/#.*$/, "")) { if ("([{".includes(ch)) depth++; else if (")]}".includes(ch)) depth--; }
      e = j;
      if (depth <= 0) break;
    }
    if (!out.has(m[1])) out.set(m[1], { s: i + 1, e: e + 1 });
  }
  return out;
}

