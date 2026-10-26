# Development Report <Month day, year> (<Weekday>): <the day's lesson, as a phrase>


> **Placement.** One report per work-session date. <If a job spans two dates, say where its records live.>

**The day in one line.** <What existed before, what the ticket added, the proof, the PR and merge sha. Whether there was a migration.>

**The lesson the day is named for.** <The one failure or surprise worth carrying forward, told plainly, including the foreman's own mistakes.>

---

## Work log

| When | What |
|---|---|
| | Site walk: <score, re-answers, disagreements with the shift handover> |
| | Scoping: <forks settled, notable measurements> |
| | Work order <m> (the builder): <what, commits, captures> |
| | Gate <1/2>: <findings count, blocking ones> |
| | Lens inspection (f-inspect, or SKIP (QUICK)) / independent inspection (xreview): <findings and claims, dispositions> |
| | PR #<n> opened, checked in the browser, Greptile rounds <n, each score> or none, description checked, merged, proved by the tree check (`METHOD.md` §10 step 3) |

## At a glance

| | |
|---|---|
| Merge | `<sha>`, parents `<a>` (+ `<b>`), in `<remote>/<main>`; `M^{tree}` `<tree>` = expected tree `<tree>` (reviewed head's, or the tested merge-preview's) |
| Commits / files / lines | <n> / <n> / +<a> −<r> |
| Tests added | <n>, plus <DB proofs> |
| Autonomous run notes | survey answers it gave itself, any in-scope option taken over a starred pick, usage-limit pauses (when and how long), or "not an autonomous run" |
| Extra paid spend | $<n> (a live key, a paid review seat; the command or usage reading it came from), or $0. Never the builder's own bill |
| Probes | <n>/<n> bite |
| Findings | gate 1 <n>, work order reviews <n>, gate 2 <n>, lens inspection <n or SKIP> (accepted <n>), independent inspection <n> (accepted <n>), Greptile <rounds, findings> (accepted <n>), fix review <n> |

## The foreman's scorecard (grade yourself as honestly as the builder)

| Question | This job |
|---|---|
| Work orders that needed a `<m>b` correction because of *your* error | |
| Real bugs that got past your reviews to the independent inspection | |
| Did you break "existing tests before commit"? | |
| Did you claim anything you hadn't checked on disk or on the remote? | |
| Work orders for the ticket (against the estimate at planning) | |

## Learnings
Numbered, each: what happened → the rule it becomes → where the rule now lives (work order template, RULES.md, shift handover gotchas).

## Owed
Every decision or act still waiting for the owner's word.
