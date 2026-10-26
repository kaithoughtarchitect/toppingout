---
name: f-blueprint
description: >
  Topping Out's second step: write one decision-complete BLUEPRINT under
  foreman/blueprints/ready/ (the head it serves, locked decisions, verification points,
  tasks, HALTs and outward items), to be cold-read by /f-plancheck and then cut into
  one-PR tickets by /f-schedule. No implementation. Use for /f-blueprint or after
  /f-survey. Not for open decisions (f-survey), not for cutting into tickets
  (f-schedule), not for building.
---

# Topping Out: Blueprint

**In Topping Out this plan is a project, never one job.** After writing it: `/f-plancheck <plan>` (cold seats from other model families; it writes the `gate: plancheck` line), apply or answer its findings, then `/f-schedule <plan>` cuts it into jobs. So the plan must name, quoted exactly: **the head** (the one outcome it serves and how it's judged, e.g. the owner's walkthrough), the **locked decisions** (D-ids), the **verification points** (VP-ids, each with its cheaper wrong route to reject), the **tasks**, and every **assumption, HALT and outward item** (spend, live access, installs, owner decisions). Research and owner decisions are listed as such, never hidden inside a task.


Write **one plan file** that a later agent can execute. Do not implement, open a job, run f-plancheck, stage, commit, or push. (The owner or the foreman runs `/f-plancheck` afterwards, as a separate step.)

## North star

**Fidelity over cleverness.** Capture the commission and what was already agreed in context. Do not expand, renegotiate, drop, or “improve” the deal.

- Prefer close paraphrase or settled wording over rewrite.
- If commission and context conflict, **halt and surface**, do not pick a side silently.
- Completeness of the **agreement**, not completeness of the universe.
- Tight and high-signal is good. Inventing detail to fill a template is not.

**Capture the agreement in product terms; ground it in code terms; invent neither.**

## Preconditions

0. **First, the end-game lock:** run `node <skills>/f-signoff/endgame.mjs check --root <records root>`. Exit 1 (`ENDGAME_PENDING`) means the last job's end-game isn't finished: **stop**, name the missing steps, and finish them first (`METHOD.md` §10). Exit 2 or 3 is an error, never a pass.
1. Extract the commission, locked decisions, constraints, exclusions, actors/boundaries, acceptance, and open items from the conversation and any survey block.
2. If load-bearing choices are still open (architecture, data model, API, acceptance, or scope that changes the solution), **stop** and use `f-survey`. Do not invent them to finish the plan.
3. Open items may remain only when they are empirical checks or **explicitly labeled deferred** with a default-if-silent or `HALT until decided`.

## Exploration

Inspect the real codebase to **ground** the agreement, not to grow scope.

- Confirm current paths, symbols, interfaces, patterns, tests, the repo's own scripts and gates (the repo profile names the gates), and dependencies the agreed work will touch.
- Small scope: one bounded `code-explorer` question. Cross-cutting: independent explorers with non-overlapping questions.
- If code reality conflicts with the agreement, surface the conflict; do not silently rewrite the commission.
- Budgets: a latency, speed or size figure becomes a pass/fail VP only with a measured baseline (its anchor named); otherwise write it as `estimate`, and the VP records the measured figure.
- Harness/measurement work: if the repo has a measurement or eval harness, the repo profile names it (its commands, what it grades, what a run costs). Plan its validation **before first spend** (the harness is checked sound before any paid run), keep capture separate from grading (the harness captures; whatever the repo uses as its grader grades), never put the plan's own acceptance text into a grading prompt, and list every paid run as an outward item. A repo with no such harness: say so and verify with its ordinary gates.

## Plan file

Write exactly one file:

`foreman/blueprints/ready/BLUEPRINT-YYYY-MM-DD_<short-slug>.md`

File hygiene only (not job lifecycle): if deliberately postponed before any build, move it to `foreman/blueprints/deferred/`. Do not delete from this skill.

### Header

- **Title · Date · Status** (`ready` | `blocked-on-decision`)
- **Objective** (faithful to commission)
- **Background** (only context needed to understand the deal)

### Body (in order)

1. **Commission capture**, user outcomes and agreed behavior as settled; no product freestyle.
2. **Decisions (locked)**, table or list `D0…` with final wording only for choices already made.
3. **In scope / Out of scope**, explicit fence; do not add “while we’re here.”
4. **Assumptions**, marked as assumptions, not decisions.
5. **Unresolved**, only rows that must not be invented at build; each has **default if silent** or `HALT until decided`.
6. **Done-When and verification**, checkable acceptance from the agreement; positive and negative verification points with stable ids when useful; map to real repo commands where they exist.
7. **Grounding (descriptive)**, inventory: files to **modify** vs **create** (path + role); patterns to mirror with file/symbol evidence. Current state only.
8. **Interfaces (prescriptive)**, types, shapes, migrations, flags, boundary/error contracts **required by** the agreed work. Label clearly as future state. Omit speculative architecture.
9. **Ordered tasks** `T0…`, implementation of the **agreed** commission only. Each task:

   - **Owns**, paths
   - **Prereq / Blocked by**, none or task ids
   - **Outcome**, end-to-end behavior this slice makes true
   - **Trace**, `D*` / Done-When / VP ids
   - **Verify**, an existing gate from the repo profile, or a documented script in the repo's own manifest, + expected signal (never invent a gate)

   Prefer thin vertical slices of agreed capability over horizontal layering. One context-window–sized task. Coding-agent work only (write / modify / test). No orphan steps that leave unintegrated work. No tasks for out-of-scope items.

10. **Risks, rollback, environment**, thin; real constraints only.
11. **Post-implementation gates**, only from the constitution the repo profile names (`AGENTS.md` or `CLAUDE.md`) and the gates listed in the repo profile. Never invent a gate.
12. **Plan check findings**, the heading `## Plan check findings` and an empty table `| # | Finding (with its evidence) | Fate | Why |`. `/f-plancheck` writes the `gate: plancheck` line; the foreman fills the table from its output (`METHOD.md` §13, the transfer step). `/f-schedule` refuses a blank fate.

Mark **descriptive current state** vs **prescriptive future state** so they cannot be mixed unmarked.

### Code in the plan

Talk about code as **grounding**, not as the implementation:

| Include | Exclude |
|---|---|
| Paths, modules, create vs modify | Full diffs / line-by-line patches |
| Contracts and shapes the deal requires | Speculative interfaces not in the agreement |
| Patterns to mirror with evidence | Redesign freestyle |
| Real verify commands and signals | Invented gates or ops theater |

Docs/process commissions may stay path-light; software commissions must be code-grounded enough for a cold agent.

## Accuracy pass

Call `spec-validator-fixer` on the plan. It may correct only **provably false descriptive** claims about current code or scripts. It must **preserve intended future state** and all commission/decision wording. Re-read the final file: every referenced **current** path, symbol, and script exists (or is listed under Create).

## Index

In the same pass as writing the blueprint, add a **Ready** entry to `foreman/blueprints/README.md` (create it from the package copy if missing): path, one sentence, and what gates it (usually "needs `/f-plancheck`"). When a blueprint is deferred, move its file to `foreman/blueprints/deferred/` and its entry to **Deferred**, with the trigger that brings it back. When `/f-schedule` cuts it, add "→ `foreman/projects/<slug>/`" to its entry. Trust the disk: fix any entry that disagrees with it.

## Report

Return:

- plan path
- what was captured (objective + decision count + task count)
- validation result
- any unresolved items left as default/HALT (not invented)
- conflicts surfaced between agreement and codebase, if any

Do not implement, stage, commit, push, open a job, or run f-plancheck from this skill.
