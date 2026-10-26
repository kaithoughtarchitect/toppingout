# TICKET-<nn>: <title>

**Project:** `<project-slug>` · **Board:** <nn> · **Tracker key:** <an existing key, or "none (this file is the ticket)"> · **State:** see `BOARD.json` / the board page (never kept here)
**Needs:** <job ids that must be merged first, or "none"> · **Unblocks:** <job ids>

## Why this job
<What it makes possible for the head, in two or three sentences.>

## Acceptance (verbatim from the project's plan)
- <VPn, or the part of it this job carries, quoted exactly>
- <the negative controls it must pass, quoted exactly>

## Inherited decisions
<D-ids from the project that bind this ticket, each with its one-line text. The job's scoping may not reopen them.>

## Scope
**In:** <the module area and files it owns>.
**Out:** <what neighbouring jobs own, with their ids>.

## Starting point (measured, with the commands)
<What the repository already holds for this job: files, partial work, tests. Updated whenever the ticket is picked.>

## Size check
One PR, one module area, roughly 8–9 work orders at most. If scoping shows it's bigger, split the job (`/f-schedule --split <project> <nn>`) rather than stretching the job.

## For a decision job only
**To decide:** <the question>. **Owner:** <who>. **Options and evidence:** <each option, what it costs, what it unblocks>. **Until decided:** <what stays visibly unavailable>.

## Record (filled at close)
Job: <J-number, archived job file> · PR: <#n> · Merge: <sha> · Verified: `M^{tree}` `<tree>` = the reviewed / merge-preview tree `<tree>` (`METHOD.md` §10 step 3)
