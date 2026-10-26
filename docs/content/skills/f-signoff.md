---
sample: Workflow | 2
sample_title: How every close ends
sample_note: The close report ends with this checklist, exactly as the skill prints it, so the next steps are read, not remembered.
---

## It's working if

- On a build job that isn't merged, it refuses and points to the PR instead.
- Every row of the acceptance ledger is PASS. A row that isn't stops the close: there is no "close anyway".
- It shows a drift audit, planned but not built against built but not planned. An empty table is the normal result.
- The job file has moved to `foreman/completed-jobs/<YYYY-MM>/` and is gone from `foreman/jobs/`.
- The last line reads `F-SIGNOFF: SIGNED OFF <archive path>`, followed by the end-game checklist.
- It staged, committed and pushed nothing, and the blueprint is untouched.

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
