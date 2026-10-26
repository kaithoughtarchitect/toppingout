# f-signoff

Close a merged job: check every requirement passed, save the lessons, file the job away.

Command: `/f-signoff` (old name `/f-close`)

Stage: Merge, close and Logbook · Close · step 11 of 11 in the order of works (Close)
Source: `skills/f-signoff/SKILL.md`

## On site

After the merge: closes the job only when every requirement has passed, with nothing put off for later. Then come the dev report, the choice of the next job, the board update and the handover, in that order. At the board's head it tops the project out instead: a topping out report, the frozen board, and candidate next heads for you to pick from.

## Say it

- "close this job"
- "we're done, wrap it up"

## When to use it

Right after a job's pull request is merged and the merge is confirmed.

## Not for

Committing or pushing (the owner's word).

## It's working if

- On a build job that isn't merged, it refuses and points to the PR instead.
- Every row of the acceptance ledger is PASS. A row that isn't stops the close: there is no "close anyway".
- It shows a drift audit, planned but not built against built but not planned. An empty table is the normal result.
- The job file has moved to `foreman/completed-jobs/<YYYY-MM>/` and is gone from `foreman/jobs/`.
- The last line reads `F-SIGNOFF: SIGNED OFF <archive path>`, followed by the end-game checklist.
- It staged, committed and pushed nothing, and the blueprint is untouched.

## How every close ends

The close report ends with this checklist, exactly as the skill prints it, so the next steps are read, not remembered.

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

## Common questions

### Can I close a job that isn't quite finished?

No. Finish it, or record your own scope decision in the acceptance ledger. A job that can't finish is halted on the board, not closed.

### What if the close is interrupted halfway?

Each stage is recorded in the job file with the hash of what it wrote. A retry resumes from the first unfinished stage and never repeats a completed write. If a file doesn't match its recorded hash, it stops and reports every stage's state.

### Does it commit or push?

No. File moves are plain moves; you commit them when you choose.

### Why doesn't it retire the blueprint?

A job builds one ticket of a project. The blueprint is archived only after its board tops out, and only on your word. If you top out with jobs carried over, the carried work lives on in the topping out report.

### What comes after it?

The dev report, then the next-ticket decision, which you confirm. Then the board's close event, and the shift handover with the next session's opener beside it (`foreman/handovers/OPENER-JOB-<N>.txt`, which you get to paste). Nothing new starts until those are done; then the records are pushed.

### What happens at the board's head?

The last job closes with no next job, the board tops out (`topout`), and in place of the handover you get a topping out report and three to five candidate next heads. There is no opener: you pick the next head when you're ready.

### It used to be called something else?

Yes: `/f-close` still works.

## Connections

- Leads to: f-board, f-night-shift
- Uses: spec-validator-fixer
- Used by: f-setup
