# Setup

## 1 · Install the complete package into the repo that holds your records

**The way in is `/f-setup`.** Start a session in the repo that will hold your records and say `Read <path to the package>/skills/f-setup/SKILL.md and follow it`. It installs the package, writes the repo profile from what the repo actually has (asking you only what it can't find out), sets up the names files and the test adapter, runs the checks, and lists the files for your commit. The install copies `f-setup` too, so later runs (an upgrade, a re-check) are just `/f-setup`. The sections below say what it does, for reference and for a setup by hand.

This folder is the whole package: **30 skills** (Topping Out's own `f-*`, including `f-setup`, `f-sketch`, `f-comply`, `f-inspect` and `f-greploop`, plus the shared `pack-review`, `xreview`, `adjudicate`, `f-plancheck`, `model-council`, `agent-council`, `speak`, `converse`, `orca-pi-connect`), 13 agents (repo-agnostic), templates, snippets, scripts. **Install rule: copy only what's missing; never overwrite.** A skill, agent, template or Logbook the repo already has may carry that repo's adaptations (§1 "Adapt"), so an install never replaces it. Updating an existing file is an **upgrade** (below), done file by file with a diff. Topping Out's skills are all `f-*` or uniquely named, so they sit beside a repo's other skills without colliding.

The installer is one Node script, the same on Windows, macOS and Linux:

```bash
PKG="<path to the Topping Out package>"; REPO="<path to the records repo>"
node "$PKG/skills/f-setup/install.mjs" --repo "$REPO" --dry-run   # what it would copy, and what it keeps
node "$PKG/skills/f-setup/install.mjs" --repo "$REPO"             # copy what's missing, never overwrite
```

It copies skills to `.claude/skills/`, agents to `.claude/agents/`, the dispatcher and the voice trio to `scripts/`, the job templates to `foreman/templates/`, and the method (the top-level `.md` files, `templates/`, `snippets/`, `examples/`) to `foreman/method/`; the Logbook only where the repo has none (an existing one keeps its cards, index and links). It creates the `foreman/` folders, writes `foreman/INSTALL-RECEIPT.txt` (the package revision, the date, one `installed …` line per file) and adds `scratch/` to `.gitignore`. The site, the wiki and the page generators are not installed. A package that is a git checkout must have no uncommitted changes (only its committed files are copied, so the receipt's revision matches them).

**Names file after an upgrade:** the check matches each line as a literal whole word; `names-check.mjs` refuses (exit 2) a line with regex characters, so rewrite alternations and `?` as one plain name per line.

**Upgrade** (a newer package over an existing install; only with the records checkout on `<main>`, no job worktree open and no end game pending; if a sync lands mid-job anyway, the foreman re-reads the method files it changed, listed in the sync commit, before its next step): `node <package>/skills/f-setup/install.mjs --repo <repo> --upgrade` prints the plan from the receipt's revision (add `--apply` to write): a file unchanged here since the receipt is replaced, one adapted here is kept and listed, to merge by hand with a diff. It refuses while a job is open or an end game is owed. **Files the package added** are copied; **files it removed** are deleted when unadapted here, else listed. The Logbook's cards, index and links are never touched. With `--apply` it rewrites the receipt's revision line. Then update any repo-profile row naming a removed path.

**Upgrade by hand** (a receipt without a git revision, a package without git, or an install from before receipts): for each file the package changed since the old revision, `diff` the repo's copy against the package's. Replace it where the repo's copy is unadapted; merge by hand where it carries adaptations. Copy the files the package added; delete the ones it removed once a diff shows no local adaptation. Never touch the Logbook's cards, index or links (its card templates, `README.md`, `ARCHIVE-SYSTEM.md` and scripts upgrade the same way). Then write the new revision into the receipt.

**The Deep Agents add-on** (only for a product that is an AI agent built on LangChain, LangGraph or Deep Agents): `/f-setup` asks, and on yes installs `/deep`, a reference checked against the real `deepagents` code, LangChain's docs server and, for a new project, a running agent skeleton (`--addon deep-agents [--starter]`). `/deep` becomes the framework check the ground investigation runs at every end game that has a next job. It needs Python 3.11 or later. What it holds, and how its sources are fetched rather than shipped: `addons/deep-agents/README.md`.

**Optional add-ons, installed with the rest, working once set up:**
- **Voice** (`speak`, `converse`, `f-survey --voice`): `OPENROUTER_API_KEY` in the repo's `.env` (read by `scripts/bootstrap-env.ts`), Node with `npx tsx`, Windows audio playback. Check with `npx tsx scripts/speak.ts <a text file>`.
- **Councils.** `model-council`: an OpenRouter key. `agent-council`: **always** the pinned Pi CLI (the exact version in its `references/`) with an OpenRouter key, because its preflight and auditor run through Pi; qualified native subscription CLIs (claude, codex, grok) are optional extra transports. Its `self-test` is structural only: it doesn't prove seats are reachable. `f-survey` uses the councils to settle a fork only when the owner authorises it.
- **`f-comply`**: the `claude` CLI, authenticated. `node .claude/skills/f-comply/comply.test.mjs` checks the grader offline; `--run` spends subscription turns and is opt-in.

**Then write the repo profile** (`templates/REPO-PROFILE.md` → `<records>/REPO-PROFILE-<product>.md`, i.e. `foreman/REPO-PROFILE-<product>.md` in single-repo mode), and the git-ignored names file it points to (default `scratch/names-kept-out.txt`: the builders' model, vendor and tool names, one per line; and `scratch/names-allowed.txt`: the contexts that contain one by design, such as the builder tool's own folder; `node <skills>/f-signoff/names-check.mjs --self-test` proves the checker on this machine): the method root, gates, shell, worktree tool, ticket mode (tracker or local), board publish mode (artifact or local), merge strategy, budgets, and the test adapter. Every opener names it.

**Then the test adapter** (`templates/TEST-ADAPTERS.md`): copy the block for the repo's test runner into `<records>/test-adapter.sh` (`foreman/test-adapter.sh` in single-repo mode), set its paid-key list from the profile, and prove it on the two-fixture check (the same test file in two folders, base and head failing different tests plus one shared failure; `comm -13` must print only the head-only one: `skills/f-setup/SKILL.md` Step 4). Record the proof in the profile. Every work order sources this file, so the first job can't start without it. Keep this method folder where the profile says: the openers and skills read its top-level files.

**Check the install:** `python .claude/skills/f-board/test_render_board.py` must pass.

For builders that read agent-neutral folders instead of `.claude/`, mirror the same skills into `.agents/skills/`.

**Adapt:** the skills and agents are repo-agnostic: they read the repo's gates, database change paths and conventions from the repo profile (`templates/REPO-PROFILE.md`) and the constitution (`AGENTS.md` or `CLAUDE.md`), so fill those in rather than editing the skills. If you do adapt a skill, note it in the repo profile so an upgrade can diff it.

## 2 · Two repos, kept apart (or one, with a boundary)

| Repo | Holds |
|---|---|
| **Records repo** | job files, work orders, reports, reviews, captures, shift handovers. **No product code, ever.** |
| **Target repo** (system under test) | product code only, built in **worktrees** cut by name from `<remote>/<main>` |

**Single-repo mode is supported:** records and product in one repo. The records then live under `foreman/`, `foreman/projects/` and the day folders, and the boundary is by path: a work order's commits touch only product paths, and records are committed separately by the foreman (never in a product commit). The repo profile says which mode the repo uses.

### What Topping Out adds to your repo

Everything below is created by the install (§1) or by a step of the method; the right-hand column says which. In single-repo mode it all sits beside your product code; with two repos, `.claude/` and `foreman/` go in the records repo.

```
your-repo/
├── .claude/
│   ├── skills/                    the 30 skills (see the skills pages)          install
│   └── agents/                    the 13 agents (see the skills pages)          install
├── scripts/
│   ├── cross-review-dispatch.mjs  sends the independent review to another AI company's session   install
│   └── speak.ts, speak-setup.ts, bootstrap-env.ts   the voice add-on (optional)   install
├── foreman/                       everything the method owns
│   ├── method/                    the method itself: METHOD.md, RULES.md, the two playbooks, BUILDER-PROFILES.md, templates/ (every document the method writes)   install
│   ├── REPO-PROFILE-<product>.md  your gates, shell, test adapter, remotes      you, at setup
│   ├── test-adapter.sh            how this repo's tests are run and read        you, at setup
│   ├── ideas/                     IDEA-<date>_<slug>.md                        /f-sketch
│   ├── blueprints/
│   │   ├── README.md              the index: ready, deferred, ideas
│   │   ├── ready/                 BLUEPRINT-<date>_<slug>.md                   /f-blueprint, checked by /f-plancheck
│   │   └── deferred/              plans put off before any build
│   ├── projects/<slug>/           one folder per project                       /f-schedule
│   │   ├── PROJECT.md             the plan cut into jobs
│   │   ├── tickets/               TICKET-<nn>.md, one per job
│   │   ├── BOARD.json             the board's data (the only place job state lives)   /f-board
│   │   └── board.html             the board page, generated from BOARD.json    /f-board
│   ├── jobs/                      JOB_<date>_<slug>.md: the job in progress    work order 1
│   ├── completed-jobs/<YYYY-MM>/  closed jobs, filed by month                  /f-signoff
│   ├── handovers/                 AGENT-HANDOFF-<date>-job-<N>-<slug>.md, its site-walk answer key, and OPENER-JOB-<N>.txt (the next session's opener)   end of each job with a next job
│   ├── logbook/                   lessons that outlive a job                   /f-card, /f-signoff
│   │   ├── logbook_index.md       the card catalogue: every live card, its type and topic, the counts   updated with every card
│   │   ├── logbook_links.md       how cards relate: one supersedes, refines or contradicts another     updated with every card
│   │   ├── entries/
│   │   │   ├── insights/          INSIGHT cards: a lesson or gotcha (why)
│   │   │   ├── methods/           METHOD cards: a repeatable way of doing something (how)
│   │   │   └── builds/            BUILD cards: what a job built
│   │   ├── archived/              older cards moved out once there are more than 250   /f-archive
│   │   ├── sessions/              saved copies of past sessions
│   │   ├── ARCHIVE-SYSTEM.md      how cards are moved to the archive
│   │   ├── archive_cards.py       the script that moves them (with its test)
│   │   └── README.md              which skill reads or writes which part
│   ├── templates/                 the job file, by size: JOB-QUICK.md, JOB-STANDARD.md, JOB-FULL.md   install
│   ├── ENDGAME-PENDING.md         only while a closed job still owes its end-game steps   /f-signoff
│   └── INSTALL-RECEIPT.txt        which Topping Out version is installed, and when   install
├── work-sessions/<Month-Year>/Work-<date>/   one folder per working day
│   ├── JOB-<N>-SITE-WALK-ANSWERS.md, JOB-<N>-SCOPING.md, JOB-<N>-PLAN.md      before work order 1
│   ├── JOB-<N>-BUILDER-PREFLIGHT.txt and its -REPORT.md                       before work order 1
│   ├── JOB-<N>-WORK-ORDER-<m>.txt, -REPORT.md, -REVIEW.md                     each work order
│   ├── captures                    test and gate outputs, from the first run and each work order
│   ├── JOB-<N>-LENS-INSPECTION.md, blind-pack/ (the outside review's brief)  the two reviews
│   ├── JOB-<N>-ACCEPTANCE-LEDGER.md, the PR body                              before the pull request
│   └── the dev report, JOB-<N+1>-NEXT-TICKET-DECISION.md, the next session's brief (at a topping out: TOPPING-OUT-REPORT.md, NEXT-HEADS.md)   after the merge
├── .claude/skills/deep/, deepagents-ref/, .mcp.json   the Deep Agents add-on (only on yes); its agent skeleton (src/agent/, tests/ …) only for a new project   /f-setup
└── scratch/                       working files (plan checks, councils, voice) and names-kept-out.txt + names-allowed.txt (the names the records push checks for); keep it in .gitignore
```

### A job's files, start to finish

| When | What appears | Where |
|---|---|---|
| The board is checked and you say "go" | the job marked started | `foreman/projects/<slug>/BOARD.json` |
| Before work order 1 | the site-walk answers, the builder pre-flight and its report, the scoping, the plan | the day folder (`JOB-<N>-SITE-WALK-ANSWERS.md`, `JOB-<N>-BUILDER-PREFLIGHT.txt`, `JOB-<N>-SCOPING.md`, `JOB-<N>-PLAN.md`) |
| Work order 1 | the job file, plus the first test and gate captures | `foreman/jobs/JOB_<date>_<slug>.md`; the day folder |
| Each work order | the work order, the builder's report, the foreman's review | the day folder (`JOB-<N>-WORK-ORDER-<m>.txt`, `…-REPORT.md`, `…-REVIEW.md`) |
| The two reviews | the lens inspection, then the brief for the outside reviewer and the adjudication | the day folder (`JOB-<N>-LENS-INSPECTION.md`, `blind-pack/`) |
| Before the pull request | the acceptance ledger and the PR body | the day folder |
| After the merge (`/f-signoff`) | the job file moves; the lessons become Logbook cards; the end-game lock opens | `foreman/completed-jobs/<YYYY-MM>/`, `foreman/logbook/`, `foreman/ENDGAME-PENDING.md` |
| Then, in order | the dev report, the next-ticket decision, your confirmation, the board close, the handover and the next session's opener; the lock clears; the records are pushed (at the board's head: the close, the topout, the topping out report and the next heads instead, `METHOD.md` §11b) | the day folder; `BOARD.json`; `foreman/handovers/` (`OPENER-JOB-<N>.txt` beside the handover) |

The product's own changes never go in these folders: they're built in the job's worktree and reach `main` only through the pull request.

## 3 · Gate runners

Write one runner per job (copy `snippets/run-gates.sh` and fill in its CONFIG and GATES blocks):
- it starts with `WT=` and `LOG=` lines, and every run is `env -u <paid keys> ...`;
- it writes one `.txt` and one `.exit` per gate, plus a `summary.txt` ending `ALL DONE`;
- runs are serial, and each is called with a label (`t0`, `t1`, ...), so captures never overwrite each other.

A code area that no gate covers gets its own runner by explicit path: another copy of the same template, whose gates name that area's tests.

## 3b · The mutation-probe harness

One script per job (e.g. `tests/acceptance/<ticket>_mutation_probes.py` in the target repo). Each probe finds its guard **by a unique anchor read from the file** (never a hand-copied line number), breaks it in place, runs the named tests, prints **BITES** (red) or **GREEN** (still passing), then restores the file byte for byte. A full run exits non-zero if any probe is GREEN. Probes are written in the work order that adds the guard (`WORK-ORDER.txt` B.2b). The harness to copy: `snippets/mutation_probes.py` (fill in its CONFIG block and add one `Probe` per guard). It reports BITES, GREEN, DIRTY or UNRUN (a test that fails by raising still bites, and the line shows its first error), restores every file byte for byte, and refuses to run with an empty probe list. Before sending a work order, `PROBE_ROOT=<the tree after its edits> python <harness> --check-anchors` checks every anchor still matches exactly once, without running tests.

## 4 · Optional: the pane link

The bundled skill **`skills/orca-pi-connect`** lets the foreman send pointers to a Pi builder in the pane beside it, in **Orca** (the builder pane split to the foreman's right, in the job's worktree), and wait on Pi's real turn-end signal. It needs:
- **Orca** installed, with both sessions running inside it (`orca` on PATH; the foreman's pane has `ORCA_TERMINAL_HANDLE`);
- Pi's global stop extension, listening to `agent_settled`: bundled at `skills/orca-pi-connect/pi-extension/foreman-stop.ts` (writes `~/.pi/agent/foreman-stops.log`). Copy it to `~/.pi/agent/extensions/` and restart Pi so it loads. A Pi that already runs another stop extension writes to that extension's log: pass its path as `--log`.
- a bound pane and Pi session ID before anything is sent: a pane the foreman opened itself binds at once (exactly one new pane, on its right, a fresh session id, or the old one when resuming after host sleep, `orca-pi-connect` §1b; the handshake proves it); a pane it did not open, or a wrong count or place, needs the owner's yes (`orca-pi-connect` §1 gives the conditions);
- **a background stop watcher**, armed after every send (`.claude/skills/orca-pi-connect/stop-watch.mjs`, run as a background command so its exit wakes the foreman). A foreman that only checks the stop log during its own turns misses stops made while it's idle.

Without it, or with another pane host, hand-carry the one-line pointers: the method is the same either way. (The night shift needs Orca.)

## 5 · Optional guard hooks

Topping Out ships no hooks. If your tool supports them (Claude Code's PreToolUse hooks, for example), a migration guard is worth adding. The principle: **migrations and schema files can't be edited until the owner types an exact phrase.**

## 6 · Projects and the board

When a board reaches its head, the end game **tops it out** (`METHOD.md` §11b): a report, the board frozen as the project's record, and candidate next heads; the next head gets a new board. Work found while testing goes on an **iteration board** (`init --iteration`).

`/f-schedule` writes `foreman/projects/<slug>/` in the **records** repo. The skills carry what they need: `skills/f-schedule/templates/` and `skills/f-board/render_board.py` (Python 3, stdlib only). Copy the whole skill folders, not just `SKILL.md`. The first publish creates the board page's link; `BOARD.json` keeps it, and every `f-board` event republishes there.

## 7 · Start a job

0. If the work is a big plan, run `/f-schedule` first and pick the `next` job; the job builds that ticket. A project that wasn't cut still needs its board before "go": `render_board.py foreman/projects/<slug>/BOARD.json init …`, then `add` the planned jobs (and `add --merged` any already merged).
1. **The first job on a board** (the repo's first board, or a new head's board after a topping out): fill `templates/SESSION-OPENER-FIRST-JOB.txt` and paste it into a fresh foreman (no shift handover exists yet). **Every later job:** fill `templates/HANDOFF-SESSION-BRIEF.md`, ask the `handoff-builder` agent to build the shift handover from it, then fill `templates/SESSION-OPENER.txt`.
2. Paste the opener into a fresh foreman.
3. Follow `METHOD.md` from §2.

**To run a job without you (an autonomous run):** in a fresh foreman, instead of pasting the opener, type `/goal autonomous run: <path to OPENER-JOB-<N>.txt>, until done or stopped` (add `, spend up to <n> USD (read, or a ceiling under it)` if the walkthrough needs a live key or a paid review seat; the builder's own bill never counts). It takes that one job from the site walk to the merge and the end game, and repairs what goes red and stops only on the conditions `RULES.md` ("The one exception") lists. `RULES.md` ("The one exception") says exactly what it covers. Before leaving it alone: pre-allow in your coding tool the commands it will run (`git push`, `gh pr create`, `gh pr merge`, the browser tools), and leave the browser open, or it waits on a prompt. **Several jobs in a row (a night shift):** in a fresh session in the records checkout, type `/goal night shift: jobs <board id>, <board id>, until done or stopped` (or `/goal night shift: 2 jobs, auto-pick, until done or stopped`). The first job's opener must exist, and the repo profile must name the **Foreman launch command** (how you start a foreman session, with your usual flags). In the morning read `foreman/handovers/NIGHT-SHIFT-<date>.md`.

## 8 · Windows notes

Each of these cost a turn the first time it bit. Read them before the first job on a Windows machine.

- **Line endings.** A system-wide `core.autocrlf=true` turns checked-out files into CRLF. Byte-level tests then pass in the worktree and fail after a fresh checkout, and `git archive` applies the same conversion, so it can't stand in for a Linux checkout. Pin LF in the repo with a `.gitattributes` (`* text=auto eol=lf`) and set `git config core.autocrlf false` there.
- **`ref:path` arguments.** Git Bash rewrites anything that looks like a path, including `HEAD:src/app.py`. Prefix the command with `MSYS_NO_PATHCONV=1`, or run that one git call from PowerShell.
- **Headless Chrome screenshots** need an absolute output path; a relative one is silently written elsewhere or not at all.
- **The stop watcher can be reaped.** The coding tool may kill background shells under memory pressure, and a dead watcher means the foreman can't see the builder stop. `orca-pi-connect` §6 tells the foreman to read the Stop log itself at the start of its next turn, and to go hand-carried if the log can't be read. A real job reported that setting `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1` before starting Claude Code stops the reaping; treat that as a reported workaround, not a documented setting.

## 9 · Tested setup

**Tested:** Windows 11, Claude Code as the foreman, Git Bash for work orders, Node 22, Python 3.12, on real repos since September 2026. That is the only configuration every step has run on.

**Expected to work, not yet verified:** macOS and Linux. The installer and the checks are Node and Python, the work orders are Bash, and nothing in the core method needs Windows (the voice add-on's playback does); the Windows-specific parts are workarounds (§8). If something breaks on another system, it is most likely a path or shell difference an agent can fix in place.

| Part | Needed | Notes |
|---|---|---|
| A foreman: a coding agent that runs skills (Claude Code tested) | required | |
| A builder: any coding agent that can read a file, run a shell and write a report | required | `BUILDER-PROFILES.md` |
| `git`, Node 18+, Python 3.9+, Bash | required | `/f-setup` checks each |
| Hand-carried work orders | the default | you paste a one-line pointer; works with any builder and any terminal |
| Orca and Pi (the pane link) | optional adapter | `skills/orca-pi-connect`, §4 above; an autonomous run you leave alone, and the night shift, need it |
| Greptile | optional | the PR review rounds; `none` in the profile skips them |
| A session from a second model family (the independent review) | required (`METHOD.md` §8) | its CLI lets the dispatcher run it headless (Claude and codex foremen); hand-carrying the brief into that family's session also works |
| Paid calls and add-ons | optional, opt-in | the councils, voice and a live-key walkthrough spend money only when you allow it; tests always run with paid keys stripped. Voice needs Windows audio playback today; `agent-council` needs the pinned Pi CLI (§1) |

**Removing it:** the package's files are the `installed …` lines in `foreman/INSTALL-RECEIPT.txt`, including those an upgrade added. Delete those you haven't adapted, then the receipt and the lines the installer added to `.gitignore`. With the Deep Agents add-on, also remove the `docs-langchain` entry from `.mcp.json` if it was merged by hand, and `deepagents-ref/sources/`. The agent skeleton (`starter …` lines) is your product code and stays. Your records are yours and stay: `foreman/jobs/`, `foreman/completed-jobs/`, `foreman/projects/`, `foreman/handovers/`, the Logbook's cards, `foreman/REPO-PROFILE-*.md`, `foreman/test-adapter.sh` and the day folders.
