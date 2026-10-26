# f-inspect

Have specialist reviewers check the finished job's changes and report only problems.

Command: `/f-inspect` (old name `/f-lens`)

Stage: Inspect · The end game · step 7 of 11 in the order of works (Inspect)
Source: `skills/f-inspect/SKILL.md`

## On site

Near the end of a job, the first of two reviews: the foreman runs it once the build is finished, before any pull request. Small, low-risk jobs skip it. It reviews only this job's changes, makes no fixes and gives no verdict, just findings. The record goes in templates/LENS-INSPECTION.md.

## Say it

- "run the lens inspection"

## When to use it

When a job's build is finished and its tests pass, before the pull request is opened.

## Not for

The independent inspection (pack-review → xreview → adjudicate), not a review of an open PR (f-greploop).

## It's working if

- It stops and says so when `foreman/jobs/` holds no job file for the slug, instead of reviewing anyway.
- It stops and reports a wrong HEAD or an unexpected dirty file, and never checks out, stashes or resets anything.
- It lists which lenses ran and which were skipped, each with a reason, and `lens-simplify` ran last as report-only.
- Every finding carries severity, confidence, file:line, the scenario, why it matters and a concrete remedy.
- Each lens is asked whether, where a test proves something is absent (no raw amount, no secret), another test pins the exact value shown.
- A lens that halted, errored or returned `BLOCK` is reported as such, not as a clean lens with zero findings.
- The findings are written to `<day folder>/JOB-<N>-LENS-INSPECTION.md`.
- It gave no SHIP or BLOCK verdict, fixed nothing, and made no commit, push or PR.

## How it pins the scope

These are the checks it runs before any lens reads the work, shown exactly as the skill lists them.

```
WT="<worktree>"; BASE="<base sha>"; HEAD_SHA="<final head sha>"
git -C "$WT" rev-parse HEAD                      # must equal $HEAD_SHA: stop if not
git -C "$WT" status --short                      # only the profile's dirty-file allowlist
git -C "$WT" diff --name-status "$BASE..$HEAD_SHA"   # the manifest the lenses review
git -C "$WT" diff "$BASE..$HEAD_SHA" > "<day folder>/lens/<ticket>.diff"
```

## Common questions

### Why is there no PR yet?

This inspection runs after gate 2 and before the PR is prepared. The PR comes only after both inspections, the final re-run and the acceptance ledger.

### Does every job get it?

No. QUICK jobs skip it, and the record says `lens inspection: SKIP (QUICK)`. STANDARD and FULL jobs get it.

### Who fixes what it finds?

Not this skill. The findings go to adjudication, where each is reproduced against the code and accepted, rejected or partly accepted. Accepted findings become the builder's test-first repair work orders.

### Why does each lens start fresh?

Each triggered lens runs as a new subagent with no context from the job, so it reads the work cold. It is briefed with the range, the diff, the ticket's goal and constraints, and the settled decisions it must not relitigate.

### How is it different from the independent inspection?

This is the first of a job's two inspections, run by the foreman in its own session. The independent inspection (`/pack-review`, `/xreview`, `/adjudicate`) comes after, with a reviewer in another session.

### It used to be called something else?

Yes: `/f-lens` still works.

## Connections

- Leads to: f-greploop, pack-review
- Uses: lens-code, lens-comments, lens-errors, lens-instructions, lens-migrations, lens-simplify, lens-tests, lens-types
