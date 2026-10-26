---
name: f-inspect
description: >
  The foreman's lens inspection: review a finished job's commit range (base to
  final head, in its worktree) through fresh specialist lens agents and return
  evidence-checked findings only. Use when the owner or METHOD §8 says "run the
  lens inspection", /f-inspect, or after gate 2 on a STANDARD or FULL job. No PR
  exists yet and none is needed: this runs before the PR is prepared. Never
  fixes, never gives a verdict, never commits or pushes. Not the independent
  inspection (pack-review → xreview → adjudicate), not a review of an open PR
  (f-greploop). Also answers to its old name, /f-lens.
argument-hint: "<base sha>..<final head sha> [worktree]"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Task"]
---

# Topping Out: Lens inspection

The first of a job's two inspections (`METHOD.md` §8 step 3). The foreman runs it **in its own session**, after gate 2, over the job's finished work. **There is no PR yet**: the PR is prepared only after both inspections, the final re-run and the acceptance ledger. The builder never runs this and never reviews its own branch. **QUICK jobs skip it** (the record says `lens inspection: SKIP (QUICK)`).

Topping Out's rules are built in: the scope is always the job's range, the mode is always findings-only.

## 1 · Pin the scope

**First, the job file:** `ls foreman/jobs/JOB_*_<slug>.md` must list exactly one file. None means this isn't a job yet (`RULES.md` rule 15): **stop** and say so; the job starts with work order 1, which writes it. A late job file needs the owner's word and states its gaps.

The scope is the job's commit range in its worktree, from the job record's header:

```bash
WT="<worktree>"; BASE="<base sha>"; HEAD_SHA="<final head sha>"
git -C "$WT" rev-parse HEAD                      # must equal $HEAD_SHA: stop if not
git -C "$WT" status --short                      # only the profile's dirty-file allowlist
git -C "$WT" diff --name-status "$BASE..$HEAD_SHA"   # the manifest the lenses review
git -C "$WT" diff "$BASE..$HEAD_SHA" > "<day folder>/lens/<ticket>.diff"
```

A wrong HEAD or an unexpected dirty file: **stop** and report it; don't review a moving target. Never check out, stash or reset anything.

## 2 · Pick the lenses

Each triggered lens runs as a **fresh subagent** with no context from this job. Record which ran and which were skipped, with the reason.

| Lens | Runs when |
|---|---|
| `lens-code` | always |
| `lens-tests` | tests changed, or changed behaviour lacks a test |
| `lens-errors` | error handling, fallbacks, catches or partial-failure paths changed |
| `lens-types` | types, schemas or invariants changed |
| `lens-comments` | durable comments or documentation prose changed |
| `lens-instructions` | skills, agents, prompts or templates changed |
| `lens-migrations` | the diff touches the repo profile's **database change paths** |
| `lens-simplify` | last, and always with the words **report-only** (its no-write branch) |

## 3 · Brief every lens the same way

- the range `<base>..<final head>`, the worktree path and the diff file;
- the ticket's goal and its constraints, verbatim;
- the settled decisions (`D-…`) marked **not to relitigate**;
- one standing question: **where a test proves something is absent (no raw amount, no secret), is there also a test that pins the exact value shown?** Absence tests pass while the shown value is wrong;
- **findings only**: no edits, no fixes, no verdict, no commit, no push, no PR;
- **no test suites, builds or servers**: a lens reads the code and the diff; a finding that needs a run says so, and the foreman runs it on its own schedule (suites run serially, one at a time).

Lenses run sequentially by default. A lens never dispatches another lens and never touches git history.

## 4 · Merge the findings

Every finding carries severity, confidence, file:line, the scenario, why it matters and the concrete remedy. The foreman:

- de-duplicates and drops any finding it disproves against the code at the pinned head, noting the evidence;
- reports a lens that halted, errored or returned `BLOCK` **as such**, never as a clean lens with zero findings;
- keeps each lens's own severity words (no verdict mapping: this skill has no verdict).

Write them to `templates/LENS-INSPECTION.md`'s findings table (`<day folder>/JOB-<N>-LENS-INSPECTION.md`).

## 5 · Then

The findings go to adjudication (`templates/ADJUDICATION.md`): each one reproduced against the code, then accepted, rejected or partly accepted. Accepted findings become the builder's test-first repair work orders. This skill fixes nothing itself.

## Output

Scope (range, pinned head, manifest), lenses run and skipped with reasons, ordered findings, any halted lens, remaining risks. **Never** a SHIP / BLOCK verdict, a fix, a commit, a push or a PR.
