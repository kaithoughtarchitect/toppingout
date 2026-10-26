# J<N>: <the lens inspection (f-inspect) | the independent inspection (xreview) | Greptile round <n> (f-greploop, on the open PR)>: adjudication

**Round:** <who reviewed what: the range `base..head`, the reviewer's independence (a separate session with no prior contact / fresh lens agents in the foreman's session)>. **Status:** <the lens inspection: not independent of the foreman | Greptile: an outside reader of the PR, reads code only, runs nothing | the independent inspection: independent, reviewer's Independence section says <...>>. For the independent inspection, `/adjudicate` produces this.
**Adjudicated by:** the foreman, claim by claim. **Every claim reproduced before judgement.** For a "missing test" or "unpinned guard" claim, first name the input that **only this line** refuses: if the same reset or check repeats elsewhere unconditionally, no test can pin this one alone, so the claim is rejected with that evidence (a probe would stay GREEN and cost a stop).

| ID | Claim | Reproduction (command and its output, or the new failing test) | Verdict |
|---|---|---|---|
| C1 | <the claim, in one sentence> | <at `<sha>` -> exact output> | **ACCEPT, fixed as the reviewer specified** / **ACCEPT, fixed in this job (work order <m>)** / **PARTIAL: <which part>** / **REJECT: <reason, with evidence>** / **ROUTED to <board id>: outside the ticket (act 8), not a security or concurrency defect in this diff; thread replied** (Greptile rounds only) |

"Ship with follow-ups" verdicts are rewritten: every accepted item is fixed in this job; there are no follow-ups. A ROUTED finding (Greptile rounds only, `skills/f-greploop` step 5) is not a follow-up: its fix lies outside this ticket's files and is recorded on the board.

**The fixes:** <for each accepted claim: the commit, the regression test, the probe added>.

**Reviewer acknowledgment** (security or concurrency repairs, and converged-case fixes, `METHOD.md` §9): the changed-since-review diff `<reviewed sha>..<final sha>` sent back to the same reviewer; its answer: <ACK at `<final sha>` | objections> | not needed: <why>.
**Proved in both states:** the regression test fails at `<before>` and passes at `<after>`; the probe BITES.
**Existing tests run BEFORE the commit:** <which suites, results, FAILED/ERROR identical to the last capture>.
**Review status of each repair:** <reviewer-specified, implemented as specified, proved in both states | reviewed in <file>>.
**The reviewer's "keep" list and unknowns:** <noted; anything the reviewer did not run, and who ran it instead>.
