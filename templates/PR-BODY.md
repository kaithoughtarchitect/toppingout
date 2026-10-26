# <KEY> <title>

**Scan the finished body for builder names before opening the PR.**

## 1 · What this changes
<Two or three sentences: what existed, what this adds, what it makes possible. Whether there is a migration.>

## 2 · The acceptance criteria against the code

| Criterion (verbatim) | Where it holds (file:line) | Proof (test name / proof module) |
|---|---|---|

## 3 · Design decisions
Each with its evidence and what was rejected.

## 4 · Files
<Each file, one line on what it does. Nothing outside the ticket's files.>

## 5 · How it was proved
- New tests: <n>, plus <database proofs, on which disposable DB>.
- Mutation probes: <n>/<n> bite.
- Under an autonomous run: the survey answers it gave itself, any in-scope option taken over a starred pick, and any usage-limit pause (or "not an autonomous run").
- Base vs head: red-at-head-only = 0 (both runs, at the final head).
- Captures: every gate at the final head, compared with the baseline.

## 6 · ⚠️ Limitations
What this does NOT do, and which ticket owns it. Anything characterised as an intermittent.

## 7 · Rollback
<If the ticket asks for one: how to switch it off or revert, and what state that leaves.>

## Review record

| Round | What it found |
|---|---|
| Plan review (gate 1) | |
| Task reviews | |
| Build review (gate 2) | |
| Lens inspection (f-inspect, by the foreman) | <findings; accepted / rejected> or `SKIP (QUICK)` |
| Independent inspection (xreview, another model family) | <claims; accepted / rejected> |
| Greptile rounds (`/f-greploop`, on the open PR) | <round 1: n/5, findings accepted / rejected; round 2 …; at most three> or `none (no PR review bot)` |
