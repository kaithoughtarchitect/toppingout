# J<N>: gate 2 review (the whole build) by the foreman

**Branch:** `<branch>`, <n> commits above `<base>`, not pushed; worktree `<status>`.

| Commit | Content | Reviewed |
|---|---|---|
| `<sha>` | <what it does> | `<JOB-<N>-WORK-ORDER-<m>-REVIEW.md>` (<findings, or "clean">) |

**Final captures t<k> (head `<sha>`):** every gate with its result, compared with t0; every difference **attributed** (which new module caused it) or named as a characterised intermittent. Between t0 and t-final the whole-suite gate is a SKIP: the whole-suite evidence here is the builder's widened base-vs-head run; a difference outside every work order's affected set is attributed at t-final (or by bisecting the commits). Database roles restored after each arm.

**Base-vs-head run 1:** the derived set (script + COUNT), base and head results, **red-at-head-only = <n>**. The builder's widened comparison (its first run): head <f> failed / <p> passed, base <f> / <p>. The foreman's own run here is run 1; its widened run is at the final head (`METHOD.md` §8 step 6).
- the builder's run: <result; if it stopped, what it stopped on>;
- characterisation by the foreman (if any red): identical to base? isolated N/N on head and base? passed in every earlier capture? **Never retried to green**;
- **the foreman's own run: red-at-head-only = <n>.**

**Base-vs-head run 2:** <result, or "empty": 0 modules failed collection, with the grep>.

**P0 coverage:** every P0 VP and the probe that bites on its guard (id, BITES), or the gap; the non-functional rows (speed, security, privacy, cost) touched so far.

**Coverage caveat:** code the gates do not run, and where its evidence comes from instead.

**The one safety fact:** <the whole-system property this ticket must not break>, proven by executing shipped code: <command + output>, or **unproven** because <why>.

**Switch rule across the build:** <never triggered | the trigger>. **Unreviewed repairs:** <none | list>.

**Next:** the lens inspection, run here (`/f-inspect` with fresh lens agents → findings adjudicated here → repair work orders; QUICK: `SKIP (QUICK)`) → the independent inspection (/pack-review here → /xreview in a fresh session of another family → /adjudicate here) → review of the fixes → final re-run → acceptance ledger → PR. Merge is the owner's word.
