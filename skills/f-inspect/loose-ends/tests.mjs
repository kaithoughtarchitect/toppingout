// Does a change to a test file make it check less? Plain triggers only: an assertion
// removed (net) or commented out, an expected value changed, a skip / xfail / only added.
// A trigger is a reason to look, not a verdict: the reader judges.

export const TEST_FILE = /(^|\/)(__tests__|tests?|spec)\/|[._-](test|spec)\.[cm]?[jt]sx?$|(^|\/)test_[^/]*\.py$|_test\.py$/;

const ASSERT = /\b(assert\w*|expect\s*\(|check\s*\(|should\b|ok\s*\(|equal\s*\(|strictEqual|deepStrictEqual|deepEqual|notEqual|throws\s*\(|rejects\s*\(|t\.(is|not|true|false|truthy|falsy|like|regex)\b)|\.(to|not)\.?\w*(Be|Equal|Match|Throw|Contain|Have|Resolve|Reject)\w*\s*\(/;
const SKIP = /\b(it|test|describe|context)\.(skip|todo|only|fixme)\b|\bx(it|test|describe)\s*\(|\bf(it|describe)\s*\(|@pytest\.mark\.(skip|skipif|xfail)|\bpytest\.(skip|xfail)\s*\(|@unittest\.skip|\bskip\s*:\s*true\b/;
const COMMENTED = /^\s*(\/\/|#|\/\*|\*)/;
// The text after a comment marker that is a check, not prose about one.
const ASSERT_CODE = /^(await\s+)?(assert\w*(\s*\(|\.\w+\s*\(|\s+[\w(!])|expect\s*\(|check\s*\(|self\.assert\w*\s*\(|t\.\w+\s*\(|[\w.$[\]()]+\.(should|to|not)\b)/;
// An assertion's "shape": the same line with its literals blanked out.
const shape = (l) => l.trim().replace(/(["'`])(?:\\.|(?!\1).)*\1/g, "S").replace(/\b\d+(\.\d+)?\b/g, "N");

const toks = (l) => l.split(/\s+|(\|\||&&|===|!==|==|!=|[()[\]{},;.])/).filter(Boolean);
/**
 * Is `after` the assertion `before` made stricter? True when the only difference is
 * one alternative deleted (`|| x`, `or x`) or one condition added (`&& x`, `and x`).
 */
export function tightens(before, after) {
  const b = toks(before), a = toks(after);
  const edge = (run, ops) => run.length > 1 && (ops.includes(run[0]) || ops.includes(run[run.length - 1]));
  // Align from the front first, then from the back first: `x || y` -> `y` only lines up the second way.
  for (const frontFirst of [true, false]) {
    let p = 0, s = 0;
    const front = () => { while (p < b.length - s && p < a.length - s && b[p] === a[p]) p++; };
    const back = () => { while (s < b.length - p && s < a.length - p && b[b.length - 1 - s] === a[a.length - 1 - s]) s++; };
    if (frontFirst) { front(); back(); } else { back(); front(); }
    const gone = b.slice(p, b.length - s), added = a.slice(p, a.length - s);
    if ((added.length === 0 && edge(gone, ["||", "or"])) || (gone.length === 0 && edge(added, ["&&", "and"]))) return true;
  }
  return false;
}

function multisetMinus(a, b) {
  const m = new Map();
  for (const x of b) m.set(x, (m.get(x) ?? 0) + 1);
  return a.filter((x) => { const n = m.get(x) ?? 0; if (n > 0) { m.set(x, n - 1); return false; } return true; });
}

/**
 * Plain reasons this change might weaken a test ([] = cannot weaken). `committed`, when
 * given, limits removed assertions to those in it; null means nothing can be weakened.
 */
export function weakeningTriggers(before, after, committed) {
  if (committed === null) return [];
  const b = before.split("\n").map((l) => l.trim()).filter(Boolean);
  const a = after.split("\n").map((l) => l.trim()).filter(Boolean);
  const removed = multisetMinus(b, a), added = multisetMinus(a, b);
  const live = (l) => ASSERT.test(l) && !COMMENTED.test(l);
  const reasons = [];
  const atHead = committed === undefined ? null : new Set(committed.split("\n").map((l) => l.trim()));
  let remAssert = removed.filter(live).filter((l) => !atHead || atHead.has(l)), addAssert = added.filter(live);
  // A rewrite that only makes an assertion stricter is not weakening: pair it off.
  for (const r of [...remAssert]) {
    const i = addAssert.findIndex((a) => tightens(r, a));
    if (i >= 0) { remAssert = remAssert.filter((x) => x !== r); addAssert = addAssert.filter((_, j) => j !== i); }
  }
  // An assertion whose shape survives but whose literals changed = new expected value.
  const addShapes = addAssert.map(shape);
  const changedExpect = remAssert.filter((l) => addShapes.includes(shape(l)));
  const dropped = multisetMinus(remAssert.map(shape), addShapes);
  // Only a NET drop removes assertions. Rewritten ones (the same count, a different
  // shape: `startswith` -> `==`, a reworded literal) are reported as rewrites.
  const netDrop = Math.min(dropped.length, Math.max(0, remAssert.length - addAssert.length));
  if (netDrop) reasons.push(`removes ${netDrop} assertion(s)`);
  if (dropped.length > netDrop) reasons.push(`rewrites ${dropped.length - netDrop} assertion(s)`);
  if (changedExpect.length) reasons.push(`changes the expected value in ${changedExpect.length} assertion(s)`);
  // Only a comment that is code: prose that says "assertion" or "should" is not a
  // commented-out check.
  if (added.some((l) => COMMENTED.test(l) && ASSERT_CODE.test(l.replace(COMMENTED, "").trim()))) reasons.push("comments out an assertion");
  const newSkips = multisetMinus(added.filter((l) => SKIP.test(l)), removed.filter((l) => SKIP.test(l)));
  if (newSkips.length) reasons.push("adds skip / xfail / only");
  return reasons;
}

