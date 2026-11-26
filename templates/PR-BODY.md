# J<N> · board <id>: <what it delivers, in plain words>

> **The PR title is this heading, exactly** (`METHOD.md` §10 step 1): `J<N> · board <id>: <what it delivers>`, e.g. `J82 · board 12: tenancy wrappers for LangGraph (TenantSaver, TenantStore)`. A PR outside any job (no job file, no records): `Owner: <what it changes>`.

**Scan the finished body for builder names before opening the PR.**

## 1 · What this changes
<Two or three sentences: what existed, what this adds, what it makes possible. Whether there is a migration.>

## 2 · The acceptance criteria against the code

| Criterion (verbatim) | Where it holds (file:line) | Proof (test name / proof module) |
|---|---|---|

## 3 · Design decisions
Each with its evidence and what was rejected.

## 4 · Files
<Each file, one line on what it does. Nothing outside the ticket's files (a master builder job: every file outside the plan's file list says why).>

## 5 · How it was proved
- New tests: <n>, plus <database proofs, on which disposable DB>.
- Mutation probes: <n>/<n> bite; every P0 VP has its probe.
- Non-functional checks: speed, security, privacy, cost: each PASS or `not touched` (from the acceptance ledger).
- Behaviour (AI features only): the eval harness, base vs head, or `not measured` (owed) / `not applicable`.
- Under an autonomous run: the survey answers it gave itself, any in-scope option taken over a starred pick, and any usage-limit pause (or "not an autonomous run").
- Base vs head: red-at-head-only = 0 (runs 1 and 2, at `<sha>`). The whole suite (builder, t-final at `<sha>`): <f> failed, each labelled inherited or environment with its evidence, none introduced. CI at the final head: run <id>, <green>.
- Captures: every gate at the final head, compared with the baseline.

## 6 · ⚠️ Limitations
What this does NOT do, and which ticket owns it. Anything characterised as an intermittent.

## 7 · Rollback
<If the ticket asks for one: how to switch it off or revert, and what state that leaves.>

## Review record

| Round | What it found |
|---|---|
| Plan review (gate 1) | |
| Task reviews | <or, in a master builder job: `none (master builder)`, and the fix reviews below> |
| Build review (gate 2) | |
| Lens inspection (f-inspect, by the foreman, or by the master builder with fresh lens agents) | <findings; accepted / rejected> or `SKIP (QUICK)` |
| Independent inspection (xreview, another model family) | <claims; accepted / rejected> |
| Greptile rounds (`/f-greploop`, on the open PR) | <round 1: n/5, findings accepted / rejected; round 2 …; at most three> or `none (no PR review bot: <the owner's recorded reason, from the repo profile>)` |
| Split under the autonomous run | `no`, or: the parent job, its children, the work-order count that triggered it, the goal's words (`RULES.md`, "Its own job's split"); for the owner to review |
