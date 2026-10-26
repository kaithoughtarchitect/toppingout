---
name: f-schedule
description: >
  Break a decision-complete plan (a /f-blueprint BLUEPRINT, or any plan too big
  for one job) into a PROJECT: one ticket file per job, a dependency graph, and
  the first project board (BOARD.json + a generated board page). Use when the user runs
  /f-schedule, says "break this plan into tickets", "decompose this into jobs",
  "turn this plan into a project", or when a plan has more than one PR's worth of work.
  Proposed-first: shows the cut and waits for the owner's go before writing.
  Not for writing the plan (f-blueprint), not for planning one ticket's job
  (the foreman's scoping + PLAN.md), not for board updates after that (f-board).
  Also answers to its old name, /f-decompose.
---

# Topping Out: Decompose

**One plan in, one project out: a ticket per job, and a board you can follow.**

**A new head after a topping out** (`METHOD.md` §11b) gets a **new project folder and board** (`foreman/projects/<new slug>/`), never the topped-out board, which is the old project's frozen record. Read the topping out report's carried-over items before cutting: they are candidates for the new board.

In Topping Out (`METHOD.md` §12–§13), a job is always **one ticket**: one PR, one module area, roughly 8–9 work orders. A plan bigger than that becomes a **project**. This skill cuts it.

```
/f-survey → /f-blueprint (the blueprint) → /f-plancheck (cold cross-family read) → /f-schedule (tickets + board) → pick a job
        → one job per ticket (f-board start) → /f-signoff → f-board close → next job
        (repeat while a next job is confirmed; at the head, top out and stop: METHOD.md §11b)
```

## Usage

```
/f-schedule <path to BLUEPRINT>            # propose the cut, then write on go
/f-schedule --split <project-slug> <job-id>  # split one job that scoping found too big
```

## Where things go

- **The project folder:** `foreman/projects/<project-slug>/` **in the records repo** (jobs, work orders, reviews), not the product repo (in a single-repo setup, the same `foreman/projects/` path).
- **The templates:** `templates/` inside this skill's folder (`PROJECT.md`, `TICKET.md`, `BOARD.json`).
- **The board tool:** the `f-board` skill's `render_board.py` (installed: `.claude/skills/f-board/render_board.py`).
- **The job header for a job:** `Project: <slug>`, `Job: <id>`, `SourcePlan: <path>`, never `Blueprint`, so `/f-signoff` can't retire the whole project's plan (`skills/f-signoff`, "The blueprint is never retired here").

## Phase 0 · The f-plancheck gate

**First, the end-game lock:** run `node <skills>/f-signoff/endgame.mjs check --root <records root>`. Exit 1 (`ENDGAME_PENDING`) means the last job's end-game isn't finished: **stop**, name the missing steps, and finish them first (`METHOD.md` §10). Exit 2 or 3 is an error, never a pass.

The plan must carry a **`gate: plancheck` line** (older plans: `gate: plan-read`, the same gate under its old name) (written by `/f-plancheck`, the cold cross-family read of the blueprint), and every finding it raised must be applied or answered in the plan. **No gate line (`grep -nE '^\*{0,2}gate: (plancheck|plan-read)' <plan>`; f-plancheck writes it in bold) → stop** and tell the owner to run `/f-plancheck <plan>` first. A plan with unanswered f-plancheck findings is not decision-complete. Apply them under the f-plancheck discipline (`METHOD.md` §13): one read, each finding judged against the locked decisions, evidence-backed findings only, every fate recorded in the blueprint's `## Plan check findings` table (copied into `PROJECT.md`'s). **A row with a blank fate → stop**: the transfer step (`METHOD.md` §13) isn't done.

## Phase 1 · Read (no writes)

1. **Read the plan whole.** Extract, quoting exactly:
   - the **head**: the one outcome the plan exists for, and how it's judged (usually its final owner-facing acceptance, never a green gate alone);
   - the **locked decisions** (D-ids);
   - the **verification points** (VP-ids), each with its "cheaper wrong route to reject";
   - the **tasks** and their prerequisites;
   - the **assumptions, HALTs and outward items** (spend, live access, installs, owner decisions).
