#!/usr/bin/env node
/**
 * greptile-wait.mjs — wait for Greptile's review of one PR head, then report the score.
 *
 *   node greptile-wait.mjs --pr <n> --head <sha> [--repo <owner/name>] [--timeout 600] [--interval 60]
 *   node greptile-wait.mjs --self-test
 *
 * Greptile shows a finished review in either of two ways, and both count:
 *   1. a pull-request review by greptile-apps[bot] whose commit is the head, or
 *   2. its summary comment (Greptile EDITS the same comment on a re-review) saying
 *      "Last reviewed commit: <sha>" for the head, with "Confidence Score: N/5".
 *
 * Exit codes:
 *   0  reviewed: prints one JSON line {"done":true,"score":N,"source":...,"url":...}
 *   2  timed out: no review of this head yet (a halt for the owner, never a guessed score)
 *   3  error: a gh failure, an unreadable response, or no score where a review was found.
 *      A failed or empty read is an ERROR, never "nothing yet".
 *   64 bad invocation
 *
 * Read-only: it calls `gh api` GET endpoints and nothing else. Node 18+ and an authenticated `gh`.
 */
import { execFileSync } from "node:child_process";

const BOT = /^greptile-apps(\[bot\])?$/i;
// Greptile's own formats, both seen on real PRs: the score as a hidden marker or as text, and the
// reviewed commit either inside a commit link or written right after the colon.
const SCORE = /greptile_confidence_score:\s*(\d)|Confidence Score:\s*\**\s*(\d)\s*\/\s*5/i;
const LAST = /Last reviewed commit:[^\n]*?\/commit\/([0-9a-f]{7,40})|Last reviewed commit:?\s*(?:\[)?`?([0-9a-f]{7,40})/i;
const first = (m) => (m ? m[1] || m[2] : undefined);

/** Does a short or long sha name the same commit as the head? */
export function sameCommit(a, head) {
  if (!a || !head) return false;
  const x = String(a).toLowerCase(), h = String(head).toLowerCase();
  return x.length >= 7 && (h.startsWith(x) || x.startsWith(h));
}

/**
 * Pure. Given what GitHub returned, is there a Greptile review of `head`, and what is its score?
 * Returns {done:false} | {done:true, score, source, url} | {error}.
 */
export function judge({ reviews, issueComments }, head) {
  if (!Array.isArray(reviews) || !Array.isArray(issueComments)) return { error: "unreadable response: expected two arrays" };
  const bot = (x) => x && x.user && BOT.test(String(x.user.login || ""));
  const summary = issueComments.filter(bot).filter((c) => SCORE.test(c.body || "") || LAST.test(c.body || ""));
  // the summary comment is edited in place: the latest one names the commit it last reviewed
  const latest = summary.sort((a, b) => String(a.updated_at || "").localeCompare(String(b.updated_at || ""))).at(-1);
  const viaSummary = latest && sameCommit(first(LAST.exec(latest.body || "")), head);
  const review = reviews.filter(bot).filter((r) => sameCommit(r.commit_id, head)).at(-1);
  if (!viaSummary && !review) return { done: false };
  // The score must come from something that names THIS head: the summary only when it points here,
  // else the review itself. Never borrow the summary's score from a later commit.
  const scored = SCORE.exec((viaSummary ? latest.body : review.body) || "");
  if (!scored) return { error: "a review of this head was found but no 'Confidence Score: N/5' could be read" };
  return { done: true, score: Number(first(scored)), source: viaSummary ? "summary-comment" : "review", url: (viaSummary ? latest : review).html_url || null };
}

function gh(path) {
  const out = execFileSync("gh", ["api", "--paginate", "--slurp", path], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 60000 });
  const pages = JSON.parse(out);
  if (!Array.isArray(pages)) throw new Error(`unexpected response shape for ${path}`);
  return pages.flat();
}

function repoName(given) {
  if (given) return given;
  return execFileSync("gh", ["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
}

function arg(name) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : undefined;
}

function selfTest() {
  const H = "529bc48e1f0a9d3c2b7a6e5d4c3b2a1908f7e6d5";
  const bot = { login: "greptile-apps[bot]" };
  const cases = [
    ["a review of the head is detected", { reviews: [{ user: bot, commit_id: H, body: "Confidence Score: 4/5", html_url: "r" }], issueComments: [] }, (r) => r.done && r.score === 4 && r.source === "review"],
    ["an edited summary naming the head is detected", { reviews: [], issueComments: [{ user: bot, updated_at: "2", body: "Confidence Score: 5/5\nReviews (2) · Last reviewed commit: [529bc48](x)", html_url: "c" }] }, (r) => r.done && r.score === 5 && r.source === "summary-comment"],
    ["the real format (hidden score marker, commit inside a link) is detected", { reviews: [], issueComments: [{ user: bot, updated_at: "3",
      body: "<h2>Greptile Summary</h2>\n<!-- greptile_confidence_score:5 -->\n<sub>Reviews (2) · Last reviewed commit: [\"TICKET-01 keep the chat busy\"](https://github.com/o/r/commit/" + H + ")</sub>" }] },
      (r) => r.done && r.score === 5 && r.source === "summary-comment"],
    ["a summary still on the old commit is not done", { reviews: [], issueComments: [{ user: bot, updated_at: "1", body: "Confidence Score: 3/5 · Last reviewed commit: 1111111" }] }, (r) => r.done === false],
    ["a review of an older commit is not done", { reviews: [{ user: bot, commit_id: "1111111aaaa", body: "Confidence Score: 5/5" }], issueComments: [] }, (r) => r.done === false],
    ["a human's comment never counts", { reviews: [], issueComments: [{ user: { login: "someone" }, body: "Confidence Score: 5/5 Last reviewed commit: 529bc48" }] }, (r) => r.done === false],
    ["an older head's score is never borrowed from a later summary", { reviews: [{ user: bot, commit_id: H, body: "Looks fine" }], issueComments: [{ user: bot, updated_at: "9", body: "Confidence Score: 5/5 · Last reviewed commit: 2222222" }] }, (r) => !!r.error],
    ["nothing yet is not done", { reviews: [], issueComments: [] }, (r) => r.done === false],
    ["a found review with no score is an error, not a pass", { reviews: [{ user: bot, commit_id: H, body: "Looks fine" }], issueComments: [] }, (r) => !!r.error],
    ["an unreadable response is an error, not nothing yet", { reviews: null, issueComments: [] }, (r) => !!r.error],
    ["the latest edit of the summary wins", { reviews: [], issueComments: [
      { user: bot, updated_at: "1", body: "Confidence Score: 4/5 · Last reviewed commit: 1111111" },
      { user: bot, updated_at: "2", body: "Confidence Score: 5/5 · Last reviewed commit: 529bc48" }] }, (r) => r.done && r.score === 5],
  ];
  let failed = 0;
  for (const [name, input, ok] of cases) {
    const r = judge(input, H);
    const pass = ok(r);
    if (!pass) failed++;
    console.log(`${pass ? "ok  " : "FAIL"} ${name}  ${JSON.stringify(r)}`);
  }
  console.log(failed ? `GREPTILE_WAIT_SELFTEST_FAIL ${failed}/${cases.length}` : `GREPTILE_WAIT_SELFTEST_OK ${cases.length}/${cases.length}`);
  process.exit(failed ? 1 : 0);
}

async function main() {
  if (process.argv.includes("--self-test")) return selfTest();
  const pr = arg("pr"), head = arg("head");
  const timeout = Number(arg("timeout") || 600), interval = Number(arg("interval") || 60);
  if (!/^\d+$/.test(pr || "") || !/^[0-9a-f]{7,40}$/i.test(head || "") || !(timeout > 0) || !(interval > 0)) {
    console.error("usage: greptile-wait.mjs --pr <n> --head <sha> [--repo <owner/name>] [--timeout 600] [--interval 60]");
    process.exit(64);
  }
  const deadline = Date.now() + timeout * 1000;
  let repo;
  try { repo = repoName(arg("repo")); } catch (e) { console.error(`GREPTILE_WAIT_ERR repo: ${e.message}`); process.exit(3); }
  for (;;) {
    let verdict;
    try {
      verdict = judge({ reviews: gh(`repos/${repo}/pulls/${pr}/reviews`), issueComments: gh(`repos/${repo}/issues/${pr}/comments`) }, head);
    } catch (e) {
      console.error(`GREPTILE_WAIT_ERR read: ${String(e.stderr || e.message).trim().slice(0, 300)}`);
      process.exit(3);
    }
    if (verdict.error) { console.error(`GREPTILE_WAIT_ERR ${verdict.error}`); process.exit(3); }
    if (verdict.done) { console.log(JSON.stringify(verdict)); process.exit(0); }
    if (Date.now() + interval * 1000 > deadline) { console.error(`GREPTILE_WAIT_TIMEOUT no review of ${head.slice(0, 7)} after ${timeout}s`); process.exit(2); }
    await new Promise((r) => setTimeout(r, interval * 1000));
  }
}

main();
