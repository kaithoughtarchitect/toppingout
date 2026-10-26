# The Method, stage by stage

Each stage lists **who** does it, **what** it produces, and **why** it exists. The "why" matters most: every step here was added after a specific failure.

---

## 0 · Roles

**Two numbers, never one word for both.** A job's **J-number** (J21) is its ID for life: it counts up across every board in the repo, and it is the number in its branch, its job file and its records' names (`JOB-21-…`). Its **board number** (board 01) is its place on the current board's plan, and restarts on each new board. Write "J21" and "board 01", never a bare "job 21"; a PR number is GitHub's counter, never an ID.

Topping Out has four roles: the foreman, the builder, the inspectors (the lens agents and the cold reader from another model family) and the owner. "Foreman" always means the role, never the method.

| Role | Does | Never does |
|---|---|---|
| **Foreman** | scopes the ticket, settles the design, writes every work order, reviews every diff, runs its own base-vs-head checks, runs the lens inspection (`/f-inspect`) in its own session, writes repair work orders, writes the records | write product code in the build loop (except in the "converged case", §9) |
| **Builder** | cuts the worktree, writes the job file, runs gates and captures, writes code and tests, commits, fixes what the foreman accepts from each inspection, opens the PR when told | make design decisions, explain differences away, push or merge on its own |
| **Owner** | says "go", pastes the builder's pointers when there is no pane link, watches the PR, gives the exact word for every act that needs it (`RULES.md`) | arbitrate technical choices (the foreman decides on evidence and records what it rejected) |

**Mode 1** (the only mode this method uses): the foreman scopes, plans, writes every work order and reviews; the builder builds. The converged case (§9) is the one exception, and only the owner invokes it.

**The builder is never named** by model, vendor, agent or tool in any file, commit, PR or record. It is "the builder".

---

## 1 · The shift handover and the opener