2. **Read the plan's later dated notes and any job it spawned.** A later note can retire an earlier requirement. Where they disagree, list it for the owner; never pick silently.
3. **Measure what's already built** (repository before plan): commits, files, tests, partial work, open jobs and their HALT receipts, with the commands.
4. **If the product uses a ticket tracker** (e.g. Jira): read the live board for the plan's area. Map each job to an **existing** key where one fits (**never mint a key**, never propose minting one); compare the tracker's "blocks" links with the jobs' `needs`. Disagreements go on the owner's list; the tracker isn't silently overridden, and neither is the plan.

## Phase 2 · Cut the jobs

1. **One job = one ticket = one PR = one module area**, sized for roughly 8–9 work orders.
2. **Research, qualification and owner decisions are their own jobs.** A question that ends in the owner's answer is a decision job (stored state `decision`, with the question and its owner); research that produces a file (a document, an audit, data) is a **build** job and goes through a PR (`RULES.md` rule 13). **Never hide them inside a build job**: in one product, a first job halted with buildable work trapped behind two research HALTs.
3. **Every VP maps to at least one job.** An unmapped VP is a gap: report it.
4. **Every plan task maps to a job, or to "not carried, on purpose"** with its reason.
5. **Dependencies are explicit** (`needs`), only where a job truly consumes another's output.
6. **Kind and state from evidence:** a job delivered by a PR is `kind: build` (`merged` only with a PR, a merge SHA and its job; otherwise `open`); a job delivered by the owner's call is `kind: decision` (`decision`, with its question and owner; `resolved` once decided). The tool derives ready/blocked; a need is satisfied by `merged` or `resolved`.
7. **Job 00** is often the plan's frozen controls or foundation already on main.
8. **First `next`:** an eligible job; prefer the one that unblocks most, then the one with most partial work.

With more than ~10 jobs, run `simplicity-critic` on the cut (any job doing two jobs? two jobs that are one?).

## Phase 3 · Propose (stop; write nothing)

Show the owner:
- the head;
- the job table: id, title, state, needs, the VPs it carries, the tracker key if any, one line on what it builds;
- the decision jobs: what must be decided, by whom, what each unblocks;
- unmapped VPs or tasks, plan disagreements, tracker disagreements;
- the recommended first job, and why.

## Phase 4 · Write (each act on its own word)

**On "go" for the project** (records repo, the foreman's own records):
1. `PROJECT.md` from the template: the head, the D-table and VP→job map quoted verbatim, the jobs, the owner's decisions, what's not carried, the reconciliation with what's built.
2. One `tickets/TICKET-<nn>-<slug>.md` per job. Acceptance **quoted**, never reworded. **No state field:** state lives only in `BOARD.json`.
3. `BOARD.json`: `project.title` = **the blueprint's title** (it is the board's name on every render; the owner may edit the text later), `project.head.outcome` and `head.test` from the head above, `version: 1`, today, `next`, `publish: {"url": null, "local_html": "board.html"}`, each job's `kind` and stored state.
4. Validate and render: `python <path>/render_board.py foreman/projects/<slug>/BOARD.json`. It refuses bad states, unknown needs, cycles, a merged job without its SHA, a decision job without its question, an ineligible `next`.

**Separate word: publish the board page** (publish mode `artifact` only; a new private page, icon `diagram`). Record the URL in `publish.url` and `publish.granted: true`, and run the tool once more. From then on, `f-board` republishes to that one link.

**Separate word: a note on the source plan** (it lives in `foreman/blueprints/ready/` in the records repo; also add "→ `foreman/projects/<slug>/`" to its entry in `foreman/blueprints/README.md`): one line at the top, "Decomposed into `<records>/foreman/projects/<slug>/` on <date>; the project and its tickets are now the execution order." Never delete or rewrite the plan.

Commit nothing unless the owner asks.

## `--split <project-slug> <job-id>`

When scoping shows a job is bigger than one PR: `render_board.py BOARD.json split <id> --into "a=Title A,b=Title B" [--chain] [--active a]` (one event: the children replace the job, dependents are rewired to the last child with `--chain` or to all children without it, a job in progress continues on its `--active` child, one version, a supersession record). Then move the VPs across in new ticket files (each VP still carried) and record the split in `PROJECT.md`. A merged or decision job can't be split.

## Report

The project folder, job counts by state, the first `next`, the board link (once published), and every gap or disagreement still open.

End with the 5-line status block (`templates/J-STATUS.md`).
