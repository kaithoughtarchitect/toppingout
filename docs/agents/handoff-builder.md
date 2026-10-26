# handoff-builder

Write the handover notes so the next session can pick up the work.

Stage: Kit · Agents still in use
Source: `agents/handoff-builder.md`

## On site

Used at the end of every job that has a next job, from templates/HANDOFF-SESSION-BRIEF.md; the answers to its quiz go in a separate file. A topping out writes none.

## When to use it

At the end of every job that has a next job, to write the notes for the next session.

## It's working if

- Without a session brief it stops and lists the fields it needs, rather than writing a handoff from guesses.
- It writes exactly two files: the handoff, and a separate answer key the new session opens only after answering the questionnaire cold.
- The handoff states its mode (`MODE: full` or `MODE: quick`) and keeps pending approvals apart from approved ones.
- Every path and git fact in it was checked against the repo; where the brief and the repo disagree, the repo wins and the handoff says so.
- Its return report includes the final self-check block it passed, and the claims it corrected.
- It committed nothing and pushed nothing.

## Common questions

### What do I have to give it?

A session brief: the workstream, where the day ended, decisions made out loud, pending approvals, likely next asks, outward and database state, near-mistakes and key files. In Topping Out that is `templates/HANDOFF-SESSION-BRIEF.md` with `mode: full`.

### What is the difference between quick and full?

Quick is a thin pack, usually one or two screens, with 4 to 5 questions, for unblocking the next agent fast. Full is the thorough pack with 8 to 12 questions and a revision loop. A Topping Out shift handover is full, and a request that names no depth is treated as full.

### Where do the files go?

Where the caller names them. Otherwise the Topping Out convention applies: `foreman/handovers/`, as `AGENT-HANDOFF-<date>-job-<N>-<slug>.md` with `SITE-WALK-ANSWER-KEY-J<N>.md` beside it.

### Why does the next session answer questions before starting?

The questionnaire checks it is ready: the process rules, the current state, what is still pending, and a scenario deep into a session whose answer is the pre-action check. It answers in its own words, then opens the answer key and scores itself honestly.

### What if the handoff fails its own check?

Full mode revises up to three times; quick mode fixes once. If it still fails, no file is written and the report names the failing check.
