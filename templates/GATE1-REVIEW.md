# J<N>: gate 1 review (the builder's plan)

> **Form B only** (the builder wrote the plan). **In form A** (default), gate 1 is the `/f-plancheck` result on the foreman's own `PLAN.md`, recorded in the plan header and the job file before work order 2; this template isn't used.

**By:** the foreman, <date>. **Reviewed:** `<job file>` (<lines>, Phases 0–4) and `<work order 2 report>`.
**Disk first:** worktree HEAD `<sha>`, `git status --short` = `<...>`, commits: <n>; job file <CR count>, Foreman line, VP header, gate lines.

## 1 · The audition verdict (only if the builder is on audition)

| Point | Verdict | Evidence in the plan |
|---|---|---|
| a · <hard point> | FOUND / MISSED / half-seen | <plan :line and what it shows> |
| b · ... | | |
| c · ... | | |

**Result: <k> of 3.** <Consequence under the audition rule.>

## 2 · Findings on the plan (each reproduced against the tree at `<sha>`)

| # | Finding | Evidence | Disposition for the next work order |
|---|---|---|---|
| G1 | <what is wrong> | <plan :line; code file:line> | ACCEPT / PARTIAL / REJECT: <what the work order carries> |

**Held as correct and kept:** <what the plan got right; say so explicitly>.

## 3 · What the next work order carries

The decisions of `<your scoping file>`, with G1–Gn applied. <Self-contained for a fresh builder, if a switch is possible.>
