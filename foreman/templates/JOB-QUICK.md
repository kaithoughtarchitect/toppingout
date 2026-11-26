# J<n> (board <NN>): <title>

**Project:** <project slug (its board: `foreman/projects/<slug>/BOARD.json`)>
**J-number:** J<n> (this job's ID for life) · **Board:** <NN> (its place on the project's board) · **Kind:** build
**Ticket:** <tracker key and link>
**SourcePlan:** <path to the blueprint section this job came from, or `none`>
**Size:** QUICK (agreed by the owner at "go")
**Crew:** <foreman and builder | master builder> · **the owner's crew word:** <quoted, with where it was said (this job's "go", the goal, a night shift's marks, or carried over from J<n>), or "none: foreman and builder by default">
**Inspections:** lens inspection: SKIP (QUICK) · independent inspection: run
**Validation strategy:** <code-read | check | harness | UI> (harness: its name and command from the repo profile)
**Budgets:** repair work orders per task <3> · wall time <…> · foreman tokens <…>
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
| 3: Plan and gate 1 | `PLAN.md` + its `gate: plancheck` line | ⬜ | |
| 4: Tasks | the plan in force (below) | ⬜ | |
| 5: Build | one or several tasks per work order, each work order reviewed | ⬜ | |
| 6: Gate 2 and inspection | `GATE2-REVIEW.md`, independent inspection (lens inspection: SKIP (QUICK)) | ⬜ | |
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

**Plan:** <day folder>/PLAN.md (the foreman's) · **Gate 1:** <the `**gate: plancheck**` line f-plancheck wrote>

| Finding | Fate (applied / rejected with reason) |
| --- | --- |
| | |

## Phase 4: Tasks (the plan in force)

| Task | Outcome (one, independently verifiable) | Work order | Commit | Review | Status |
| --- | --- | --- | --- | --- | --- |
| T1 | | 2 (plan in force + T1) | | | ⬜ |

## Phase 5: Build

_Each work order's review is linked in the task row above. Repairs are counted against the budget, as a running count per task:_ <task: build repairs n, inspection repairs n, walkthrough repairs n, Greptile repairs n>.

## Phase 6: Gate 2 and inspections

| Round | File | Findings | Accepted | Repair work orders |
| --- | --- | --- | --- | --- |
| Base-vs-head (builder) | | red-at-head-only <n> | | |
| Gate 2 (foreman; the builder's base-vs-head checked on disk) | | | | |
| Lens inspection | SKIP (QUICK) | none | none | none |
| Independent inspection (`/xreview`, another family) | | | | |
| Fix review | | | | |
| Greptile rounds (`/f-greploop`, max 3; the round table in the skill) | | score per round | | |

## Phase 7: Verification

**Final head:** <full sha> · **t-final:** <folder> · **base-vs-head:** red-at-head-only <n> at `<sha>` · **repairs since t-final:** <none, or their affected tests at `<sha>`> · **the whole suite (builder, t-final):** <f> failed, each labelled introduced / inherited / environment · **CI at the final head:** run <id>, <green / red> · **main's latest CI:** <not red, run <id>>

**Harness receipt** (validation strategy `harness` only): <harness name · run id · verdict> | not applicable

### Files changed (`git -C <wt> diff --name-status <base>..<final head>`)

| Status | Path |
| --- | --- |
| | |

### Verification points

| VP | Risk | Requirement | Proof (command + output, or test name; P0: the probe id too) | Result |
| --- | --- | --- | --- | --- |
| <VP id> | <R id> | <command + output, or test name> | <PASS / FAIL> |

**The one safety fact:** <property>, <proof or "unproven because …">

## PR and merge

**PR:** <#n, link> · **Reviewed head:** <sha> · **Reviewed tree:** <`git rev-parse <sha>^{tree}`> · **Merge:** <sha> · **Merge tree check:** <equal to the reviewed tree / the head with main merged in: command + output>

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
