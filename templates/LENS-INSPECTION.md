# J<N>: the lens inspection (`/f-inspect`): the record

**Who runs it:** the foreman, **in its own session**, after gate 2. It is not a builder work order: the builder never reviews its own branch. **QUICK lane:** skipped; record `lens inspection: SKIP (QUICK)` in the job header and the PR's review record.

**Range:** `<base sha>..<final head sha>` in `<worktree>`. **Pinned head:** `<full sha>` (checked with `git -C <worktree> rev-parse HEAD` before the agents start).

## 1 · Run it

Invoke `/f-inspect <base sha>..<final head sha> <worktree>`. The skill pins the head, picks the lenses the diff triggers (each a fresh subagent), briefs them the same way (goal, constraints verbatim, settled decisions not to relitigate, findings only) and never fixes, gives a verdict, commits or opens a PR. No PR exists yet; none is needed.

**Lenses run:** <list> · **skipped:** <list, each with why> · **halted:** <none | which, and why>

## 2 · Findings (as the lenses returned them)

| Id | Lens | File:line | Scenario | Why it matters |
|---|---|---|---|---|
| S1 | | | | |

## 3 · Adjudicate

Every finding is **reproduced against the code first**, then ACCEPT / REJECT / PARTIAL / CANNOT VERIFY, in `templates/ADJUDICATION.md` (`Round: the lens inspection`). "Ship with follow-ups" becomes fixed now, or rejected with a reason.

The lenses ran in the foreman's session, so this round is **not independent of the foreman**: it never replaces the independent inspection, and an issue the foreman rejects here can still be raised there.

## 4 · Repairs

Only accepted findings go to the builder, as **test-first repair work orders** (`templates/WORK-ORDER.txt`, one outcome each). The foreman reviews each fix like any work order (`templates/WORK-ORDER-REVIEW.md`). The foreman never makes the fix itself outside the converged case (`METHOD.md` §9).

**Next:** the independent inspection (`METHOD.md` §8 step 4) over the final range, including these repairs.
