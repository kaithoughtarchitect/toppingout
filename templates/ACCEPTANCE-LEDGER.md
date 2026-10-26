# J<N>: acceptance ledger (pre-merge)

**By:** the foreman, <date>. **Final reviewed head:** `<full sha>` on `<branch>` (the head every row below was proven at). **Base:** `<sha>`.

The PR may open when no row is FAIL, UNTESTED or INCONCLUSIVE; a row waiting only on the foreman's own final-head run, or on a Linux check that runs as CI on the PR, is PENDING (`METHOD.md` §8 steps 1 and 6). **The merge waits until every row is PASS.** A requirement dropped from scope, weakened (reworded so less is proven) or substituted needs the owner's recorded decision below (quote it), never a smaller denominator or a quietly reworded row (`RULES.md`, Evidence). The requirement column is copied verbatim from the job file's requirement table, which work order 1 writes from the ticket as the site walk left it (`METHOD.md` §2), so the baseline is fixed before the build starts. `/f-signoff` reads this ledger: every row PASS, no deferrals.

## Requirements and verification points

| ID | Requirement / VP (verbatim) | Result | Achieved mode | Evidence at the final head |
|---|---|---|---|---|
| R1 | | PASS / FAIL / UNTESTED / INCONCLUSIVE / PENDING (the foreman's own final-head run, or CI on the PR; never at merge) | executed test / database proof / probe / code-read / live check / owner walkthrough / API walkthrough (page not exercised) | test name + command + output line, or file:line |
| VP1 | | | | |

**Achieved mode** says how it was actually shown. A proxy is not a pass: "the unit test mocks the peer" does not prove "the live peer accepts it". Say which, and mark a live claim INCONCLUSIVE until it has been observed. **When the page can't be driven** (clicks or keys don't post), the walkthrough may go through the app's own API route, with the server log as evidence: the mode is then "API walkthrough (page not exercised)", and the page itself is owed to the owner in the PR body. **A check that needs a real keystroke or other OS input** is marked owner-only, or done as a synthetic page event labelled as such; it is never left "owed" from job to job.

## The one safety fact

The single whole-system property this ticket must not break (e.g. "a resumed run never uses a seat other than its pinned one"), and how it was proven **by executing shipped code**, not by reading it or by a unit test of one piece. If it could not be executed: **unproven**, and say why.

## Scope decisions by the owner

| Item | Change (drop / weaken / substitute) | Old wording | New wording | Reason | Owner's words (quoted) | Evidence invalidated and re-run | Date |
|---|---|---|---|---|---|---|---|

**Spend:** <the provider-reported USD of each paid call (a live key, a paid review seat), or `estimate`, or $0>
