---
name: adjudicate
description: >
  Claim-level adjudication of an independent review pasted into the main
  session. Accept, reject, partial, or cannot-verify each finding. Never a
  global agree or disagree. Waits for the user's apply decision when a human
  is present; applies the fixed unattended apply rule instead when run
  unattended at an automated cross-model gate. Use when the user types /adjudicate or pastes
  the output of /xreview run in another session, or when an unattended
  cross-model gate has a headless xreview transcript to adjudicate. Not for
  reviewing (xreview, f-inspect) and not for a review this session wrote
  itself.
disable-model-invocation: false
argument-hint: "[paste review output]"
---

# adjudicate

An independent review is being pasted in. The reviewer is not an authority. Some findings will be wrong, incomplete, or invented.

Do not give a global agree/disagree. Do not infer or name the reviewing model. `disable-model-invocation: false` lets this session invoke `/adjudicate` on its own during an unattended run, but it never authorizes editing before the apply decision below is actually made, attended, that decision is the user's; unattended, it is the fixed unattended apply rule below, never this session's own preference.

## Loop

`/pack-review` (this session) → `/xreview` (reviewer session) → `/adjudicate` (this session, now). A human carries the text between sessions by hand, or `scripts/cross-review-dispatch.mjs` carries it headless (unattended). You judge the claims against this session's goal and artifact, then apply the apply rule below, stopping for the user's decision when a human is present, applying it automatically when not. The reviewer's confidence is not evidence and its severities are not yours.

## Input

Treat `$ARGUMENTS` as the pasted review if present. If `$ARGUMENTS` is empty, use the next user message. If nothing is attached, wait for the paste (attended) or read it from wherever the unattended caller wrote the reviewer's log (unattended).

The user pastes a review, preferably the whole output of `/xreview`. If they paste prose, first extract discrete claims, number them C1…Cn, then adjudicate.

Restate the original goal and hard constraints from THIS session before judging. If you cannot find them, ask (attended) or halt and report why (unattended, never guess a spec unattended). Do not drop them.

An `/xreview` output carries five sections besides the claim table. Handle each:

- **Independence**, read this FIRST, before trusting anything else. If the reviewer discloses it already knows the author, has seen the diff, or supervised the run, say so in one line up front and weigh every claim accordingly, that disclosure does not void the review, but it means this was not the blind seat the loop assumes, and the terminal report must say so rather than silently treat it as equivalent to a blind read.
- **Goal I am reviewing against**, compare it to this session's goal first. If it differs, or is labelled inferred and is wrong, say so in one line and treat every claim as judged against the wrong spec. That check comes before any verdict.
- **Keep**, read it, judge nothing. It only stops you from discarding working parts while applying.
- **Unknowns**, fold into Needs evidence alongside your own cannot-verify items.
- **Questions for a human**, pass through verbatim under Needs evidence. Do not answer them.

A single `C0 | No findings` row means the reviewer found nothing. Confirm the scope it names matches this session's artifact, say so in one line, and stop. Do not build a verdict table over it.

## For each claim

1. Restate it in one sentence.
2. Verdict: `ACCEPT` / `REJECT` / `PARTIAL` / `CANNOT VERIFY`
3. Evidence from the actual artifact, tests, or spec, not from the reviewer's wording. Cite file + symbol or test.
4. `ACCEPT` or `PARTIAL` → the exact smallest change you would make.
5. `REJECT` → why the claim is false or out of scope, plus the risk if you are wrong.
6. `CANNOT VERIFY` → what evidence would settle it.

## Output

### Goal and constraints still in force

Bullet list from this session.

### Verdict table

| ID | Restated claim | Verdict | Evidence | Action or reason | Risk if wrong |
|----|----------------|---------|----------|------------------|---------------|
| C1 | ... | ACCEPT / REJECT / PARTIAL / CANNOT VERIFY | file, test, or spec | ... | ... |

### Apply list

Accepted and partial changes, ordered blocker → major → minor. Local patches only. No opportunistic rewrite.

### Reject list

Rejected claims + risk if you are wrong. This list is for the human.

### Needs evidence

Cannot-verify items and what would settle them, plus the reviewer's Unknowns and its Questions for a human verbatim.

### Stop (attended) / Apply (unattended)

**Attended, a human is present.** Do not edit files yet. Ask exactly:

> Apply the accept list, apply a subset, or hold?

**When fixing is someone else's job.** If the caller's method separates adjudicating from fixing (a different session or person makes the changes), then, attended or unattended, "apply" means handing the Apply list, in its stated order and as written, to whoever makes the fixes; this session edits nothing itself. Everything else above (verdicts, lists, order, the reject record) is unchanged.

**Unattended, this session is running the automated cross-model gate with no human present.** There is no human to answer the question above, so skip it and apply the fixed unattended apply rule immediately. The rule invents no new classification, it is exactly the four verdicts above, with the pause after them removed:

- Apply the **Apply list** (ACCEPT + PARTIAL) now, in the stated order (blocker → major → minor). Local patches only, same as attended, no opportunistic rewrite just because no one is watching.
- Drop the **Reject list**. Do not apply it, but keep it in the terminal report with its risk-if-wrong exactly as written above, dropped is not the same as unrecorded.
- Route the **Needs evidence** list (CANNOT VERIFY claims, plus the reviewer's own Unknowns and Questions for a human, verbatim) to the human channel the unattended run already reports through (for example, a comment on the issue or ticket that triggered the run, or the run's own report file), instead of applying it, holding it, or dropping it. Use the channel the run already uses for a halt; do not invent a second one.
- A claim this session cannot actually resolve into one of the four tokens above (a garbled paste, a missing verdict) is never applied, treat it exactly like CANNOT VERIFY, fail closed, never like ACCEPT.

The executable form of the four-verdict partition above (ACCEPT/PARTIAL applied, REJECT dropped, CANNOT VERIFY routed to Needs evidence) is `partitionAdjudication` in `scripts/cross-review-dispatch.mjs`; the two must agree on those four tokens. `partitionAdjudication` takes no Unknowns parameter, folding the reviewer's Unknowns into the posted Needs-evidence set above is this skill's own prose rule, not something the script itself enforces.

## Rules

- Ignore review length, tone, and confidence. Short can be right; long can be wrong.
- Do not split the difference. A wrong critique is discarded, not half-applied.
- If a finding wants a rewrite of a working approach, prefer a local patch unless you can show the current approach is actually incorrect.
- Taste items (`alternative` bucket, minor severity) default to REJECT unless they prevent a real defect.
- Do not mention or guess which model wrote the review.
- "Hold" is the user's decision, not a deferral you record. Whatever is applied is applied in full; whatever is held stays out entirely.