**Who:** the previous job's foreman, at its end.
**Produces:**
- a **session brief** (what the next session needs to know; `templates/HANDOFF-SESSION-BRIEF.md`);
- a **shift handover** built from it by the `handoff-builder` agent: self-contained, with a site-walk questionnaire and a separate answer key (the agent writes both; the answer key is a separate file the new session opens only after answering);
- a short **opener** the owner pastes into a fresh session (the end game's last message offers it three ways, ready to paste: the opener itself, an autonomous run, or a night shift; see `skills/f-signoff`. A topping out writes no opener: it offers the candidate next heads, §11b): **a file**, `foreman/handovers/OPENER-JOB-<N>.txt` (N = the next job), beside the handover and its answer key, written from `templates/SESSION-OPENER.txt` with every blank filled. **The opener never adds, tightens or restates a rule:** it points to `RULES.md`. A choice the owner made for this job only is quoted with where they said it. The foreman's last message gives its path and its text, ready to paste. The end-game lock won't clear without it. (The very first Topping Out job in a repo has no previous job: `templates/SESSION-OPENER-FIRST-JOB.txt`.)

**Why:** a new context window knows nothing. The shift handover carries facts *with file:line evidence*, gotchas and red lines, so the new session doesn't rediscover them the hard way.

---

## 2 · The site walk

**Who:** the new foreman, before anything else.
1. Answer the site-walk questions **cold**, write them to a file, *then* open the answer key, score honestly and re-answer misses.
2. Verify the machine yourself (git heads, worktrees, containers). **Where your command disagrees with the shift handover, your command wins.** Say so. One drift is expected: a handover can't name the commit that holds it, so `<main>` being a few **records commits** ahead of the handover's base is a match; a **product** commit since that base is a real disagreement. The same holds for local `<main>` against `<remote>/<main>`: **records-only commits not yet pushed are a match**, reported as "push pending, carried by this job's records push", never a blocker (`RULES.md` rule 7); an unpushed **product** commit is a real disagreement.
2a. Check that no test file sits in the records where the product's test runner would collect it (`RULES.md` rule 11).
3. Re-read the **live ticket** yourself and transcribe it verbatim (open it in the browser with the browser tools, or ask the owner to; screenshot its linked-issues panel). Never trust a shift handover's summary of a ticket.
4. Report every owed decision and every disagreement with the shift handover, unprompted. **If the owner reshapes the ticket** at the site walk, write one line at the top of the site-walk answers, `Owner reshaped the ticket: "<the owner's words>"` (rule 17 in `RULES.md`), naming the opener's steps it supersedes; work order 1 copies the same line to the top of the job file. The rest of the records point to that line instead of marking each step.
5. **STOP and wait for "go".** Choosing the ticket is not authorising the build. In an autonomous run the owner's goal is the "go", and the foreman answers its own survey (`RULES.md`), unless a question has no clear recommendation or the site walk found a scope-changing disagreement (`RULES.md`).

**Why:** shift handovers rot within hours (a later commit, a moved branch). The ritual catches the rot before it becomes a wrong plan.

---

## 3 · The builder pre-flight

**Who:** the builder, from a work order the foreman writes (`templates/BUILDER-PREFLIGHT.txt`).
**Produces:** a report ending **READY** or **BLOCKED: <what>**.
**Checks:** the shell; git on the target repo; reading *and writing* outside its project folder; tools on PATH; what it does without asking a human.

**When:** it writes no product files (its only side effect is a `git fetch`), so it may run **before** the owner's "go". Work order 1 needs the "go".

**Why:** a builder in a new app (for example a desktop IDE that sandboxes its project folder) can fail at work order 2 for environmental reasons. The pre-flight costs five minutes and removes that whole class of failure. **A new builder always gets a new pre-flight**, and when the foreman writes one mid-job, that's the signal to switch builders.

---

## 4 · Work order 1: setup and baseline, no code

**Every job starts here, whatever its kind** (code, documents, an audit, research): work order 1 writes the job file, and every later work order, inspection and PR checks that it exists (`RULES.md` rule 15). Work with no job file isn't a job yet.

**On the board:** at the owner's "go", record it with the `f-board` **start** event (the job becomes in-progress and `next`). If the job later HALTs, record the **halt** event.

**Lane:** a ticket built by this method is **STANDARD** by default (job record `foreman/templates/JOB-STANDARD.md`); QUICK (`JOB-QUICK.md`) when the owner agrees it at "go"; FULL only if the ticket spans several services (`JOB-STANDARD.md` plus `JOB-FULL.md`). Work order 1 names the template for the lane.

**QUICK lane** (a small, low-risk ticket: one module, no security, concurrency, schema or outward change, no new dependency): the same work orders and mechanical checks, one base-vs-head run at the end, the acceptance ledger, and **one** inspection: the independent inspection. The lens inspection is skipped and recorded as `SKIP (QUICK)` in the job header, gate 2 and the PR's review record. The owner agrees the lane at "go"; any finding of a security or concurrency kind moves the job back to STANDARD.

**Budgets** (in the repo profile, recorded in the job header): max repair work orders per task (default 3), wall time, foreman tokens. Exhausting one is a HALT: re-scope the job, split it, or switch builder, with the owner. A usage-limit pause doesn't count against wall time, and never leads to a switch (§7e).

Template: `templates/WORK-ORDER-1-SETUP.txt`.

**The builder:** cuts the worktree **by name** from `<remote>/<main>` (the profile's remote and main branch, written into the work order); checks HEAD in two separate calls; writes the job file header; checks the gate runners (**who writes them:** for a light builder the foreman writes them from `snippets/` and the builder only verifies them; a strong builder writes them from `snippets/` itself); captures **t0** on every gate, serially; answers a few mechanism questions from the code.

**With a pane link** (§7e) the builder's pane has to start inside the job's worktree, so the order flips: the **foreman** cuts the job worktree first (by name, from `<remote>/<main>`, the same command), starts the builder there, and work order 1 **verifies** the worktree instead of cutting it. The base worktree, if needed, is still the builder's.

**Why:** a baseline captured *before any edit* is the only honest answer to "was that red before we touched it?". Flaky tests are named up front so nobody "fixes" them or re-runs them to green.

---

## 5 · Work order 2: the plan

There are two forms. **The foreman-plans form is the default**; the builder-plans form is only for an audition.

**A · The foreman plans (default).** The foreman writes the plan itself: its scoping (`templates/SCOPING.md`, forks settled) plus `templates/PLAN.md` (tasks, verification points, the tests each task must fail first). It has its own plan cold-read with **`/f-plancheck`** (seats from other model families; optionally `simplicity-critic` too) before work order 2, because no builder plan exists for gate 1 to catch its mistakes. **Work order 2 is then "plan in force + T1"**: the builder copies the plan into the job file and builds the first task, from `templates/WORK-ORDER.txt`.

**B · The builder plans (an audition).** The builder writes the plan itself, as plain numbered steps in the job file (`templates/WORK-ORDER-2-PLAN.txt`): requirements verbatim, design, verified citations, a verification-point table, tasks. **Plain steps only**, no planning commands or agents: say so in the work order. The foreman judges it at gate 1 (`templates/GATE1-REVIEW.md`).

**The audition** (form B only). For an untried builder, the foreman writes down the ticket's hard points *before* reading the plan, and keeps them out of every file the builder may open. The builder's plan must find them unaided. See `BUILDER-PROFILES.md`.

---

## 6 · Gate 1: the plan review

**Who:** the foreman. **When:** after "go", while work order 1 runs, finished **before** it reads the builder's plan. It first writes its **own scoping** (`templates/SCOPING.md`; the design forks settled, each with evidence and rejects) so it has its own answers before judging. For a light builder this scoping is the most important document in the job: every later work order's `D-` decisions come from it.
**Produces:** `GATE1-REVIEW.md` (`templates/GATE1-REVIEW.md`): the audition verdict (if any), then numbered findings G1..Gn, each with evidence and a disposition.
**In form A** there is no builder plan: gate 1 is **`/f-plancheck`** on the foreman's own plan (cold seats from other model families; it writes the `gate: plancheck` line), used under the f-plancheck discipline (§13), with its findings fixed before work order 2 (record the verdict in the job file).
**Then:** the next work order carries **the plan in force**, meaning the builder's plan with every accepted finding applied. The foreman's decisions go in; the builder's wrong ones go out.

---

## 7 · The build loop: one task per work order

**Work order size follows the builder's strength** (record it in the job file at work order 1):
- **Light builder (the default): one task per work order**, from `templates/WORK-ORDER.txt`.
- **Strong builder:** one work order may carry several tasks, still with one commit per task and every check per task.
Either way the foreman reviews every commit before gate 2, and keeps the job file current (below).

Each work order (`templates/WORK-ORDER.txt`):
1. opens with a **state check** pinning the worktree, branch and **exact HEAD SHA** (count and last subject as diagnostics), so it survives a stopped or compacted builder and a pipelined draft can't run on the wrong tree;
2. names the task, its files, and the **tests that must fail at the current head** (test-first);
3. carries the **hostile-input checklist** in every work order that writes or changes code (a database proof gets the database variant);
4. runs **the existing tests of every module it touches BEFORE the commit**;
5. makes **one commit**: subject only, staged by explicit path, never `git add -A`;
6. captures t<N> on every gate, serially, and compares against t0;
7. ends with **one report file and STOP**.

**After each work order, the foreman:**
1. **checks the disk first**: `git log`, the `.exit` files, the capture folders, the job file;
2. then reads the report;
3. **probes** the new code itself (a scratch script that feeds it hostile inputs, or mutation probes);
4. writes `JOB-<N>-WORK-ORDER-<m>-REVIEW.md` from `templates/WORK-ORDER-REVIEW.md` (findings R1..Rn, each reproduced);
5. puts the repairs, test-first, at the top of the next work order (PART A of `WORK-ORDER.txt`; a repair-only work order simply has no PART B);
6. **keeps the job file current** (in the records repo): the plan in force (gate-1 findings applied) under Phase 4, each task marked ✅ with its commit, and each review's findings linked. Before `/f-signoff` it fills Phases 5–7 (no phase is opt-in; QUICK records its lens inspection as `SKIP (QUICK)`), so `/f-signoff` finds every required phase ✅ and its drift audit compares against the plan that was actually built.

**Work order numbering:** work orders are numbered in order (1, 2, 3...). A correction to work order *m*'s own task, whether because it stopped or because its review found a gap in it, is `<m>b` (e.g. 8b, 12b), not a new number. New work gets the next number.

**Work order 2:** in form A (default) it's an ordinary `WORK-ORDER.txt` whose PART A copies the plan in force into the job file; in form B the builder plans from `templates/WORK-ORDER-2-PLAN.txt`.

**Mutation probes:** for each guard, a probe removes it and runs the tests. Only **BITES** (tests go red) passes. **A probe bites when its named test fails for any reason**, an assertion or an exception, so the harness reports the first error line, never only an assertion's tag (a test that raises under the mutation is a bite, not a wrong result). **Before sending a work order, the foreman checks every probe anchor still matches exactly once** in the tree as it will be after that work order's edits (an anchor broken by an edit makes a probe silently test nothing). **GREEN** (tests still pass without the guard) is a finding: the test doesn't test the guard. **Every work order carries the stop rule** (`templates/WORK-ORDER.txt` rule 7): on GREEN, the builder reports and STOPS, and never re-aims. Two builders in two jobs "fixed" a GREEN by re-aiming the probe, and both times it hid a missing test (in one, a well-shaped forged value was refused only by the guard, and no test covered it).

### 7b · The work order as it matured

Eight refinements that made a light builder reliable, plus four added later to cut the repair work orders (9–12). `templates/WORK-ORDER.txt` carries all of them.

| # | Refinement | What it looks like |
|---|---|---|
| 1 | **Decisions are labelled and final** | `D-D`, `D-E`, ...: each settled down to the exact expression or data shape. The work order says: *"Every design decision below is made. Do not change or extend any of them. If one cannot be built exactly as written, stop and say why."* |
| 2 | **Named test commands, defined once** | `NEW = <the full command for the new test file>`, `SUITE = the same over the whole folder`. The builder never assembles a pytest line itself |
| 3 | **A tighter reading fence** | "ANY file inside the worktree; nothing else in the records repo, apart from the one baseline file named." Hint-bearing notes stay out of reach |
| 4 | **The state check pins the exact HEAD sha** (plus worktree and branch; count and last subject as diagnostics) | a wrong, missing or extra commit is caught before any work starts |
| 5 | **The hostile-input checklist is per work order, numbered `H1..Hn`, and each item needs a test** | tailored to the task (for a database proof: isolation, never the shared port, can't pass for the wrong reason, no secrets in failure output). *"A repeat of a finding already warned about here ends this builder's run"*, which is the switch rule made visible to the builder |
| 6 | **Test-first with named tests that must fail at the current head**; "if any passes, stop: it does not test what it names" | when the code already exists (an acceptance proof), the builder first **breaks the assertion on purpose, shows it fails, restores it exactly**, then runs it for real |
| 7 | **The pre-commit comparison is a literal command** | `ran_ok` passes, then `diff <(failed_ids <baseline>) <(failed_ids <new output>)` is empty (the repo's test adapter, `templates/TEST-ADAPTERS.md`), or no commit |
| 8 | **The report sections are numbered and fixed** | the review can check them one by one |
| 9 | **A branch-coverage gate** (added later) | every uncovered line or branch in the new code gets a test or a reason the foreman gives (`WORK-ORDER.txt` B.2a) |
| 10 | **Probes per task** (added later) | each guard's mutation probe is written and run in the work order that adds the guard (B.2b) |
| 11 | **The standard gap checklist G1–G6** (added later) | cancellation, deadlines on every leg, fields reaching their destination, every error path mapped and tested, multi-item cases, local typed errors for bad input (B.2c) |
| 12 | **An "untested paths" report section** (added later) | the builder lists what it did NOT test; "none" only with an empty coverage table |

### 7c · The review after each work order (`JOB-<N>-WORK-ORDER-<m>-REVIEW.md`)

One review file per work order, `JOB-<N>-WORK-ORDER-<m>-REVIEW.md` (`templates/WORK-ORDER-REVIEW.md`):
- **Disk first**: the commit range, files touched per commit, subject lines, the capture counts, database roles restored, FAILED/ERROR lists against the previous capture.
- **Earlier findings re-probed** at the new head (each must now refuse).
- **The test-first claim verified independently**: the foreman runs the work order's new tests against the *previous* commit's code (the profile's old-code method, `templates/TEST-ADAPTERS.md`: in Python a scratch copy placed first on `PYTHONPATH`, elsewhere a throwaway worktree at the previous commit with only the new tests copied in) and confirms they fail there and pass at head. The builder's word is never enough.
- **Extra care on security code**: a paragraph per security-relevant path (credentials, identity, user context).
- **A switch-rule line every time**: "no security-class bug, no repeat of a warned finding: the builder continues", or the trigger that fired.

### 7d · Pipelining work orders

While the builder runs work order *m*, the foreman drafts work orders *m+1* and *m+2*. Each still opens with its own state check (the expected HEAD sha, re-pinned after the previous work order's review), so a drafted work order that no longer fits its starting state stops on its first step instead of building on the wrong base. The review of work order *m* can still change a drafted work order before it's sent.

### 7e · Delivery: hand-carried or pane link

- **Hand-carried** (the default): the owner pastes the one-line pointer into the builder.
- Earlier jobs also printed the work order's text in chat. **That's retired**: the chat window wraps long lines and broke paths. The pointer is the only hand-over.
- **Pane link**: when the builder runs in a terminal pane the foreman can reach (a pane-bridge tool; one is bundled, for a Pi builder in Orca: `skills/orca-pi-connect`), the foreman sends the one-line pointer itself and runs a **background watcher on the builder's stop signal**, so it's notified when the work order ends. The file header then reads *"Sent by the foreman as a one-line pointer."* Everything else is unchanged: the work order is still a file, the report is still a file, and the disk check still comes first. The owner keeps every word `RULES.md` reserves.
  - **Where the pane starts:** beside the foreman, in the **same tab** (split to the right), with the builder running **in the job's worktree** (§4). A split inherits the worktree of the pane it splits from (the foreman's checkout) and takes no worktree flag, so the startup command changes folder first: `orca terminal split --terminal <foreman's handle> --direction vertical --command "cd '<worktree>'; <builder start command>"` (on the Orca build this was proved on, `vertical` put the pane on the **right**, the opposite of Orca's own guide, so confirm with `orca terminal list --include-visual-layouts --json`; the handle is `$ORCA_TERMINAL_HANDLE` in the foreman's pane; `cd '<path>'; …` works in both PowerShell and bash). Don't use `orca terminal create --worktree`: that opens the builder in a **separate tab**. Then check the builder's own working directory in the first handshake (the READY line), not Orca's label: Orca still files the pane under the foreman's worktree. **Pi asks "Trust project folder?" in every new worktree**, which stalls an autonomous run on the owner's Enter: start it with `--approve` (`pi --approve --session-id <SID>`, Pi 1.0+), which trusts the project's own files for that run only. Use it only for a worktree of the owner's own repo; never for a folder someone else controls.
  - **If the builder hits a usage limit** (its subscription's limit, a provider's 429, a five-hour window): it often looks like an ordinary turn end, with no report and the work uncommitted. Read the pane. **Pause, never switch:** no paid seat, no other builder. Tell the owner in one line, "waiting for the builder's usage limit to reset (about <time, with its time zone> if the pane says)", and record it in the job file as environmental (not the switch rule). Wait in the foreground, repeated, each call under the tool's call limit: `node .claude/skills/orca-pi-connect/stop-watch.mjs --session <SID> --seen <n> --log <log> --timeout-seconds 540` (it also wakes you if the builder comes back early), reading the pane between calls. **A reset more than six hours away, or no reset time shown:** tell the owner and stop (a night shift counts that as stopped). A usage-limit pause does not count against the job's wall-time budget. When the builder is back, pin the work already done (its staged blob ids, or a commit) and send a `<m>b` that finishes only the remaining steps; a pane replaced while waiting gets a fresh handshake and pre-flight. **When the foreman's own session hits a limit,** it can't say or do anything: the host shows its limit notice and the turn ends. The run resumes when someone sends it one line after the reset: the owner, or in a night shift the shift boss (`skills/f-night-shift`). On that line the foreman reads its job file, checks the disk, and carries on from where it stopped.
  - **If the host kills the watcher** (a coding tool can reap background shells under memory pressure, and may say not to restart them): **don't restart it unasked**; say so in the reply. Fall back to a **foreground wait, repeated** (each call under the tool's call limit), e.g. `node .claude/skills/orca-pi-connect/stop-watch.mjs --session <SID> --seen <n> --log <log> --timeout-seconds 540`, reading the stop log before each wait. A stop log you can't read means the link is down: tell the owner and go hand-carried.

---

## 8 · Gate 2 and the end game

**Text the owner approves** (a document, a frame map, prompt or character text): the inspections run on the **draft**, before the owner's approval, never after it. The builder lands the draft; the lens inspection and the independent inspection (QUICK: the independent one only) read it; accepted findings change the draft; then the owner approves the inspected text **once**, and that text is landed byte-identical (copied, and the committed copy's hash checked). An earlier look by the owner is a preview, not the approval.

The end game. **Two inspections after gate 2** (STANDARD and FULL run both; QUICK runs only the second): the **lens inspection** (`/f-inspect`, run by the foreman in its own session with fresh reviewer agents) and the **independent inspection** (`/pack-review` → `/xreview` in a fresh session of a different model family → `/adjudicate`). Neither is skipped because an earlier one found nothing.

1. **Base-vs-head, first by the builder** (a work order of its own, `templates/BASE-VS-HEAD.txt`), two fixed runs:
   - run 1: every test module that imports a touched module, at base and at head. The set is *derived by a script*, not by grep (Python: `snippets/import_scan.py`; other stacks, or anything the scan can't see: the whole affected suite), because test modules also import each other. Failing tests are compared by **stable test IDs** through the repo's test adapter (`templates/TEST-ADAPTERS.md`), never by a summary line, and a run that collected nothing is a process failure, not a pass. Then a **widened** comparison over the whole affected suites;
   - run 2 (only where the repo has them): the tests that can't normally be collected (e.g. a platform-specific import), re-run with a stub, at base and at head.
   - **The Linux check when its container can't run** (the repo's Linux run, in the container its profile names; Docker down after a restart, say): never start, restart, stop or remove a shared container (`RULES.md`). CI on the PR is then the Linux check, recorded in the ledger as `Linux: CI on PR #<n>, run <id>` (until that run is green the row is PENDING, which blocks the merge, not the PR); the local run reproduces the CI runner's shape where the repo profile records it (**CI runner shape**, e.g. glib present, libEGL absent).
   - **The base worktree:** the last merged job's worktree if its tree equals `<remote>/<main>` at the branch point (the shift handover names it), otherwise one created by name at the branch-point sha (`templates/BASE-VS-HEAD.txt`).
   - Any **red-at-head-only** test means the builder STOPS and reports. The foreman **characterises** it (identical to base? isolated runs on head and base? passes in every earlier capture?) and never retries it to green. For example, a concurrency test that passes 8/8 in isolation on both sides is recorded as a characterised intermittent.
2. **Gate 2** (`templates/GATE2-REVIEW.md`): the foreman reviews every commit against its work order review, the final captures against t0, runs **its own** base-vs-head, and records the one safety fact.
3. **The lens inspection (`/f-inspect`)** (`templates/LENS-INSPECTION.md`):
   - the **foreman** runs `/f-inspect` over `base..final head` **in its own session** (no PR exists yet; the PR comes after both inspections), its specialist lenses spawned as **fresh subagents** with one shared brief (range, goal, constraints, settled decisions not to relitigate, findings only). The builder never reviews its own branch;
   - the foreman **checks every finding** (reproduces it against the code), accepts, rejects or partly accepts each, and records it (`templates/ADJUDICATION.md`). "Ship with follow-ups" becomes: fixed now, or rejected with a reason;
   - the foreman **sends back only what it accepted**, as test-first repair work orders; the builder fixes; the foreman reviews the fixes like any work order.
   The lenses are fresh, but they run in the foreman's session: **not counted as independent of the foreman.** That's the next step's job.
4. **The independent inspection** (`templates/PACK-REVIEW.md`, `templates/INDEPENDENT-INSPECTION.txt`):
   - the **foreman runs `/pack-review`** in its own session (it holds the goal, constraints and settled decisions): one review brief (goal, constraints verbatim, non-goals, the diff `base..final head`, absolute paths) in `<day folder>/blind-pack/`, with anything naming a model or vendor stripped;
   - the **foreman checks the brief** before it goes out (`PACK-REVIEW.md` §2): the right goal and constraints, the right range including every repair, the settled decisions listed as not to relitigate, nothing identifying the builder;
   - a **fresh session on a different model family** runs **`/xreview`** on it. If the foreman is Claude, the reviewer is **codex** (the codex CLI on the subscription, its latest model); if the foreman is codex, the reviewer is Claude. Never a session that has seen the work. The owner can carry it by hand, or the bundled `scripts/cross-review-dispatch.mjs --host <foreman's family>` automates it (headless, read-only, refuses without an independent seat), and an Orca pane running `codex` is the interactive alternative;
   - the foreman runs **`/adjudicate`** on the reviewer's output: every claim reproduced first, then ACCEPT / REJECT / PARTIAL / CANNOT VERIFY; accepted fixes go to the builder as a work order, or, in the converged case, are made by the foreman exactly as the reviewer specified. In one job its single claim was a real race that every earlier review had missed.
5. **Review of the fixes**: **nobody signs off their own repair**, with one exception: a fix the reviewer itself specified, implemented as specified, and proven in both states.
6. **After the last fix, everything re-runs at the final head**: all captures (t-final), the probe harness, and **both base-vs-head runs again** (red-at-head-only must be 0), first by the builder, then by the foreman. **The PR may open once the builder's final-head run is clean** (the ledger shows no FAIL, UNTESTED or INCONCLUSIVE row, and only the rows waiting on the foreman's own run as PENDING): the owner isn't kept waiting on a serial duplicate. **The merge waits for the foreman's own run** and an all-PASS ledger.
7. **The acceptance ledger** (`templates/ACCEPTANCE-LEDGER.md`, §10 step 0), then **the PR body**, which carries: what changed, limitations, the **rollback** (if the ticket asks for one), and a **review record** table (gate 1, task reviews, gate 2, the lens inspection or `SKIP (QUICK)`, the independent inspection, each with what it found). Template: `templates/PR-BODY.md`.

---

## 9 · The converged case

When the builder is done (or out of budget) and only review fixes remain, **the owner** may say "you take over". A converged-case fix that no reviewer specified is reviewed by the next independent round (the independent inspection, or a fix review in a separate session); the foreman never signs it off itself. **A security or concurrency repair**, even one a reviewer specified, also goes back to that same reviewer with the changed-since-review diff and the final SHA, for an acknowledgment before merge. The foreman then writes the fixes itself. **Nothing relaxes**: the tests of touched modules run before each commit, both base-vs-head runs run again, and the fixes get their own review.

---

## 10 · PR, merge, close

**In an autonomous run** (`RULES.md`, "The one exception"), the owner's `/goal` stands in for the words in steps 2, 2a and 3 and for the walkthrough; every check below still runs, and any stop condition there halts the run.

**Every build job takes this whole path, code or not** (`RULES.md` rule 13): documents, research and data deliverables go through the PR and the merge like code. Only a **decision** job skips steps 1–4: it is closed by the owner's recorded decision, then runs steps 5–9 the same way.

**While the end-game lock is open, read-only research for a candidate next ticket is allowed; the survey is not.** **The two locks** (`skills/f-signoff/endgame.mjs`): `/f-signoff` (step 5) first runs `verify-merge` and refuses a build job whose merge commit isn't on `<remote>/<main>`; after archiving it runs `open`, which writes `foreman/ENDGAME-PENDING.md`. Steps 6, 7, 7b and 8 and the shift handover (together with the next session's opener, §1; at a topping out the report, the topped-out board and the next heads instead, §11b) each `tick` their line with the file they wrote (the ground investigation its `JOB-<N>-GROUND-INVESTIGATION.md`; the decision must name the board version it chose from; the board step ticks the project's `BOARD.json`: no step can be skipped); the handover step then runs `clear`. While the lock exists, `/f-survey`, `/f-blueprint`, `/f-schedule`, `/f-shift` and work order 1 refuse to start.

**The live walkthrough** (when the ticket asks for one; run by the owner, or by the foreman when the owner delegates it or in an autonomous run):
- **Browser:** any browser tool that reaches the app's local address. If one refuses it (a browser extension blocked `127.0.0.1` once), use the pane host's own browser (`orca` browser eval and click).
- **Drive the page, never the keyboard.** Click, and set values through the page itself (its DOM, or its own API route). **Never send OS-level keystrokes** (`orca type`/`keypress`, desktop typing): they go to whatever has focus, and once typed into the foreman's own input. A check that needs a real keystroke is the owner's (owed) or done as a synthetic page event and recorded as one.
- **Before every turn**, check the app's server is alive (its health or state endpoint). If the host killed it, say so; don't restart it unasked.
- **Riskiest turns first.** Open with the turns most likely to cross the ticket's red lines (what the agent must never say or reveal), so a miss shows in the first minutes, not at turn 7. A red line crossed is repaired test-first (a test pinning the reply's shape where one can), then those turns are walked again.
- **Every turn, check faithfulness:** what was sent is what the script says, the reply is recorded from the page or the API as shown, and the job's safety fact is checked live (what the model can read holds nothing it must not). Records keep verdicts and short quotes, not whole transcripts.
- **After the walkthrough, any change to text the agent shows or reads** (a prompt, a fixed reply, a tool's description) gets a short live re-check, or a waiver line in the ledger saying why not.

0. **The acceptance ledger** (`templates/ACCEPTANCE-LEDGER.md`): every requirement and VP → PASS with evidence at the final reviewed head, its achieved mode, and the one safety fact proven by executing shipped code (or marked unproven). **Any FAIL, UNTESTED or INCONCLUSIVE row halts the PR; a PENDING row (the foreman's own final-head run still going, §8 step 6, or a Linux check that runs as CI on the PR, §8 step 1) halts only the merge.** A requirement dropped from scope, weakened or substituted needs the owner's quoted decision, recorded in the ledger's scope decisions (`RULES.md`, Evidence).
1. The foreman drafts the PR body (`templates/PR-BODY.md`) and **scans it for builder names**, and checks the job file has no blank left in the header and Phases 1-7 (`grep -n '<[^>]*>' <job file> | grep -v '`[^`]*<[^`]*`'`: a blank inside a code span is a command's own placeholder, not a blank; the JOB COMPLETE lines are `/f-signoff`'s own and stay blank until its Step 3.1), the risk table, the state summary, the VP table and the final head included; the PR and merge line is filled after the merge, at step 3. **If `<remote>/<main>` has advanced since the branch point**, re-run base-vs-head against current main (a merge preview) before asking to open the PR.
2. **Only on the owner's word** (e.g. "open the PR"): the foreman (or the builder, in a PR work order) pushes the feature branch and opens the PR with that body. **The owner watches it in the browser.** Opening it is not merging it.
2a. **The Greptile rounds** (`/f-greploop`, on the owner's word "greploop"): Greptile reviews the open PR and scores it out of 5; the foreman waits with the bundled `greptile-wait.mjs`, never a hand-rolled loop. Each round's findings are adjudicated like any inspection, accepted ones become the builder's test-first repair work orders, then the tests, both base-vs-head runs and the acceptance ledger re-run at the new head before the push (Greptile reads code; it never runs the tests). **At most three rounds, then it stops for the owner**, whatever the score. The pushed head becomes the final, reviewed head.
2b. **The PR description check (every job):** before asking for "merge", the foreman re-reads the PR body against the final diff and the final gate outputs, and rewrites anything stale: what changed (including any Greptile repairs), the proof at the final head, and the review record with each Greptile round's score.
3. **Merge only on the owner's word "merge".** The foreman performs it through the host (on GitHub: `gh pr merge <n> --merge --subject "<subject>" --body ""`, so the merge commit is subject-only too), or the owner clicks it. Then verify **the actual merge commit M** the host reports (never later main): `git fetch`; `git merge-base --is-ancestor M <remote>/<main>`; then **compare trees, not diffs or parents alone**: the delivered tree must be the tree that was reviewed and tested. Once it passes, **bring local main up to date at once** (`git merge <remote>/<main>`, never a rebase), so nothing reading the local checkout during the end game sees the job as unmerged; the records push still comes last.
   - **Expected tree** `E`: if the target didn't move after the final re-run (M's first parent is the branch point, or the base the final re-run was taken on), `E` = `git rev-parse <reviewed head>^{tree}`; if it moved, `E` = `git merge-tree --write-tree <M's first parent> <reviewed head>` (git ≥ 2.38), and that merge-preview tree must itself have passed the final re-run (re-run on a merge-preview worktree **before** saying "merge" when the target moved).
   - **Check:** `git rev-parse M^{tree}` = `E`. *Merge commit* also: `git rev-parse M^2` = reviewed head. *Squash*: M has one parent, the target. Record both shas and the tree ids.
   - A mismatch means the host delivered something that wasn't reviewed: STOP and tell the owner; don't close the job.
   - **Already merged** (the owner clicked merge on the host first, or `gh pr merge` says so): take M from `gh pr view <n> --json mergeCommit` and run the same checks. A merge commit with a body is then fine: the subject-only rule binds the foreman's own merges.
4. **Post-merge cleanup is the foreman's own, once step 3's tree check has passed:** with a pane link, first close the builder pane, not just Pi (`/f-signoff` checks it again, Step 1.1c) (`orca terminal close --terminal <builder handle> --json`, then check `orca terminal list` shows it gone: Pi runs inside the pane's shell, which outlives it); then delete the merged remote branch and remove the job's worktrees (job and base), without asking. A worktree removal that fails with "Device or resource busy" means a pane still has its shell there: close the builder pane and retry; never leave the folder. The **tracker transition** still needs the owner's word.
5. `/f-signoff`: completion (it **reads the acceptance ledger**: every row PASS, no deferrals, no close-anyway), **the job's Logbook cards** (§14), the planned-vs-built drift audit, the job archived by month. A job file records `Project`, `Job` and `SourcePlan` in its header, never `Blueprint`, so `/f-signoff` never retires a project's source plan.
6. A **dev report** for the day (`templates/DEV-REPORT.md`).
7. The **next-ticket decision**: the foreman reads the board and recommends the next ticket, with the rejected candidates and why (`templates/NEXT-TICKET-DECISION.md`); or says the board's head is reached (topping out, §11b); or, with work left but nothing eligible, says what waits on the owner and asks.
7a. **The owner confirms it, or picks another.** The foreman asks one question and writes the answer into the decision as `Owner confirmed: "<the owner's words>"` (a different pick rewrites the decision first). **Under a standing goal (`/goal`) there's no stop:** the foreman takes its own recommendation and writes `Owner confirmed: decided under the standing goal "<the goal's words>"`. **If the goal names the next job** (a planned night shift adds "next job is board <id>" for the end game), it takes that one instead, writes the decision for it, and records `Owner confirmed: named by the owner's night shift list "<the goal's words>"`; if that job isn't eligible on the board, it stops and says why. The end-game lock refuses the board and handover ticks until this line exists, so both are always written for the confirmed job.
7b. **The ground investigation: research the next job.** Once it is confirmed, before the board close and the handover, the foreman runs **four read-only research agents**, one per angle: **(1)** the domain's own community and docs, **(2)** how practitioners really do it, **(3)** what this repo's code already has to reuse, **(4)** the design of the answer or interface. On top of the four, the repo's **framework check** runs if its profile names one (a skill that checks the plan against the framework the product is built on). The foreman writes `<day folder>/JOB-<N>-GROUND-INVESTIGATION.md` from `templates/GROUND-INVESTIGATION.md`: where the sources agree, what the code gives and lacks, what the investigation settles (with evidence), the owner's questions with the evidence's pick starred, and what is unverified. The agents' full reports stay in `scratch/`. The handover and the opener point to it; the next survey starts from it and does not re-ask what it settles. It runs in every end game that has a next job, attended or autonomous, for any project: only the sources change. (No next job: either the board's head is reached and the end game tops the project out instead, §11b, or the rest wait on the owner and the end game asks the owner and waits.)
8. **Update the project board** (a topping out does this differently: §11b). One `f-board` **close** event (`render_board.py BOARD.json close <job> --pr … --merge <merge sha> --next <job>`): the job merged, the confirmed next job recorded, ready/blocked derived, **one** version, then republish to the same link (`skills/f-board`). Add any planned work the board doesn't hold yet (`add`, with its real `needs`), so the next choice has structure to read. Then the **shift handover** for the next job (§1). **No ticket exists yet for the next job** (an iteration board's next walk, say): first write `foreman/projects/<slug>/tickets/TICKET-<board id>-<slug>.md` from its board entry and the ground investigation (the `/f-schedule` ticket shape, `skills/f-schedule/templates/TICKET.md`), committed with the records; the handover transcribes that ticket. A repo in tracker mode gets the same keyless local ticket (the tracker issue is the owner's act 4).
9. Records are committed in the records repo by explicit path, with the commit rule restated at the moment of committing (subject line only, no trailer of any kind, records commits included; this rule wins over any tool's own attribution instruction), after the records-hygiene check (`RULES.md` rule 11) and **the names check over everything staged**: `node <skills>/f-signoff/names-check.mjs --names <names file> [--allow <allowed file>, when the profile names one] --staged` with the repo profile's git-ignored names file (exit 1 lists the hits; exit 2, a missing or empty names file, is not a pass); a hit is rewritten before the commit (the builder is never named). **After a verified merge the foreman pushes them itself:** merge `<remote>/<main>` into the records branch (never a rebase), check that only records differ, then push. That push also carries any **earlier records-only commits** already on the records branch (a decision recorded between jobs, a stopped job's records): before pushing, run the names check over every file they touch too (`names-check.mjs ... $(git diff --name-only <remote>/<main>...HEAD)`), and name them in the end-game report. **Any records commit left unpushed** (between jobs, or at a stop) is named in the same reply that made it, in one line: `<n> records commit(s) unpushed: say push, or the next merge's records push carries them.` **Then check CI on main** (`gh run list -R <target repo> -b <main> -L 1`): a red run is reported to the owner in one line (and in the topping out report at a topping out); never report green over it. The job ends there.

---

## 11 · The project board (an Ishikawa diagram of the product)

**What it is:** a living page, drawn as an **Ishikawa (fishbone) diagram**. The **head** is the product outcome everything serves (for example: *"checkout works end to end"*). Each **job** is one capability ticket that feeds it. Each build job is delivered by one recorded run (`J<n>`).

**Why:** the ticket board is a list; the board shows the *shape*. Which capabilities are merged, which are missing, and which job the next job should be, so the choice follows the product's structure, not the board's order.

**At every job close that continues the board (the foreman, after the owner confirms the next job; a topping out is §11b):**
1. One `close` event records the merged job (PR, merge commit) and the confirmed **next job**; the tool derives ready and blocked and bumps the version once (v15 → v16).
2. `add` any planned work the board doesn't hold yet, with its real `needs`.
3. Republish the page to the same link, so the owner's copy stays current.
4. The next-ticket decision names the version it read; the shift handover measures and cites the new one.

**Where it is:** `foreman/projects/<slug>/BOARD.json`, rendered to `board.html` beside it and published where the repo profile says. Each close bumps its version by one; the next-ticket decision names the version it read.

**Every project has a board.** The board is part of Topping Out, not an extra:
- **A project cut with `/f-schedule`** gets its board from the cut.
- **A project that wasn't** (tickets written one at a time, or a first ticket): start the board at the first job, before "go": `render_board.py <project>/BOARD.json init --title … --head "<outcome>" --test "…" --job <id> --job-title "…"`, then `add` the planned jobs with their real `needs`, and backfill jobs already merged with `add <id> --merged --pr … --merge <sha> --run …`. `/f-shift` stops until it exists.

The board is generated and maintained by `f-board` events (§13): **never edit the page or a job's state by hand.** (The old "hand-maintained board" and the end-game's free-text "n/a" are retired: together they let "no board" pass unnoticed. `init` plus backfill moves any older board into `BOARD.json`.)

**A thin board can't choose.** When the ready jobs tie on what they unblock and on partial work, only the project's order is left: the next-ticket decision says so, and the foreman adds the planned work that's missing.


**An iteration board** (`render_board.py <project>/BOARD.json init … --iteration`) is for work that doesn't start from one plan: testing a product, polishing how it feels, fixing what turns up. There is no blueprint up front; small jobs are added as they are found (`add`), each with its own ticket, and run as quick jobs, autonomous runs or night shifts. Its head is the outcome the iteration aims at ("the chat feels right to talk to"); it tops out like any board when the owner says it has arrived.

---

## 11b · Topping out: when a board reaches its head

A board **tops out** when its head is reached: **every job is merged or resolved**. It is the method's name for a reason: the last beam goes on, the structure is done, and the next one starts from it. A board with jobs left (ready, blocked, or waiting on an owner decision) tops out only on **the owner's own words** ("top it out, carry the rest"), never a goal's: under a goal the foreman stops and asks instead.

**A board with no next job for another reason** (the rest wait on an owner decision, or an iteration board has no job yet) doesn't top out: the next-ticket decision says so, and the foreman asks the owner to decide, add a job, or top out. The end game waits there; under a goal it stops.

At that end game the next-ticket decision says `Topping out: yes` and names no next job ("No next job: the head is reached", keeping its "board v<n>" citation). The end-game lock fixes that branch when the decision is ticked, and the same locked steps then take the topping-out files (`skills/f-signoff/endgame.mjs` checks them). **In this order:**
1. **Close the last job, then top the board out** (board events aren't locked): for an in-progress build job, `render_board.py <project>/BOARD.json close <job> --pr … --merge <M>` (add `--no-next --reason "topping out"` when jobs are left); for a decision job, `decided <job> --note "<the owner's decision, quoted>"`; a last job already merged or resolved needs no event; then `render_board.py <project>/BOARD.json topout --report <day folder>/TOPPING-OUT-REPORT.md --head yes|partly|no` (whether the head's test passes: required when jobs are carried over; with `--quote "<the owner's words>"` when jobs are carried over). The board is frozen as the project's record (no event runs after it; the page says "topped out"), and the jobs not merged or resolved are recorded as carried over. It is kept, never deleted.
2. **Write the topping out report** (`templates/TOPPING-OUT-REPORT.md`): `render_board.py <project>/BOARD.json report` prints its mechanical part (every job, its PR and merge, the carried jobs, the board's owed items word for word, whether the head was reached); the foreman adds, from the records (rule 16): what was built (every job, its PR, the totals), whether the head's test now passes, the three to five lessons worth carrying, and **everything carried over** (jobs not built, owed items carried across jobs, ruled-out ideas whose "revisit if" may now hold). Tick it in place of the ground investigation; then tick the board.
3. **Write the candidate next heads** (`templates/NEXT-HEADS.md`): three to five next projects, each with why now, where it comes from (a carried job, an owed item, a card, or a direction the owner has named) and its shape (a project with a blueprint, or an iteration board). Tick it in place of the handover; there is no opener.
4. **Any opener or handover already written for a next job on this board is superseded:** move it to `foreman/handovers/superseded/` (`/f-shift` and the night shift refuse an opener there). The lock clears and the records are pushed as always, with **CI on main checked** (`METHOD.md` §10 step 9): the topping out report never says green over a red main. The blueprint the board came from is archived now, on the owner's word (`skills/f-signoff`, the source plan).

**A late topping out** (the last end game already closed with "no next job, ask the owner", and the owner then says "top it out"): open a new end game for that same job (`endgame.mjs open --J<N>`), tick its existing dev report, write a `TOPPING-OUT-DECISION.md` that supersedes the earlier decision (`Topping out: yes`, the board citation, the owner's words), then follow the steps above and clear the lock.

**Then the cycle starts again, one level up.** The owner picks a head ("next head: 2") or names another, in a fresh foreman session. A project head goes through `/f-survey` → `/f-blueprint` → `/f-plancheck` → `/f-schedule`, which writes a **new board** in its own `foreman/projects/<new slug>/`; the foreman then writes the first job's opener from `templates/SESSION-OPENER-FIRST-JOB.txt` (the first job of a new board has no shift handover). An iteration head starts an iteration board with `init --iteration`; the foreman writes its first job's ticket and opener the same way. The product goes on through many boards, each one vision; the topped-out ones are its history.

Under a goal (an autonomous run, a night shift) the foreman tops out on its own only when every job is merged or resolved, and stops: choosing the next head is always the owner's.

---

## 12 · The shape: who does what

**One foreman plays every thinking role, and the builder plays only assembly.** The job file and its structure carry the record; the skills and agents below are the foreman's tools.

| Need | In Topping Out |
|---|---|
| Exploration | the site walk (§2) and the foreman's scoping (§6) |
| Requirements, design, tasks | **the foreman**, in `SCOPING.md` + `PLAN.md` (or, for an audition, the builder by plain steps) |
| Checking a plan | **`f-plancheck`**: a cold read from other model families, of the blueprint before `/f-schedule` (§13) and each job's `PLAN.md` at gate 1 (§6). `plan-validator` is only its checklist; never call it directly |
| Over-engineering check | `simplicity-critic` (optional), on the foreman's plan or a large project cut |
| Surveys, blueprints, status | `f-survey`, `f-blueprint`, `f-status` |
| Building | **the builder**, from work orders |
| Reviewing the branch | **`f-inspect`**, the lens inspection: the job's range, findings only, run by the foreman in its own session before any PR exists (§8 step 3). Once the PR is open, `/f-greploop` reviews it |
| Independent review | `pack-review`, `xreview`, `adjudicate` (§8 step 4): the foreman packs and adjudicates, a fresh session of another family runs `xreview` |
| Code quality | the foreman's **work order reviews** (§7c) plus the mechanical checks in every work order: probes, coverage gate, G1–G6. The review agents (`lens-code`, `lens-errors`, `lens-types` and the rest) run as **lenses** inside `/f-inspect`; the foreman adjudicates what they find |
| Questions to the owner mid-job | none: work orders carry settled decisions only |
| The record | the job file (`foreman/templates/JOB-*.md`: Phases 0–7 mapped to Topping Out artifacts, VP table, Key Discoveries). The foreman keeps it current (§7 step 6) and fills Phases 1–7 before `/f-signoff` |
| Lessons across jobs | the Logbook skills (`f-card`, `f-search`, `f-archive`, `f-archive-search`, `f-catchup`, `f-context`, `f-distill`, `f-dream`), set up from the first job (§14) |
| Closing a job | `f-signoff`: the acceptance ledger, no deferrals, the job header and the board close built in (§10) |
| Continuing in a new session | `handoff-builder` (§1) |

**Why this shape:** a light builder can't be trusted with design (an audition showed it), and every phase gate is one more place for it to guess. Moving all judgment to one session, and handing the builder only settled decisions and mechanical checks, is what let a cheap builder ship production code.

**Where the builder is a separate harness** (e.g. a Pi session): it can't spawn Claude Code's `.claude/agents` agents. Don't ask it to use them: the work order is the whole instruction. The agents run on the foreman's side.

---

## 13 · From a big plan to tickets: projects, jobs and `/f-schedule`

A job is always **one ticket**: one PR, one module area, roughly 8–9 work orders. A plan bigger than that is an **project**, and it's cut into tickets before any job starts.

```
/f-survey → /f-blueprint (the blueprint) → /f-plancheck (cold cross-family read) → /f-schedule (tickets + board) → pick a job
        → one job per ticket → /f-signoff → /f-board (mark merged, next job) → next job
        (repeat while a next job is confirmed; at the head, top out, §11b, and stop: only the owner picks a new head)
```

| Layer | What it is | Where it lives |
|---|---|---|
| **Plan** | `/f-blueprint`'s blueprint: the head, the decisions, the acceptance, the tasks; cold-read by `/f-plancheck`, which writes its `gate: plancheck` line | `foreman/blueprints/ready/` |
| **Project** | the plan cut into jobs, with the head it all feeds | `<records repo>/foreman/projects/<slug>/PROJECT.md` (the foreman's records: no product-repo PR for board updates) |
| **Ticket** | one job: its acceptance quoted verbatim, inherited decisions, needs, scope, record | `<records repo>/foreman/projects/<slug>/tickets/TICKET-<nn>-<slug>.md`, linked to an existing tracker key where there is one (never a minted key) |
| **Board** | the project's Ishikawa page, generated from data | `BOARD.json` → `board.html`, published to one link you follow |
| **Job** | the build of one ticket (this whole method) | the job file + day folders, as before |

**`/f-plancheck` comes first.** It seats 1–5 cold readers from model families other than the plan's author (codex, Grok…), runs them in parallel, merges their findings without voting, and writes the `gate: plancheck` line. `/f-schedule` refuses a plan without it.

### Plan check discipline (no loops, no drift)

A reviewer model is rewarded for finding things, so it always finds something. Loop it and each round nudges the plan further from what was decided. `/f-plancheck` is one pass and never edits the plan by design; these rules govern how its findings are used.

0. **Pre-read check (the foreman, before invoking `/f-plancheck`):** `grep -nE '^\*{0,2}gate: (plancheck|plan-read)' <plan>` (f-plancheck writes the line in bold: `**gate: plancheck**, …`) and look for an earlier read's scratch folder. A gate line or a prior read means this is a **second read**: stop and ask the owner (rule 1). For a job's `PLAN.md` (outside `foreman/blueprints/ready/`), **ask f-plancheck for the gate explicitly**, so it writes the `gate: plancheck` line into that file. With nobody at the seat picker (an unattended run, or under an autonomous goal), `/f-plancheck` picks seats with its unattended resolver (`plancheck-seat-resolve.mjs`), as the skill describes; say so in the job file.
1. **One plan check per plan.** A second read only if a finding forced a real design change, and only on the owner's word.
2. **Judge every finding against the locked decisions and the head.** A finding that reopens a settled decision is rejected with its reason, not debated.
3. **Only findings with evidence count:** a file:line, a failing scenario, a missing check. "Consider…", style and "could be cleaner" are dropped.
4. **Record each finding's fate** in the plan's findings table (applied / rejected, and why / answered). The original decisions stay above it unchanged, so the owner reads one table, not a rewritten plan.
   **The transfer step:** f-plancheck leaves its findings in its scratch output with the Disposition blank. The foreman copies each merged finding into the plan's table (the blueprint's `## Plan check findings`, `PLAN.md`'s, or `PROJECT.md`'s), with a link to the raw finding, then fills in the fate. Where a fate is "applied", the edit goes into the plan's body and the table row says what changed. The reviewer never edits the plan; `/f-schedule` checks the table has no blank fate.
5. **The foreman decides**, the same way it adjudicates an inspection. The owner is asked only when a finding would change the scope or a locked decision.

**The cutting rules** (`skills/f-schedule`):
1. One job = one ticket = one PR = one module area.
2. **Owner decisions are their own jobs** (state `decision`), never hidden inside a build job. Research that produces a file (a document, an audit, data) is a **build** job: it goes through a PR like code (`RULES.md` rule 13); only a question that ends in the owner's answer is a decision job. A build job that discovers it needs a decision stops, and the decision becomes a job.
3. Every verification point in the plan is carried by at least one job; every task maps to a job or to "not carried, on purpose".
4. Dependencies are explicit; a job is `ready` only when everything it needs is merged.
5. Acceptance is quoted, never reworded.

**Why:** a plan run as one job stalls as a whole on its hardest part. One early job halted with three buildable parts trapped behind two research halts. As jobs, the buildable parts proceed while the decisions wait visibly.

**The board is generated** (`skills/f-board/render_board.py`). The foreman records lifecycle **events**, one command each: `start` at "go", `close` (merged + next, one version), `halt`, `decided`, `add`. The tool derives ready/blocked from `needs`, bumps the version once, and re-renders; the page is republished to the same link. It refuses bad data and impossible events (starting a blocked job, closing a job that is not in progress, a merged job without its SHA, an ineligible `next`). **Never hand-edit the page or a job's state.** State lives only in `BOARD.json`, not in `PROJECT.md` or the ticket files.

**If scoping finds a job too big:** `/f-schedule --split`, recorded in the project. Don't stretch the job.

---

## 14 · The Logbook: context that outlives a job

A job's lessons shouldn't live only in its records. The **Logbook** (`foreman/logbook/`, the foreman's logbook) holds them as cards the next foreman searches. It's set up from the first job, not bolted on later.

| Card | Holds | Example |
|---|---|---|
| **INSIGHT** | a reusable gotcha or principle (why) | "a GREEN probe re-aimed hides a missing test" (it happened twice, with two builders: a card would have stopped the repeat) |
| **METHOD** | a repeatable procedure (how) | "verify a test-first claim by running the new tests on the previous commit" |
| **BUILD** | a compact record of what a job built | "job 12: the payment adapter: retries, idempotency key, timeout" |

**When it's used:**
- **`/f-shift`** (every job start) searches the Logbook for the job's area and lists the **cards in force** in its first reply. Past 250 live cards it runs **`/f-archive`** first (keeps 50 index cards).
- **`/f-card`**: one lesson, mid-job.
- **`/f-signoff`** writes the job's INSIGHT / METHOD / BUILD cards (evidence and provenance, no duplicates) and updates the index. A routine job may warrant none.
- **`/f-search`** / **`/f-archive-search`**: find cards. **`/f-context`**: a full cold orientation of a repo, with focus-matched cards.
- **`/f-catchup`**: once, to seed the Logbook from completed jobs that never got cards, or after a gap.
- **`/f-dream`** (now and then): merge duplicates, mark supersessions, find repeated mistakes; dry run first.
- **`/f-distill`** (now and then): promote the best cards into halt-shaped rules: product lessons into the repo's **constitution**, method lessons into Topping Out's `RULES.md` or playbooks. **Only on the owner's word.**

**Rules:** cards carry evidence and provenance; **a card never overrides `RULES.md`** (where one disagrees, the foreman says so); cards are the foreman's records, but promoting one into a rule needs the owner.

**Why:** the shift handover shouldn't carry every gotcha by hand (one ran to 897 lines), and the same mistake shouldn't happen twice.

---

## The owner's loop

```
foreman: "work order N ready: read <file>, lines A-B"
   └─> you paste that ONE LINE into the builder   (or, over a pane link, the foreman sends it)
builder finishes (report file written, STOP)
   └─> you tell the foreman: "work order N done"  (or its watcher sees the stop signal)
foreman: disk check → work order review → next work order (often already drafted)
```

**Watch for:**
- **A new pre-flight file** = the foreman is asking you to switch builders.
- **A standing goal** (`/goal`, "keep going until…") is never your word for an owner-only act (`RULES.md`), unless it says "autonomous run" (below). End it at "ready for your word", or it will keep prompting the foreman while the job waits on you.
- **"Needs your word"** = any of the acts listed in `RULES.md`. Nothing happens without it.
- **To let several jobs run one after another:** `/goal night shift: jobs <board id>, <board id>, until done or stopped` in a fresh session (`skills/f-night-shift`). Any stop ends the shift; the morning summary is `foreman/handovers/NIGHT-SHIFT-<date>.md`.
- **To let a job run to the merge without you:** in a fresh session, instead of pasting the opener, type `/goal autonomous run: <path to OPENER-JOB-<N>.txt>, until done or stopped` (add `, spend up to <n> USD (read, or a ceiling under it)` if the walkthrough needs a live key or a paid review seat; the builder's own bill never counts). It repairs what goes red and stops only on the conditions it lists; read `RULES.md` for exactly what it covers.
- **Every reply ends with a status block** (`templates/J-STATUS.md`). If you're lost, read that.
