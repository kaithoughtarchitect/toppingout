# J<n> (board <NN>): <title>

**Project:** <project slug (its board: `foreman/projects/<slug>/BOARD.json`)>
**J-number:** J<n> (this job's ID for life) · **Board:** <NN> (its place on the project's board) · **Kind:** build
**Ticket:** <tracker key and link>
**SourcePlan:** <path to the blueprint section this job came from, or `none`>
**Lane:** STANDARD
**Inspections:** lens inspection: run · independent inspection: run
**Validation strategy:** <code-read | check | harness | UI> (harness: its name and command from the repo profile)
**Budgets:** repair work orders per task <3> · wall time <…> (usage-limit pauses don't count) · foreman tokens <…>
**Foreman:** the foreman
**Builder:** the builder
**Target repo:** <path> · **Worktree:** <absolute path> · **Branch:** <branch>
**Base:** <full sha> (`git -C <wt> rev-parse <remote>/<main>` at the cut) · **Final head:** <full sha, filled at Phase 7> · **Started:** <YYYY-MM-DD HH:MM>
**Acceptance ledger:** <day folder>/JOB-<NN>-ACCEPTANCE-LEDGER.md

## Risk Assessment

| Risk | Impact (1-5) | Probability (1-5) | Score | Mitigation |
| --- | --- | --- | --- | --- |
| | | | | |

_Score = Impact × Probability. 15-25 critical, 10-14 high, 5-9 medium, 1-4 low._

## Phase Status

| Phase | Topping Out artifact | Status | Done |
| --- | --- | --- | --- |
| 0: Setup and t0 | work order 1 report | ⬜ | |
| 1: Requirements | `SCOPING.md` | ⬜ | |
| 2: Design | settled decisions `D-…` in `SCOPING.md` | ⬜ | |
| 3: Plan and gate 1 | Form A: `PLAN.md` + its `gate: plancheck` line · Form B (audition): the builder's plan + `GATE1-REVIEW.md` | ⬜ | |
| 4: Tasks | the plan in force (below) | ⬜ | |
| 5: Build | one work order per task, each reviewed | ⬜ | |
| 6: Gate 2 and inspections | `GATE2-REVIEW.md`, lens inspection, independent inspection | ⬜ | |
| 7: Verification | final re-run + acceptance ledger | ⬜ | |

## State Summary

_One paragraph the foreman rewrites at every phase boundary: what's decided and why, what's locked, what's open. The shift handover copies it._

---

## Phase 0: Setup and t0

**Gate runners:** <paths> · **t0 captures:** <folder>

| Gate | t0 result |
| --- | --- |
| | |

**Mechanism answers:** <Q1…Qn, with file:line>

## Phase 1: Requirements

| Id | Requirement (from the ticket as the site walk left it, verbatim) | VP |
| --- | --- | --- |
| <R id> | <requirement> | <VP id> |

## Phase 2: Design

| Decision | Choice | Rejected, and why |
| --- | --- | --- |
| D-1 | | |

## Phase 3: Plan and gate 1

**Form:** <A: the foreman's plan | B: an audition> · **Plan:** <day folder>/PLAN.md · **Gate 1:** <Form A: the `**gate: plancheck**` line f-plancheck wrote | Form B: GATE1-REVIEW.md path>

| Finding | Fate (applied / rejected with reason) |
| --- | --- |
| | |

## Phase 4: Tasks (the plan in force)

| Task | Outcome (one, independently verifiable) | Work order | Commit | Review | Status |
| --- | --- | --- | --- | --- | --- |
| T1 | | <Form A: 2 (plan in force + T1) · Form B: 3> | | | ⬜ |

## Phase 5: Build

_Each work order's review is linked in the task row above. Repairs are counted against the budget, as a running count per task:_ <task: build repairs n, inspection repairs n, walkthrough repairs n, Greptile repairs n>.

## Phase 6: Gate 2 and inspections

| Round | File | Findings | Accepted | Repair work orders |
| --- | --- | --- | --- | --- |
| Base-vs-head (builder) | | red-at-head-only <n> | | |
| Gate 2 (foreman + its own base-vs-head) | | | | |
| Lens inspection (`/f-inspect`, foreman's session) | | | | |
| Independent inspection (`/xreview`, another family) | | | | |
| Fix review | | | | |
| Greptile rounds (`/f-greploop`, max 3; the round table in the skill) | | score per round | | |

## Phase 7: Verification

**Final head:** <full sha> · **t-final:** <folder> · **base-vs-head at final head:** red-at-head-only <n>

**Harness receipt** (validation strategy `harness` only): <harness name · run id · verdict> | not applicable

### Files changed (`git -C <wt> diff --name-status <base>..<final head>`)

| Status | Path |
| --- | --- |
| | |

### Verification points

| VP | Requirement | Proof (command + output, or test name) | Result |
| --- | --- | --- | --- |
| <VP id> | <R id> | <command + output, or test name> | <PASS / FAIL> |

**The one safety fact:** <property>, <proof or "unproven because …">

## PR and merge

**PR:** <#n, link> · **Reviewed head:** <sha> · **Reviewed tree:** <`git rev-parse <sha>^{tree}`> · **Merge:** <sha> · **Merge tree check:** <equal to the reviewed tree / the tested merge-preview tree: command + output>

---

## Key Discoveries

### Patterns Found

| Pattern | Type | Reuse Potential |
| --- | --- | --- |
| | | |

### Key Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| | | |

### Problems Solved

| Problem | Root Cause | Solution |
| --- | --- | --- |
| | | |

---

## JOB COMPLETE

**Status:** PENDING
**Closed:** <YYYY-MM-DD HH:MM, filled by /f-signoff>
**Requirements Satisfied:** <X/X>
**Tasks Completed:** <X/X>
**Verifications Passed:** <X/X>
**Duration:** <started → closed>
**Lines of Code:** <+X added, -Y removed (net +/-Z)>
