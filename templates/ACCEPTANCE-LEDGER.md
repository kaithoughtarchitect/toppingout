# J<N>: acceptance ledger (pre-merge)

**By:** the foreman, <date>. **Final reviewed head:** `<full sha>` on `<branch>` (the head every row below was proven at, or the sha a row names, with the repairs since and their affected-test runs listed under it). **Base:** `<sha>`.

The PR may open when no row is FAIL, UNTESTED, INCONCLUSIVE or blank (a page check `owed: no browser tool` is not blank: it goes in the PR body for the owner); a row waiting only on CI on the PR at the final head (the job's second whole-suite run), on the foreman's own final-head run where CI doesn't run the whole suite, or on a Linux check that runs as CI on the PR, is PENDING (`METHOD.md` §8 steps 1 and 6). **The merge waits until every requirement and VP row PASS, the non-functional rows PASS or `not touched` with a reason, and the behaviour row recorded (it never blocks).** A requirement dropped from scope, weakened (reworded so less is proven) or substituted needs the owner's recorded decision below (quote it), never a smaller denominator or a quietly reworded row (`RULES.md`, Evidence). The requirement column is copied verbatim from the job file's requirement table, which work order 1 writes from the ticket as the site walk left it (`METHOD.md` §2), so the baseline is fixed before the build starts. `/f-signoff` reads this ledger: every requirement and VP row PASS, the non-functional rows PASS or `not touched` with a reason, and the behaviour row recorded (it never blocks); no deferrals.

## Requirements and verification points

| ID | Risk | Requirement / VP (verbatim) | Result | Achieved mode | Evidence at the final head |
|---|---|---|---|---|---|
| R1 | P0 / P1 / P2 / P3 (from the plan) | | PASS / FAIL / UNTESTED / INCONCLUSIVE / PENDING (CI on the PR, or the foreman's own final-head run where CI doesn't run the whole suite; never at merge) | executed test / database proof / probe / code-read / live check / owner walkthrough / API walkthrough (page not exercised) | test name + command + output line, or file:line |
| VP1 | | | | | |

**Risk** comes from the plan (a requirement row takes the highest risk among the VPs that prove it; a plan written before risk levels: P2). It sets the least proof that counts: a **P0** row needs an executed proof **and** a mutation probe that bites on its guard, named by its probe id (a guard that existed before this job gets its probe at the final head; when no input exists that only the guard refuses, the pinned-line record `RULES.md` asks for in that case counts); a **P1** row needs an executed proof (a code read is not a PASS); **P2** as usual; **P3** may pass on a code read. A row whose proof is below its risk level is INCONCLUSIVE.

**Achieved mode** says how it was actually shown. A proxy is not a pass: "the unit test mocks the peer" does not prove "the live peer accepts it". Say which, and mark a live claim INCONCLUSIVE until it has been observed. **When the page can't be driven** (clicks or keys don't post), the walkthrough may go through the app's own API route, with the server log as evidence: the mode is then "API walkthrough (page not exercised)", and the page itself is owed to the owner in the PR body. **A check that needs a real keystroke or other OS input** is marked owner-only, or done as a synthetic page event labelled as such; it is never left "owed" from job to job.

## Non-functional checks

What a job can break without any requirement failing. Every row is filled: either `not touched: <why>` or its evidence at the final head. A blank row halts the PR like an UNTESTED one.

| Check | Result | Evidence or why not touched |
|---|---|---|
| Speed | not touched / PASS / FAIL | e.g. the hot path's timing before and after, the slowest-tests list, a query plan |
| Security | | e.g. the inputs it now accepts and the probe that refuses a bad one; secrets never logged |
| Privacy | | e.g. no personal data newly stored, logged or sent; retention as agreed |
| Cost | | e.g. paid calls added per request, the measured spend |

## Page check (page changes only)

When the job changes something a user sees in a page, the foreman (or the master builder) opens the app at the final head in a browser tool and drives each changed screen the way its requirement describes (`METHOD.md` §10, "The page check"). Unit tests and a code read don't stand in for it. Save the evidence beside this ledger as `JOB-<N>-PAGE-<screen>.png` (or `.txt` for a snapshot), with no login value or personal data showing; a repair after it that touches a checked screen re-takes that row at the new head. **No browser tool loaded:** `owed: no browser tool`, listed for the owner in the PR body, never a PASS; attended, the owner does it before the merge or records that they won't; in an autonomous run it stops the job, as an UNTESTED row does. A job that changes no page writes `not applicable`.

| Screen and what was done | Result | Achieved mode | Evidence |
|---|---|---|---|
| `<page or route>`: <the clicks and values, as the requirement describes> | PASS / FAIL / owed | live check | `JOB-<N>-PAGE-<screen>.png`, the browser tool used, the head sha |

## Behaviour (AI features only)

When the job changes how an AI feature behaves (a prompt, a model, a tool, how an agent is wired), run the repo profile's **measurement / eval harness** on the base and on the final head and record both. No harness in the profile: `not measured: no harness`, listed as owed to the owner (never a halt). A job that changes no AI behaviour writes `not applicable`.

| Harness and command | Base result | Head result | Read |
|---|---|---|---|
| | | | better / same / worse, and on what |

A **worse** read is never a halt by itself: it goes into the PR body and the dev report for the owner, and if a requirement or VP covers that behaviour, that row decides.

## The one safety fact

The single whole-system property this ticket must not break (e.g. "a resumed run never uses a seat other than its pinned one"), and how it was proven **by executing shipped code**, not by reading it or by a unit test of one piece. If it could not be executed: **unproven**, and say why.

## Scope decisions by the owner

| Item | Change (drop / weaken / substitute) | Old wording | New wording | Reason | Owner's words (quoted) | Evidence invalidated and re-run | Date |
|---|---|---|---|---|---|---|---|

**Spend:** <the provider-reported USD of each paid call (a live key, a paid review seat), or `estimate`, or $0>
