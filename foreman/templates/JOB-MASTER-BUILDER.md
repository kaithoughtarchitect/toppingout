# J<n> (board <NN>): <title>

**Project:** <project slug (its board: `foreman/projects/<slug>/BOARD.json`)>
**J-number:** J<n> (this job's ID for life) · **Board:** <NN> (its place on the project's board) · **Kind:** build
**Ticket:** <tracker key and link>
**SourcePlan:** <path to the blueprint section this job came from, or `none`>
**Size:** MASTER BUILDER (chosen by the owner at "go")
**Master builder:** the master builder <(standard) or (strong), when the repo profile's "Builders" row has two; never a model, vendor or tool> (its model's family goes only to `--host`, never into this file)
**Difficulty:** <1-5, from the ticket> · **Wall time budget:** <…>
**Inspections:** lens inspection: run (fresh eyes, its own family) · independent inspection: run (another family)
**Validation strategy:** <code-read | check | harness | UI> (harness: its name and command from the repo profile)
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
| 0: Setup and t0 | the master builder's setup note | ⬜ | |
| 1: Requirements | `SCOPING.md` | ⬜ | |
| 2: Design | settled decisions `D-…` in `SCOPING.md` | ⬜ | |
| 3: Plan and gate 1 | `PLAN.md` (tests first, the file list) + its `gate: plancheck` line | ⬜ | |
| 4: Tasks | the plan in force (below) | ⬜ | |
| 5: Build | one commit per task, tests first | ⬜ | |
| 6: Gate 2 and inspections | base-vs-head, the lens inspection, the independent inspection, fix reviews | ⬜ | |
| 7: Verification | base-vs-head again if needed, the whole suite at the final head, the acceptance ledger, the file-list check, CI | ⬜ | |

## State Summary

_One paragraph the master builder rewrites at every phase boundary: what's decided and why, what's locked, what's open. The shift handover copies it._

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

**Plan:** <day folder>/PLAN.md (the master builder's) · **Gate 1:** <the `**gate: plancheck**` line f-plancheck wrote>

| Finding | Fate (applied / rejected with reason) |
| --- | --- |
| | |

**The plan's file list** (every file and folder the plan expects to touch; on a `/f-schedule` v2 board, the job's `footprint`):

| Path | Why |
| --- | --- |
| | |

## Phase 4: Tasks (the plan in force)

| Task | Outcome (one, independently verifiable) | Tests written first, red at the parent commit (command + failing line) | Commit | Status |
| --- | --- | --- | --- | --- |
| T1 | | | | ⬜ |

## Phase 5: Build

_Helper agents used (mechanical work only, inside the file list):_ <none, or what each did>.

## Phase 6: Gate 2 and inspections

| Round | File | Findings | Accepted | Fixed in (commit) |
| --- | --- | --- | --- | --- |
| Base-vs-head | | red-at-head-only <n> | | |
| Lens inspection (`/f-inspect`, fresh lens agents) | | | | |
| Independent inspection (`/xreview`, another family, seated by the dispatcher) | | | | |
| Fix review (fixes no reviewer specified, through the dispatcher, another family) | | | | |
| Greptile rounds (`/f-greploop`, max 3; the round table in the skill) | | score per round | | |

## Phase 7: Verification

**Final head:** <full sha> · **t-final:** <folder> · **base-vs-head:** red-at-head-only <n> at `<sha>` · **repairs since t-final:** <none, or their affected tests at `<sha>`> · **the whole suite (t-final, <n> workers):** <f> failed, each labelled introduced / inherited / environment · **CI at the final head:** run <id>, <green / red> · **main's latest CI:** <not red, run <id>>

**Harness receipt** (validation strategy `harness` only): <harness name · run id · verdict> | not applicable

### Files changed (`git -C <wt> diff --name-status <base>..<final head>`)

| Status | Path |
| --- | --- |
| | |

### The file-list check

**Outside the plan's file list** (`git diff --name-only <base>..<final head>`): <none, or each path with its reason, also in the PR body>

### Step times (each as noted at the time, or `not recorded`)

| Step | Started | Took |
| --- | --- | --- |
| Plan and gate 1 | | |
| Build | | |
| Gate 2 | | |
| Lens inspection | | |
| Independent inspection | | |
| PR, Greptile and CI | | |

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
