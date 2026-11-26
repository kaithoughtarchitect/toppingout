# J<N>: gate 2 review (the whole build) by the foreman

**Branch:** `<branch>`, <n> commits above `<base>`, not pushed; worktree `<status>`.

| Commit | Content | Reviewed |
|---|---|---|
| `<sha>` | <what it does> | `<JOB-<N>-WORK-ORDER-<m>-REVIEW.md>` (<findings, or "clean">) |

**Final captures t<k> (head `<sha>`):** every gate with its result, compared with t0; every difference **attributed** (which new module caused it) or named as a characterised intermittent. Before t-final the whole-suite gate is a SKIP (t0's baseline is main's CI at the branch point); the whole suite runs once, at the final head (`METHOD.md` §8 step 6), where a difference outside every work order's affected set is labelled and attributed (or found by bisecting the commits). Database roles restored after each arm.

**Base-vs-head run 1:** the derived set (script + COUNT), base and head results, **red-at-head-only = <n>**. No whole-suite run here: the builder's runs once at the final head and CI's on the PR (`METHOD.md` §8 step 6). The foreman checks the builder's run on disk instead of repeating it (where the repo profile says "CI runs the whole suite: no", it still runs its own).
- the builder's run: <result; if it stopped, what it stopped on>;
- characterisation by the foreman (if any red): identical to base? isolated N/N on head and base? passed in every earlier capture? **Never retried to green**;
- **the foreman's check on disk, at gate 2** (the builder's base-vs-head work order): the report's head sha = `git -C <wt> rev-parse HEAD`; an `.exit` file for every run; `ran_ok` passes on each; the saved base's key recomputed and equal; red-at-head-only recounted = <n>; tests re-run because doubted: <none, or which and the result>.
- **and at the final head** (`t-final`, recorded in the job file's Phase 7 and the ledger): the capture's `HEAD:` line = the final head; the worktree clean; the `WORKERS` line = the profile's count for this machine; every red test in the whole run labelled with its evidence; the same base-vs-head checks as above.

**Base-vs-head run 2:** <result, or "empty": 0 modules failed collection, with the grep>.

**P0 coverage:** every P0 VP and the probe that bites on its guard (id, BITES), or the gap; the non-functional rows (speed, security, privacy, cost) touched so far.

**Coverage caveat:** code the gates do not run, and where its evidence comes from instead.

**The one safety fact:** <the whole-system property this ticket must not break>, proven by executing shipped code: <command + output>, or **unproven** because <why>.

**Switch rule across the build:** <never triggered | the trigger>. **Unreviewed repairs:** <none | list>.

**Next:** the lens inspection, run here (`/f-inspect` with fresh lens agents → findings adjudicated here → repair work orders; QUICK: `SKIP (QUICK)`) → the independent inspection (/pack-review here → /xreview in a fresh session of another family → /adjudicate here) → review of the fixes → final re-run → acceptance ledger → PR. Merge is the owner's word.
