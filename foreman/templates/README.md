# Job records

The **form** for a job file. Copy one; don't invent a shape.

| Lane | Copy this |
|---|---|
| STANDARD (the default) | `JOB-STANDARD.md` |
| QUICK (owner agrees at "go") | `JOB-QUICK.md`: the same record, lens inspection pre-set to `SKIP (QUICK)` |
| FULL (several services) | `JOB-STANDARD.md`, then the extras in `JOB-FULL.md` |

Work order 1 writes the copy to `foreman/jobs/JOB_YYYY-MM-DD_<slug>.md`: the header filled in (Project, Job, Run, Ticket, SourcePlan, Lane, Inspections, Validation strategy, Budgets, Target repo, Worktree, Branch, Base, Final head, Started, Acceptance ledger), then the body from `## Risk Assessment` on. The foreman keeps it current through the job (`METHOD.md` §7 step 6); `/f-signoff` moves it to `foreman/completed-jobs/YYYY-MM/`.

The phases map to Topping Out artifacts (SCOPING, PLAN and f-plancheck, work orders, gate 2, the two inspections, the acceptance ledger). The header names the source plan as `SourcePlan`; a job close never retires it.
