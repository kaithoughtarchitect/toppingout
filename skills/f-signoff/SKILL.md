---
name: f-signoff
description: >
  Close a merged Topping Out job (one ticket): check the acceptance
  ledger is all PASS, reconcile planned-vs-built, fill and archive the job
  file, then hand over to the board close. Use when the user runs /f-signoff, says
  "close this job", "we're done, wrap it up", after the merge is verified.
  No deferrals, no close-anyway, never retires the blueprint. Not for committing
  or pushing (the owner's word).
  Also answers to its old name, /f-close.
---

# Topping Out: Close

Close a merged Topping Out job: check the acceptance ledger, reconcile planned-vs-built, write the job's Logbook cards, and archive the job file to `foreman/completed-jobs/`.

**Git custody:** close never stages, commits, or pushes. The records commits and the records push belong to the end game (`METHOD.md` §10 steps 4-9), not to the close. File moves use plain filesystem moves; git detects the rename when the user commits.

**The contract:** Phases 1–2 are a **preflight that mutates nothing**; a refusal writes no file. Phases 3–4 run in a fixed **mutation order with checkpoints** recorded in the job file, so an interrupted close resumes from the first incomplete stage and never repeats a completed write. Close ends with one terminal line: `F-SIGNOFF: SIGNED OFF <archive path>` or `F-SIGNOFF: HALTED <specific reason>`.

**Deliberately not part of this close:** any engine- or service-side capture of the job (a repo that has one runs it as its own step, named in the repo profile), an unattended `--strict` runner with ack receipts (job closes run after a verified merge, attended or under an autonomous run; there is no separate unattended runner), and completed-plan retirement: **Topping Out never retires the blueprint at a job close** (Phase 4).

**Where it sits:** work orders → inspections → acceptance ledger → PR → Greptile rounds (≤3, if the profile has it) → PR description check → merge (verified) → **`/f-signoff`** → dev report → next-ticket decision → the owner confirms → next job: the ground investigation → `/f-board close` → shift handover and opener → the lock clears → records push. **At the board's head, the other branch:** close the last job → `topout` → the topping out report → the next heads, and no handover or opener (`METHOD.md` §11b).

---

## Usage

```
/f-signoff [job-name]
```

**No arguments**: Auto-finds job file in `foreman/jobs/` (errors if multiple found).

**With name**: Closes specific job (e.g., `/f-signoff login_rate_limit` finds `JOB_2026-06-04_*login_rate_limit*.md`).

---

## How It Works

### Phase 1: Find Job File

#### Step 1.1: Locate Job

```
foreman/jobs/JOB_*.md
```

**Rules**:

- If ONE job file exists → use it
- If MULTIPLE job files exist AND no name specified → list files and ask user to specify
- If name specified → find matching `JOB_*{name}*.md`
- If NO job files → error: "No active jobs found"
- **Older name:** jobs started before the setup template named the file may be `foreman/jobs/JOB-*.md`. If no `JOB_*.md` matches, look for those too; at archive (Phase 4) rename the file to `JOB_<YYYY-MM-DD>_<slug>.md`, taking the date from the job header's start date, and say so in the close report.

#### Step 1.1b: Lock 1, the merge (refuse before anything else)

A **build** job closes only after its PR is merged, whatever the deliverable's file type (`RULES.md` rule 13). Fetch, then run:

```bash
git -C <target repo> fetch <remote>
node <skills>/f-signoff/endgame.mjs verify-merge --repo <target repo> --merge <merge sha from the job file's PR and merge section> --main <remote>/<main>
```

Exit 1 (`ENDGAME_REFUSED`): **stop**. Say the job isn't merged and that the next step is the PR (`METHOD.md` §10 steps 1–3), never a close. No merge sha in the job file is the same refusal. A **decision** job (header `Kind: decision`) skips this check but needs the owner's decision quoted in the header; without it, stop.

#### Step 1.1c: The builder pane is closed (pane link only; refuse before anything else)

With a pane link (the repo profile's builder delivery), run `orca terminal list --include-visual-layouts --json` and find your own tab: **it must hold only your pane.** A builder pane still there (Pi, or the bare shell Pi leaves behind when it exits) is closed now by its handle (`orca terminal close --terminal <builder handle> --json`), then listed again. Don't close the job with it open: its shell sits in the job's worktree and keeps Windows from removing that folder ("Device or resource busy"). Record the close in the job file.

#### Step 1.2: Read Job File

Read the entire job file. **First list every unfilled placeholder** (`grep -n '<[^>]*>' <job file> | grep -v '`[^`]*<[^`]*`'`, ignoring the JOB COMPLETE section, which Step 3.1 replaces): each one is the first finding of the preflight, filled from the reviews before anything else. Then extract:

- **Title**: the job's `# Job <NN>, <title>` line
- **Lane**: QUICK / STANDARD / FULL
- **Phase Status table**: All phases and their completion status
- **Validation strategy**: `code-read | check | harness | UI` (the header line; older records: the State Summary block)
- **Requirements**: How many satisfied
- **Tasks**: How many completed
- **Verifications**: How many passed (if applicable)
- **Target repo, Base and Final head** (header) and the **Files changed** table (Phase 7)

#### Step 1.3: Count Lines of Code

Count lines added and removed for all files in this job. Use `git diff --numstat` to get per-file additions/deletions.

**Method:** use the job's pinned range, never a date search:

```bash
git -C <target repo> diff --numstat <base>..<final head>
```

Every path it lists must be in the record's **Files changed** table and vice versa; a difference is drift (Step 2.4). A record from before these fields existed: take the range from the PR's merge (`git -C <target repo> diff --numstat <merge>^1 <merge>`) and say so in the report.

**Calculate:**

```
Lines Added:   sum of all additions across job files
Lines Removed: sum of all deletions across job files
Net Change:    Lines Added - Lines Removed
```

**Include in close report as:**

```markdown
| Lines Added | +X |
| Lines Removed | -Y |
| Net Change | +/-Z |
```

**Notes:**

- The pinned range already limits the count to this job's commits; nothing else is counted.
- If the target repo isn't reachable, report "LOC not measured"; never estimate from file sizes.

---

### Phase 2: Validate Completion

#### Step 2.1: Check Phase Completion

Every lane uses the same phases 0–7 (`foreman/templates/JOB-STANDARD.md`, or `JOB-QUICK.md` for QUICK). Verify:

| Lane | Required |
| --- | --- |
| STANDARD, FULL | Phases 0–7 all ✅; both inspections have rows in Phase 6 |
| QUICK | Phases 0–7 all ✅; Phase 6's lens-inspection row says `SKIP (QUICK)` and the independent inspection has a row |

A job record from before the current phase numbering (classic phase numbering) is checked against its own Phase Status table.

**Harness jobs** (Validation Strategy = `harness`): Phase 7 verification is owned by the repo's measurement/eval harness (the repo profile names it). Confirm the **harness verdict + its run id** (whatever identifier the harness gives a run) are recorded in the job's Phase 7 (the acceptance ledger's achieved mode), that recorded verdict IS the verification. `/f-signoff` adds no capture step of its own; if the repo's harness needs one after a run, it is the harness's step, done before close.

#### Step 2.2: Check Metrics

Verify completion metrics:

```markdown
## Completion Check

| Metric        | Required     | Actual   | Status |
| ------------- | ------------ | -------- | ------ |
| Requirements  | 100%         | X/Y (Z%) | ✅/❌  |
| Tasks         | 100%         | X/Y (Z%) | ✅/❌  |
| Acceptance ledger | every row PASS | X/Y | ✅/❌  |
| All Phases    | Complete     | X/Y      | ✅/❌  |
```

**The acceptance ledger** (`templates/ACCEPTANCE-LEDGER.md`, written before the PR) is the completion record: every requirement and VP PASS at the final reviewed head, with its achieved mode and the one safety fact. **There is no percentage threshold and no deferral:** a row that isn't PASS blocks close. The only way to drop a requirement is the owner's quoted scope decision, recorded in the ledger.

#### Step 2.3: Completion Decision

| Status | Action |
| ------ | ------ |
| All ✅ | Proceed to Phase 3 |
| Any ❌ | **Stop.** Report exactly what is missing. There is no "close anyway": fix it, or the owner records a scope decision in the ledger |

#### Step 2.3b: Names kept out of records

An early pass, **report only** (this is the preflight: it writes nothing). Grep the job's records so far (the job file, the day folder's reports and reviews) for the names in the git-ignored names file the repo profile's **Names kept out of records** row names (default `scratch/names-kept-out.txt`): `node <skills>/f-signoff/names-check.mjs --names <names file> [--allow <allowed file>] <files>` (whole words, case-insensitive; never a grep line: Git Bash's grep aborts on `-i` with several patterns and prints nothing). Each hit, including inside a quoted error message, goes into the drift table as a correction for the `drift_corrections` stage ("the builder's provider", "the review tool"). **No names file:** create it before the close, from the builders the repo profile and `BUILDER-PROFILES.md` name (git-ignored, one name per line), and say so in the close report. **No allowed file** while the profile names one: create it empty (git-ignored) beside the names file. The full check runs again at the records push, over everything staged (`METHOD.md` §10 step 9).

#### Step 2.4: Spec-Drift Audit (planned-vs-built)

Before closing, reconcile the job file against what actually shipped, jobs rot at exactly this moment, and close is when context is freshest. Diff the job's task list + VP table + "Files Changed" section against `git log` / `git diff` for the job's commits (and the working tree). Produce the two-column table:

| Planned but NOT built                     | Built but NOT planned                           |
| ----------------------------------------- | ----------------------------------------------- |
| <task/VP/type with no corresponding code> | <shipped file/function absent from the job> |

**Drift that came from an accepted, merged repair** (a finding from the lens inspection, the independent inspection, Greptile or the walkthrough, adjudicated as accepted, repaired, reviewed and in the merged tree): the foreman resolves it itself as **update-job**, naming the finding it came from (e.g. "Greptile G1-1, repaired in `<sha>`"); the owner already saw it merged. Only drift with **no finding or decision behind it** goes to the owner. **Drift that only moves tests** (a new test file instead of an edit to an old one, a test in another module) with no change to behaviour or coverage: the foreman resolves it itself as accept-drift and records why; it never goes to the owner. For each other row the owner resolves: **update-job** (record reality) / **accept-drift** (note + close) / **rule-out** (the planned item was deliberately killed, not deferred: if it could plausibly come back, a **ruled-out** card, an INSIGHT tagged `ruled-out` titled "Ruled out: <item>" with **Why** and **Revisit if**, so `/f-survey` and `/f-search` surface it before anyone proposes it again cold; if it couldn't, just note it in the job file). An empty table is the normal outcome for a disciplined job. **This step only proposes:** the table, each resolution and the exact corrections are held for the `drift_corrections` stage below; nothing is written yet.

**update-job executor** (in the `drift_corrections` stage, not now): for more than a line or two of corrections, the `spec-validator-fixer` agent scoped to the job file ONLY validates each claim against the code and fixes it in place; trivial single-line corrections are hand-edited.

#### Step 2.5: No deferrals

Follow-ups and deferred VPs are not a practice here. Anything the drift audit (Step 2.4) finds is fixed before close or rejected with a recorded reason; nothing is parked in a stub.

---

### Mutation order (checkpoints)

Only after every Phase 1–2 check passes, and the drift resolutions and card list are agreed, write this block into the job file first. It lists the one real order. Each stage is set `pending` (with its targets) before its first write, and `complete` only after every target is verified. Several stages write the same file (the job file, the index and links), so each target keeps **one current hash**, updated by whichever stage wrote it last; a stage's own line keeps the hashes it produced, as its receipt:

```text
## Close Mutation Checkpoints
- drift_corrections: pending|complete|skipped   targets: <job file; each ruled-out card; logbook_index.md; logbook_links.md>  sha256: <per target>
- finalization: pending|complete                 targets: <job file JOB COMPLETE section>        sha256: <job file after>
- logbook_cards: pending|complete|skipped        targets: <each card path>                        sha256: <per card>
- logbook_index_links: pending|complete|skipped  targets: logbook_index.md, logbook_links.md       sha256: <per file>
- board_record: pending|complete|skipped         target: <the project's BOARD.json>               sha256: <file after>
- archive: pending|complete                      target: foreman/completed-jobs/YYYY-MM/JOB_<date>_<slug>.md
- current: <one line per target: path  sha256>   (the latest verified hash of every file written so far)
```

- **How a job-file hash is taken** (`node <skills>/f-signoff/endgame.mjs hash <job file>` does exactly this): remove the `## Close Mutation Checkpoints` block (from its heading up to the next `## ` heading, or the end), because that block changes at every stage transition; then convert CRLF to LF and collapse every run of blank lines to one, so reformatting the block never changes the hash. Trailing newlines and whitespace-only lines count as written. Every other target is hashed whole, as written (plain sha256, not this command).
- `skipped`: nothing to write for that stage (no drift, no card warranted); say so in the close report.
- **Before the archive stage:** if the `archive_target` already exists and isn't this job file (same bytes, or an earlier attempt of this close with the same checkpoint block), **refuse**: `F-SIGNOFF: HALTED archive target exists`. Never overwrite it.
- **On a retry**, read the block; re-hash every target listed under `current` against its **current** hash (a later stage legitimately changes a file an earlier stage wrote, so an earlier stage's receipt is history, not the check); skip verified stages and resume from the first `pending` one, re-checking its targets before writing. A mismatch, a missing target or a partial write you can't verify: **stop** and report every stage's state and hashes. Never roll forward silently and never repeat a completed write.

**Stage by stage:** `drift_corrections` applies Step 2.4's resolutions (job file corrections, and each ruled-out card through `/f-card`'s steps, index included) and re-validates the job file; `finalization` is Phase 3 Steps 3.1, 3.3 and 3.4; `logbook_cards` and `logbook_index_links` are Step 3.2; `board_record` is Step 3.2b (never skipped: every project has a board); `archive` is Phase 4.

### Phase 3: Update Job File

#### Step 3.1: Update Status Section

Find the "JOB COMPLETE" section (older records: "COMMISSION COMPLETE") and **replace its lines** with these (one line per field, never a second copy of one):

```markdown
## JOB COMPLETE

**Status:** ✅ COMPLETE
**Closed:** YYYY-MM-DD HH:MM
**Requirements Satisfied:** X/X
**Tasks Completed:** X/X
**Verifications Passed:** X/X
**Duration:** <started → closed>
**Lines of Code:** +X added, -Y removed (net +/-Z)
```

There is no incomplete close: `/f-signoff` runs only after the merge, and the merge only after every acceptance-ledger row is PASS. A job that can't finish is HALTed on the board (`f-board halt`), not closed.

#### Step 3.2: Write the job's Logbook cards

Compare the job's discoveries (the job file's Key Discoveries, the work-order reviews, the inspections, the dev report's learnings) with existing cards (`/f-search`), then write only durable, evidence-backed cards:

- **INSIGHT** for a reusable gotcha or principle (e.g. "a GREEN probe re-aimed hides a missing test");
- **METHOD** for a repeatable procedure;
- **BUILD** for a compact record of what the job built.

**First compute the job file's final path** (Phase 4: `foreman/completed-jobs/<YYYY-MM>/JOB_<date>_<slug>.md`) and use *that* as every card's `job:`, so no card points at `foreman/jobs/`. Use the templates in `foreman/logbook/entries/*/`, set `job:` and the evidence, avoid duplicates (refine an existing card instead), and update `logbook_index.md` and `logbook_links.md` in the same pass, as `/f-card` Step 9 does (counts recounted from the files). A routine job may warrant no cards: say so. Cards are the foreman's records (no owner word needed); promoting a card into rules is `/f-distill`, which needs it.

#### Step 3.2b: The board's record of this job

Give the job's entry in the project's `BOARD.json` (the same text edit the board allows) up to three `twigs` (short lines from the key discoveries), its `figures` (the few numbers that matter, with a label and `good` / `warn`), and its `lesson` (one paragraph, the same lesson its Logbook card carries). Update `project.owed`, and `project.alerts` / `project.facts` if they changed. The board's **close** event then renders them (`skills/f-board`, "The page").

**Board text is plain prose with no em dashes (, ).** Everything written into `BOARD.json` shows on the page, so use a comma, a colon or a full stop instead. This covers twigs, figure labels, the lesson, notes, `owed`, `alerts` and `facts`.

#### Step 3.3: Ensure Key Discovery Section

If bugs were found or important discoveries made, ensure there's a "Key Discovery" or "Learnings" section preserved in the job file before it is archived. The job file keeps the full story; the Logbook cards (Step 3.2) carry the parts worth reusing.

#### Step 3.4: Team Knowledge (optional, propose-only)

If the job surfaced a durable team-relevant fact (a stakeholder ask, a dependency on another engineer, a priority, a shift handover constraint), **propose** a one-line edit to the repo's constitution (the repo profile names it: `AGENTS.md` or `CLAUDE.md`) and wait for the owner's word; never auto-write. If nothing durable surfaced, skip silently.

---

### Phase 4: Archive Job

Check the `archive_target` (refuse if a different file is there), set `archive: pending`, then **copy** the job file to the `archive_target`, verify the copy is byte-identical, set `archive: complete` in both copies, verify they're identical again, and only then delete the file in `foreman/jobs/`. A crash between the copy and the delete leaves two identical files; the retry sees `archive: complete` and finishes the delete. A crash between the two checkpoint edits leaves copies that differ only in that line: the retry halts and reports it (a safe refusal, fixed by hand), never guesses.

From `foreman/jobs/` to a month-based subfolder of `foreman/completed-jobs/`:

```
foreman/jobs/JOB_2026-06-04_login-rate-limit.md
    → foreman/completed-jobs/2026-06/JOB_2026-06-04_login-rate-limit.md
```

**Convention:** completed jobs are foldered **by month**, `foreman/completed-jobs/YYYY-MM/`, the same month-foldering the day folders use. Use the `YYYY-MM` from the job's own `JOB_YYYY-MM-DD_*` filename for the subfolder (create it if missing). **No `COMPLETED_` rename**, the move into `completed-jobs/` is itself the "closed" signal. Plain filesystem operations only (this skill never runs mutating git; git detects the rename at the user's commit).

#### Then: open the end-game lock

Once the archive is `complete`, run `node <skills>/f-signoff/endgame.mjs open --job <NN> --root <records root>`. It writes `foreman/ENDGAME-PENDING.md`; nothing new starts until the end-game clears it.

#### The blueprint is never retired here

A Topping Out job is one job of a project. Its header carries `Project`, `J-number`, `Board` and `SourcePlan` (older job files: `Job` and `Run`), never `Blueprint`. **Never delete or retire the source plan at a job close.** The blueprint is archived after its board tops out (`METHOD.md` §11b, including an owner-approved topping out with carried jobs), and only on the owner's word; the carried work lives on in the topping out report.

#### Then: the board

Hand over to `/f-board`'s **close** event (`render_board.py BOARD.json close <job> --pr … --merge <merge sha> --next <job>`), after the next-ticket decision; at the board's head, `close … --no-next --reason "topping out"` then `topout` (`METHOD.md` §11b).

---

### Phase 5: Generate Close Report

Output summary to user:

```markdown
# Job Closed

**J-number:** [J<n>, title] · **Board:** [NN]
**Lane:** [lane]
**Validation Strategy:** [code-read | check | harness | UI]

## Final Metrics

| Metric        | Result     |
| ------------- | ---------- |
| Requirements  | X/X (100%) |
| Tasks         | X/X (100%) |
| Verifications | X/X (100%) |
| Bug Fixes     | X          |
| Lines Added   | +X         |
| Lines Removed | -Y         |
| Net Change    | +/-Z       |

## Spec-Drift Audit

_(From Step 2.4)_

[Two-column table, or "No drift, job matched what shipped"]

## Delivered

- [feature 1]
- [feature 2]

## Key Files

- `path/to/file1.ts`
- `path/to/file2.tsx`

## Archive Location

`foreman/completed-jobs/YYYY-MM/JOB_YYYY-MM-DD_[name].md`

---

_Job closed and archived._

F-SIGNOFF: SIGNED OFF foreman/completed-jobs/YYYY-MM/JOB_YYYY-MM-DD_[name].md
```

A refusal ends instead with `F-SIGNOFF: HALTED <what is missing>` and writes nothing (Phases 1–2), or lists every checkpoint's state (Phases 3–4).

---

## Error Handling

| Error                              | Response                                                              |
| ---------------------------------- | --------------------------------------------------------------------- |
| No job files found             | "No active jobs in foreman/jobs/. Nothing to close."       |
| Multiple jobs, no name         | List files: "Multiple jobs found. Specify which: /f-signoff [name]" |
| Job not found by name          | "No job matching '[name]' found in foreman/jobs/"          |
| completed-jobs folder missing  | Create it automatically                                               |
| Job already under completed-jobs/ | "Job already closed: [filename]"                           |

---

## Workflow

```
merge verified (METHOD §10 step 3)
        ↓
/f-signoff                    ← YOU ARE HERE
        │
        ├─ Preflight, writes nothing: find the job file, LOC over the pinned range,
        │  the acceptance ledger (every row PASS), the drift audit and card list (proposed)
        ├─ Checkpoint block written, then in order:
        │    drift_corrections → finalization → logbook_cards → logbook_index_links → board_record → archive
        │  (each stage pending → written → verified by hash → complete; the blueprint is never retired)
        └─ Output the close report, ending F-SIGNOFF: SIGNED OFF <archive path>
        ↓
dev report → next-ticket decision → owner confirms → ground investigation → /f-board close → handover + opener → lock clears → records push
  (at the board's head: close → topout → topping out report → next heads → lock clears → records push → stop)
```

**End the close report with the end-game checklist, verbatim, so the next steps are read, not remembered:**

```
END-GAME OWED for job <NN> (foreman/ENDGAME-PENDING.md), in this order:
1. dev report            -> endgame.mjs tick dev-report --file <path>
2. next-ticket decision  -> endgame.mjs tick next-ticket-decision --file <path>
   then the owner confirms (or, under a /goal, the foreman records the goal): the file's
   "Owner confirmed:" line must be filled before step 2b
2b. ground investigation -> endgame.mjs tick ground-investigation --file <day folder>/JOB-<next>-GROUND-INVESTIGATION.md
   (METHOD.md §10 step 7b: four read-only research agents, one per angle, plus the profile's framework check;
   the handover and the opener point to it)
3. board close event     -> endgame.mjs tick board --file <project>/BOARD.json   (every project has one; none yet: render_board.py … init)
4. shift handover + opener -> endgame.mjs tick handover --file <handover> --opener foreman/handovers/OPENER-JOB-<next>.txt, then endgame.mjs clear
   (then give the owner the opener's path and **three ways to start the next job, each ready to paste**:
    normal: paste the opener's text into a fresh session;
    autonomous run: /goal autonomous run: <absolute opener path>, until done or stopped;
    night shift: /goal night shift: jobs <next board id>, <the one after, from the board>, until done or stopped;
    adding ", spend up to <n> USD (read, or a ceiling under it)" to the last two when the next job has a paid seat or a live-key walkthrough, and
    listing the questions its survey will answer itself under a goal (its ground investigation's starred picks))
5. records push         -> names check over everything staged (names-check.mjs --staged, METHOD.md §10 step 9; a hit is rewritten first), merge <remote>/<main> into
                           the records branch (never a rebase), check only records differ, push; then check CI on main
                           (gh run list -R <target repo> -b <main> -L 1): red is reported, never called green

TOPPING OUT (the decision says "Topping out: yes": every job merged or resolved, or the owner's words; METHOD.md §11b):
    first the board events (not locked): an in-progress build job: close <job> --pr ... --merge <M> [--no-next --reason "topping out"];
    a decision job: decided <job> --note "<the owner's decision>"; already merged or resolved: nothing; then
    render_board.py <project>/BOARD.json topout --report <day folder>/TOPPING-OUT-REPORT.md [--quote "<the owner's words>"]
2b. topping out report  -> write it from the topped-out board's check output, then
                           endgame.mjs tick ground-investigation --file <day folder>/TOPPING-OUT-REPORT.md
3.  board               -> endgame.mjs tick board --file <project>/BOARD.json   (must be topped out)
4.  next heads          -> endgame.mjs tick handover --file <day folder>/NEXT-HEADS.md (no opener), then endgame.mjs clear
    (then tell the owner the project topped out, and give the candidate heads, the evidence's pick first, with how each starts)
```

---

_Close the job, archive the work._
