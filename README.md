# Topping Out

**Let AI coding agents work through your tickets for hours, even overnight, without drifting: every job starts fresh from files, a cheap model does the heavy coding, and your Claude Code limit lasts far longer.**

Each job ends with evidence you can check: what was asked, what was built, what was tested, and what reviewers found.

Site: [toppingout.dev](https://toppingout.dev) · Repo: [github.com/kaithoughtarchitect/toppingout](https://github.com/kaithoughtarchitect/toppingout)

The smallest loop:

1. a **foreman** session reads the ticket and the code, and writes exact work orders;
2. a **builder** session implements each one and reports, with its test output;
3. the foreman checks the work on disk, and **inspectors** (fresh review sessions, one of them from another model family) review it and only report;
4. **you, the owner,** give the word for the acts `RULES.md` reserves for you: merging, pushes, messages, migrations and the rest.

Work orders reach the builder as a one-line pointer: you paste it, or the foreman sends it over a pane link. With an autonomous-run goal (`/goal autonomous run: …`), or a night shift of them, a job runs to the merge without you (with the pane link carrying the pointers), inside the grants `RULES.md` ("The one exception") lists. Any other standing goal grants nothing.

The name comes from the building site: the ceremony held when the last beam goes on. The roles follow the site too, and the skill names start with `f-`, for foreman, the role that runs them. It has been used on real codebases since September 2026.

**How to start:** in the repo that will hold your records, start a session and say `Read <path to this folder>/skills/f-setup/SKILL.md and follow it` (`SETUP.md`). Then run one job (below). You don't need the whole flow first: the foreman follows `METHOD.md`, and you answer when it asks.

**Tested on** Windows with Claude Code as the foreman. macOS and Linux are expected to work (the scripts are Node, Python and Bash) but aren't verified yet: `SETUP.md`, "Tested setup".

### One job, from your side

1. Give the foreman a ticket: a tracker link, or a short `TICKET-<nn>.md` (`/f-sketch` helps write one).
2. It walks the site, then asks for your **"go"**.
3. It writes work orders; you paste each pointer into the builder (or the pane link does it), until the build, the two inspections and the acceptance ledger are done.
4. On your word ("open the PR") it opens the PR, and on "greploop" runs up to three Greptile rounds. You say **"merge"** when the evidence satisfies you.
5. It closes the job, saves the lessons, and proposes the next ticket for you to confirm.

---

## Start here

| If you are... | Read |
|---|---|
| A new foreman | this README → `METHOD.md` → `RULES.md` → `OVERRIDES.md` → `Foreman-Playbook.md` → `templates/` |
| The owner | this README → `METHOD.md` §"The owner's loop" → `BUILDER-PROFILES.md` |
| Setting it up in a new repo | `SETUP.md` |
| Choosing or running a builder | `BUILDER-PROFILES.md` + `Builder-Playbook.md` |

---

## The idea in seven lines

1. **One ticket = one job = one branch = one PR.**
2. **The foreman never writes product code; the builder never makes design decisions.**
3. **Everything goes through files.** Work orders are files, reports are files, reviews are files. The builder gets a one-line pointer (from the owner, or sent over a pane link by the foreman), never pasted text.
4. **Disk before words.** After every builder step, the foreman checks commits, captures and files on disk *before* it reads the builder's report.
5. **Every claim carries its evidence:** a command and its output, a commit hash, a test name. A claim without evidence counts as not done.
6. **Some acts need the owner's word.** These are approval boundaries, not all of them irreversible: merging and pushes, tracker transitions, messages, branch and worktree deletion, edits outside the ticket's files, migrations, and the "greploop" grant for at most three Greptile rounds on one PR. The full list, and the exceptions (the job's own cleanup and records push after a verified merge, an autonomous run's grants), are in `RULES.md`.
7. **Every reply ends with the 5-line status block** (`templates/J-STATUS.md`).

---

## The flow at a glance

**Before any job**, a big plan is cut into tickets: `/f-survey` → `/f-blueprint` → **`/f-plancheck`** (cold cross-family read) → **`/f-schedule`** (project, one ticket per job, the project board). Each job below builds **one** ticket (`METHOD.md` §13).

```
 SHIFT HANDOVER + OPENER ──> SITE WALK ──> [owner: "go"]
                                          │
          BUILDER PRE-FLIGHT (read-only env check) ── READY / BLOCKED
                                          │
 WORK ORDER 1  setup + baseline (worktree, job file, t0 captures) ── no code
                                          │
 WORK ORDER 2  form A (default): "plan in force + T1" (the foreman wrote and validated the plan)
          form B (an audition): the builder writes the plan as plain steps (WORK-ORDER-2-PLAN.txt)
                                          │
 GATE 1   form A: /f-plancheck on the foreman's own plan (cold seats, other families; before work order 2)
          form B: the foreman reviews the builder's plan ──> findings
                                          │
 WORK ORDER 3..N  one decision-complete task per work order, test-first, one commit each
      │  after EACH: disk check → work order review (re-probe, verify test-first, switch-rule line)
      │  next work orders drafted while the current one runs
                                          │
 BASE-VS-HEAD  builder work order; any red-at-head-only = STOP, foreman characterises
 GATE 2   foreman reviews every commit + runs its own base-vs-head
 LENS INSP.    foreman runs /f-inspect in its own session (fresh lens agents) ──> checks each finding ──> repair work orders (QUICK: skipped)
                                          │
 CROSS-MODEL   foreman /pack-review (checks its own brief) ──> fresh session of another
               family runs /xreview ──> foreman /adjudicate ──> repair work orders
 FINAL RE-RUN  all captures, probes, both base-vs-head again at the final head
 ACCEPTANCE LEDGER  no FAIL/UNTESTED/INCONCLUSIVE to open the PR; every row PASS (the foreman's own run done) to merge
                                          │
 PR opened (owner watches it in the browser) ──> [owner: "greploop"] /f-greploop: ≤3 Greptile rounds
      (adjudicate → builder repairs → tests + both base-vs-head + ledger re-run → push) ──> PR description check
                                          │
 [owner: "merge"]
                                          │
 /f-signoff (+ Logbook cards) ──> dev report ──> next-ticket decision ──> you confirm ──> /f-board close ──> handover + opener ──> records push
                                          │
 when every job on the board is done: TOP OUT: close the last job ──> topout (board frozen as the record) ──> topping out report ──> candidate next heads
                                          │
 [owner picks a head] ──> /f-survey ──> /f-blueprint ──> /f-plancheck ──> /f-schedule ──> a new board, and the loop starts again
```

**Topping out** is where the name comes from: when a board reaches its head (every job merged or resolved), the end game freezes it as the project's record, writes what was built and what's carried over, and offers three to five candidate next heads. You pick one, whenever you're ready, and the cycle starts again on a new board (`METHOD.md` §11b). Work found while testing a product goes on an **iteration board** instead: no blueprint, small jobs added as you find them.

---

## Folder map

| Path | What it is |
|---|---|
| `README.md` | this page |
| `DESIGN.md` | **the look every Topping Out page shares**: the hard-hat mark, colours, type, the interaction rules and which source builds each page |
| `flow.html` | **the whole flow as one picture**: 45 steps in seven stages, swimlaned by who does each, with the skill, agent and template used (open in a browser) |
| `skills-wiki/` | **the map of every skill and agent**: start at `skills-wiki/index.md`; says which agents Topping Out uses. `graph.html` pictures the links |
| `scripts/` | `build_flow.py` (builds `flow.html` from its step list) and `build_skills_wiki.py` (builds `skills-wiki/` from its skill and agent list): edit these, never the pages they write. `wiki_lint.py`, `wiki_graph_html.py` (the Skill Atlas), `skills_wiki_sync.py` (keep the wiki honest), `picker_style.py` (applies DESIGN.md to the three picker consoles) and `cross-review-dispatch.mjs` (runs `/xreview` headless on another model family) |
| `METHOD.md` | the full method, stage by stage, with the "why" behind each step |
| `OVERRIDES.md` | where the method beats the bundled skills and agents (read before using them) |
| `RULES.md` | the non-negotiables, and the list of acts that need the owner's word |
| `BUILDER-PROFILES.md` | what each builder did; the audition; the switch rule |
| `Foreman-Playbook.md` | the foreman's playbook (named after the role): how to do the foreman's part well: planning, work order checklist, review order, your own mistakes to avoid. `Foreman-Playbook.html` is the same as a page, built by `scripts/build_foreman_playbook.py` |
| `Builder-Playbook.md` | running any builder without hiccups, a light one especially (`Builder-Playbook.html` is its page) |
| `SETUP.md` | installing the skills and agents into a repo |
| `skills/f-schedule/templates/` | `PROJECT.md`, `TICKET.md`, `BOARD.json`: the files `/f-schedule` writes for a project (the one copy) |
| `templates/` | fill-in-the-blanks for every document the method produces, in the order they're used (see `METHOD.md`) |
| `snippets/` | code to copy: the gate runner template, the import-scan script and the mutation-probe harness template |
| `examples/example-board/` | a **made-up** project board (synthetic data, generated by `/f-board`): open `board.html` to see what a board looks like |
| `skills/` | **30 skills, the complete set.** Topping Out's own: `f-setup`, `f-sketch`, `f-survey`, `f-blueprint`, `f-schedule`, `f-shift`, `f-board`, `f-signoff`, `f-night-shift`, `f-status`, `f-comply`, `f-inspect`, `f-greploop`, and the Logbook's `f-card`, `f-search`, `f-archive`, `f-archive-search`, `f-catchup`, `f-context`, `f-distill`, `f-dream`. Shared: `f-plancheck`, `pack-review`, `xreview`, `adjudicate`, `model-council`, `agent-council`, `speak`, `converse`, and the pane link `orca-pi-connect` (Orca) |
| `addons/deep-agents/` | **optional:** for an AI agent built on LangChain, LangGraph or Deep Agents. `/f-setup` asks and installs it only on yes: the `/deep` skill, a reference checked against the real `deepagents` code, LangChain's docs server, and a running agent skeleton for a new project (`addons/deep-agents/README.md`) |
| `agents/` | the agents Topping Out uses: `simplicity-critic`, `handoff-builder`, `spec-validator-fixer`, the review lenses `f-inspect` calls (including `lens-instructions` and `lens-migrations`), the optional `code-explorer`, and `plan-validator` (used only inside `f-plancheck`, as its checklist). |
| `foreman/` | everything the method owns in a repo: `ideas/` (f-sketch), `blueprints/` (`ready/`, `deferred/` and the index `README.md`), `projects/<slug>/` (the project and its board), `jobs/` → `completed-jobs/YYYY-MM/` (job records), `handovers/` (shift handovers and their answer keys), `logbook/` (cards, index, links, archive helper) and `templates/` (the job records). SETUP creates it all |
| *(in your repo)* | **the full picture of what Topping Out adds to your repo, and where a job's files go over its life:** `SETUP.md` §2, "What Topping Out adds to your repo" |

---

## Precedence

When two sources disagree: **the owner's own words → `RULES.md` → `METHOD.md` → `OVERRIDES.md` → `BUILDER-PROFILES.md` / `SETUP.md` → `Foreman-Playbook.md` (the why behind the foreman rules in `RULES.md`) / `Builder-Playbook.md` → `templates/` → the bundled `skills/` and `agents/`.** The bundled skills and agents are general; `OVERRIDES.md` lists exactly where the method beats them.

## What it is not

- **Not autonomous by default.** By default you give the word for every push, PR, review round and merge (except the job's own cleanup and records push after a verified merge): the owner is the one piece a confident report can't talk round. **Autonomy comes only from an explicit grant:** an autonomous run (`/goal autonomous run: <path to the job's opener>`) or a night shift covers exactly the acts `RULES.md` ("The one exception") lists, for the jobs it names, and repairs what goes red and stops only on the conditions `RULES.md` ("The one exception") lists. A standing goal never covers the other gated acts.
- **Not a second judge on top of the foreman.** Reviews are layered by *independence* (a fresh session, a different reader), not by stacking graders. Separate reviewers reduce some failure modes; they don't guarantee correct code.
- **Not tied to one builder.** Any agent that can read a file, run a shell and write a report can build. How much the work order has to spell out depends on the builder (see `BUILDER-PROFILES.md`).

## What software enforces, and what is only instructed

Most of the method is instructions the agents follow; a few checks are scripts that refuse. Know which is which:

| Promise | Enforced today by | What is not prevented |
|---|---|---|
| Gated acts (push, merge, messages) wait for your word | **instruction** (`RULES.md`), plus your coding tool's own permission prompts. The package ships no hook | an agent with push rights and pre-allowed commands can push; nothing in the package blocks it technically. `SETUP.md` §5 suggests a hook for migrations only, and `SETUP.md` §7 asks you to pre-allow `git push`, `gh pr create` and `gh pr merge` for an autonomous run |
| What merged is what was reviewed | **a check the foreman runs:** the merged commit's tree must equal the reviewed and tested tree (`METHOD.md` §10 step 3), and `skills/f-signoff/endgame.mjs verify-merge` refuses a close whose merge isn't on the main branch | the tree comparison is not scripted, and `verify-merge` checks only that the merge commit is on main (and runs because `/f-signoff` calls it); an edit after the final re-run invalidates the acceptance and is caught only if the foreman re-runs, as the rules require |
| Nothing new starts until a closed job's end game is done | **a script the skills run:** `endgame.mjs` keeps a lock file; the planning skills and work order 1 run its `check` and stop while it exists | an agent that skips the `check` call isn't stopped |
| The review is independent | **a script, when used:** `scripts/cross-review-dispatch.mjs` seats the reviewer on another vendor's CLI, in a separate process, from a brief (`/pack-review`) | the foreman writes the brief, so it chooses what the reviewer is pointed at and told (the reviewer can also read the checkout, read-only); seats exist only for Claude and codex foremen; this is separation, not adversarial isolation |
| The whole ask is done | **instruction plus a record:** the acceptance ledger lists every requirement and check with its evidence, and `/f-signoff` refuses unless every row is PASS. A change to the ask is recorded in the owner's own words (`METHOD.md` §2) | the ledger is written and checked by agents; a wrong PASS is caught only by the reviews or by you |
| Builder names stay out of the records | **a script the foreman runs:** `skills/f-signoff/names-check.mjs` checks every staged record at the records push and exits non-zero on a hit | it runs only when the foreman calls it at the records push; it checks only the names in your names file, and skips allowed contexts and rendered board pages |

## Licence

MIT. See `LICENSE`.
