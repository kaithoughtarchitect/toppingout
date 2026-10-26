---
name: f-board
description: >
  Build and maintain a project's board: the Ishikawa page the owner follows
  after every PR close. Runs the board tool (render_board.py) to record a lifecycle
  event (work starts on a job, a job closes, a job halts, a decision is
  made, a job is added, the board tops out at its head), which derives ready/blocked, bumps the version once,
  regenerates the page; then republishes it to the same link. Use when the user runs
  /f-board, at a job's "go" (start), at close (close), when a job halts or a
  decision job is decided, or when the user asks "what's next?" / "show me the
  board". Not for cutting a plan into jobs (f-schedule).
---

# Topping Out: Board

**The board is data plus a generated page. The tool changes the data; the page follows.**

`BOARD.json` holds the head, every job, its stored state and its record. `render_board.py` (in this skill's folder) validates it, applies **one** lifecycle event, derives which open jobs are *ready* (every need merged) or *blocked*, bumps `version` once, and writes `board.html`. **Never edit `board.html`**, and never change a job's state by hand: in one product a hand edit left the previous job's stats on the page.

## The page

`board.html` is drawn entirely from `BOARD.json`:

- **Header:** `project.title` as the name, `project.eyebrow`, the version and date; a gauge (the done count over one segment per job, coloured by state); counts for in progress, ready, blocked and to decide; **next** as the one hi-vis tag (on a topped-out board: "topped out <date> · <n> carried over" instead). The kicker reads "project board", or "iteration board" for one started with `--iteration`, and adds "topped out <date>" once it has. The first of `project.alerts` sits under it on a hazard-striped strip that opens The head tab.
- **Fishbone:** the spine runs into the head, drawn as a hi-vis sign (`project.head.outcome`). The spine is solid up to the last merged job and faint after it. One rib per job, alternating above and below, styled by state: merged or decided solid, in progress blue, ready dashed, blocked dotted, to decide amber, **next** hi-vis. A rib's label is outlined when done and solid when it matters (selected, in progress, to decide, next). With no `next`, a dashed "next: not chosen" slot. A job's optional `twigs` (up to three short lines) show on its rib when it's selected or hovered. On a narrow screen the drawing keeps its size and scrolls sideways inside its own box.
- **Job strip:** one continuous tape of job numbers under the drawing, a state colour along the bottom of each.
- **Panel with tabs:** **Job** (the selected job as a ticket: a state stripe, a spec strip of Key / Ticket / Run / Needs / PR / Merge, the summary, figures, lesson, and notes with its decision; earlier / later stay put while the ticket scrolls), **Open** (everything not merged or decided, the next job first; a row opens its job), **Debts** (numbered, from `project.owed`), **Split** (superseded jobs), **Lessons** (the project's rule beside each job's lesson), **The head** (the outcome and its test beside the alerts and standing facts). The page opens on the job in progress, else the next job, else the latest one done. It is complete without JavaScript; the script only switches jobs and tabs.

The page fits one screen on a desktop: the fishbone scales to its box, the selected job's name shows in the bar above it, and the tabs switch inside a fixed panel. On a phone it stacks and scrolls. Light and dark themes both follow the viewer's setting.

**The design lives in `render_board.py`, not in any per-project file.** Every project's `board.html` is regenerated from its `BOARD.json` on each event or `render`, so a change to the renderer reaches every board at its next render. To bring an existing board up to date, run `render_board.py <path>/BOARD.json render`.

**Optional fields** (all validated; each written by the step that knows it):

| Field | Shown | Written by |
|---|---|---|
| `jobs[].twigs` (≤3 short lines) | on the selected rib | `/f-signoff`, from the job's key discoveries |
| `jobs[].figures` (≤6 `{n, label, tone: good\|warn}`) | Job tab, as figures | `/f-signoff`, the job's few numbers that matter |
| `jobs[].lesson` (one paragraph) | Job tab, and gathered in the Lessons tab | `/f-signoff`, the job's lesson (the same one its Logbook card carries) |
| `project.owed` (list) | Debts tab | the foreman at each close: the debts the project still carries (loose ends left by merged work, not yet jobs) |
| `project.lesson` (`{title, rule}`) | top of the Lessons tab | the foreman, when a lesson holds across jobs |
| `project.alerts` (list) | hi-vis strip under the header (first one, "+n more") | the foreman: anything the owner must not miss (e.g. the tracker disagreeing with the repository) |
| `project.facts` (list) | The head tab | the foreman: standing facts about the project |

Hand-editing these text fields in `BOARD.json` is allowed; the next render picks them up. Write them without em dashes (, ): a comma, a colon or a full stop reads better on the page.

## Where things are

- **The tool:** `render_board.py` next to this file. Installed in a repo that's `.claude/skills/f-board/render_board.py`; in the method folder it's `skills/f-board/render_board.py`. Call it by that path.
- **The project folder:** `foreman/projects/<project-slug>/` **in the records repo** (where jobs, work orders and reviews live), not in the product repo. Board updates are the foreman's own records: no PR, no owner word to edit them. In a single-repo setup it's the same path.
- **Jobs have a kind.** `build` (delivered by work orders and a PR): stored `open`, `in-progress`, `merged`, or `decision` (halted for an owner question). `decision` (delivered by the owner's decision): `decision` → `resolved`. `ready`/`blocked` are **derived**, never stored: a need is satisfied by a `merged` or `resolved` job. **One job in progress at a time.**
- **Tests:** `test_render_board.py` next to the tool; run it after installing.

## The events (one command each, one version each)

| When | Command | What it records |
|---|---|---|
| The owner says "go" on a job | `render_board.py BOARD.json start <job> --run J7` (`J7` stands for the job's run label, whatever the repo numbers its jobs) | the job is `in-progress` and becomes `next`. Only a *ready* job can start |
| **Close** (after the merge is verified) | `render_board.py BOARD.json close <job> --pr "#22" --merge <merge sha> --next <job> [--note "<lesson>"] [--standfirst "<where the project stands>"]` (decided facts only: never a plan the next job's survey hasn't settled) | the job merged, the next job chosen, **in one version**. The tool refuses to close without `--next` when a job becomes eligible, unless `--no-next --reason "…"`. It warns when `--standfirst` is left out, and `check` warns when the standfirst still names a merged job as next |
| A job HALTs or stops | `render_board.py BOARD.json halt <job> --reason "<why>" --to open` (retry later) or `--to decision --decision "<what must be decided, by whom>"` | work on the job stops; the HALT is noted on it |
| The owner decides | `render_board.py BOARD.json decided <job> --note "<the decision, quoted>"` | a **decision job** becomes `resolved` (and its dependents can go ready), but only once its own needs are merged or resolved (deciding early is a re-plan: change its `needs` and record why); a halted **build job** goes back to `open` |
| Work on a job turns up a new one | `render_board.py BOARD.json add <id> --title "<title>" --summary "<what it builds>" [--needs a,b] [--decision "<question>"]` | a new job, open or decision. **Ids are never reused**, including the id of a job that was split |
| A job's summary is unclear | `render_board.py BOARD.json summary <job> --text "<what it builds, in plain words>"` | the summary on the Job tab, the line the owner reads to know what the job does without opening its ticket. One sentence, under about 20 words, plan references after it in brackets: *"Loads the catalogue as a runtime block, so later jobs can use it. (T2, VP-6)"*. `check` warns on a summary that is only references (*"Plan task T2; carries VP-6."*) |
| Scoping finds the job too big | `render_board.py BOARD.json split <job> --into "a=Title A,b=Title B" [--chain] [--active a]` | the children replace the job, dependents are rewired, work continues on the `--active` child, one version, a supersession record |
| **The board's head is reached** (top out without a quote only when every job is merged or resolved; with any job unfinished, only on the owner's own words with `--quote`, never a goal's. No eligible next job alone is not a topping out) | `render_board.py BOARD.json topout --report <path to the topping out report> [--quote "<the owner's words>"] [--head yes\|partly\|no]`, then `render_board.py BOARD.json report` prints the report's mechanical part | the board is frozen as the project's record (no event after it); unfinished jobs are recorded as carried over; jobs still ready need the owner's words (`METHOD.md` §11b) |
| **An iteration board** (work found as you go, no blueprint) | `render_board.py BOARD.json init --title "…" --head "<the outcome>" --job <id> --job-title "…" --iteration` | small jobs are added as they are found (`add`) |
| An open job turns out to be covered by another (the owner says so) | `render_board.py BOARD.json covered <job> --by <job> --quote "<the owner's words>"` | the job leaves the board for the superseded list with the owner's words; any job that needed it now needs the covering job |
| "What's next?" | `render_board.py BOARD.json next` (now) or `next --after-close <job>` (what closing the current job would unlock) | lists eligible jobs; changes nothing |
| Just refresh the page | `render_board.py BOARD.json` (add `--standalone` for a page to open from disk) | validate + render; no version bump. Set `publish.standalone: true` in BOARD.json to make every event render standalone |

**The board opens in your browser by itself** on its first page (a new board, from `init` or `/f-schedule`'s first render) and at every topping out; routine updates never open a tab. A page that isn't standalone opens from a standalone copy in the temp folder. Set `FOREMAN_BOARD_NO_OPEN=1` on a machine with no browser.

Exit codes: 0 ok · 1 invalid data, including a BOARD.json that isn't valid JSON (fix the data, never force) · 2 wrong usage or an impossible event (e.g. starting a blocked job) · 3 crash · **4 RENDER PENDING**.

**Write order.** `BOARD.json` is authoritative and is written first; `board.html` is derived and written second. On exits 1–3 `BOARD.json` is unchanged. On **exit 4** the event **was recorded** (the new version is in `BOARD.json`) but the page wasn't written: fix the cause (a locked or missing path), then run `render_board.py BOARD.json` to bring the page up to date. **Never replay the event**: that would record it twice.

## Every update, in this order

1. **Check reality before recording it.**
   - `close`: the merge is verified as in `METHOD.md` §10 step 3 (the actual merge commit M is in `<remote>/<main>`, and **M's tree equals the reviewed head's tree, or the tested merge-preview tree** when the target moved); `--merge` records **M**. **Never close a job on a report's word.**
   - `start`: the owner said "go" on this job.
   - `decided`: quote the owner's own words.
2. **Choose `--next` for a close** (a topping out takes `--no-next`, then `topout`, `METHOD.md` §11b): run `next --after-close <job>`; among the jobs it lists, pick the one that unblocks the most jobs, then the one with the most partial work on disk, then the project's order. The reason goes into the next-ticket decision (`templates/NEXT-TICKET-DECISION.md`), which cites the board version read before the close.
3. **Run the one command.** If it refuses, read the message: it's telling you the data or the event is wrong.
4. **Update the ticket file's Record section** (`tickets/TICKET-<nn>-*.md`: job, PR, merge). State lives only in `BOARD.json`.
5. **Republish** (publish mode `artifact` in the repo profile; mode `local` stops at the rendered file).
   - `publish.url` set and `publish.granted` true: read the live page by its URL first (the artifact tool's `read`), then publish `board.html` to that URL.
   - `publish.url` empty: **don't publish.** Render locally and ask the owner for the first publish (it uploads ticket and implementation details, even as a private page). On their word, publish a new private page (icon `diagram`), set `publish.url` and `publish.granted: true` (their standing permission to republish to that one link), and render once more.
6. **Report:** the event, the new version, the next job (or the topping-out status), the link.

## Where it sits in a job

- At the owner's **"go"**: `start` (`METHOD.md` §4).
- At **close** (`METHOD.md` §10): merge → verify → `/f-signoff` → dev report → the next-ticket decision (it names the board version it read, from `next --after-close <job>`) → the owner confirms → **`close … --next …`** (one new version) → shift handover (it measures and cites the new version). At the board's head: `close … --no-next` → `topout` → the topping out report and the next heads (`METHOD.md` §11b).
- On a **HALT**: `halt`, and the job records why.

## Starting a board for a project that wasn't cut (init and backfill)

Tickets written one at a time still need a board (`METHOD.md` §11):

```bash
render_board.py foreman/projects/<slug>/BOARD.json init --title "<project>" --head "<outcome>" --test "<how you'd know>" --job <first id> --job-title "<title>"
render_board.py foreman/projects/<slug>/BOARD.json add <id> --title "<title>" --needs <ids>                 # planned work, with its real needs
render_board.py foreman/projects/<slug>/BOARD.json add <id> --title "<title>" --merged --pr "#5" --merge <sha> --run J5   # a job merged before the board existed
```

`init` refuses to overwrite a board. Every project has one: the end-game's board step ticks only the project's `BOARD.json`, and the old free-text "n/a" is retired.

## Rules

- **Only the foreman updates the board.** The builder never touches it.
- **Never close without the merge check** (`METHOD.md` §10 step 3). Never choose a `next` the tool calls ineligible: wanting a blocked job is a re-plan (`/f-schedule --split`, or change `needs` and record why).
- **Decision jobs stay visible** until decided; don't reword them to look buildable.
- **Never name the builder** on the board.
- The page is published **private**; sharing is the owner's call from its Share menu.

End with the 5-line status block (`templates/J-STATUS.md`).
