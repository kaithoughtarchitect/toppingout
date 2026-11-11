# f-dream

Look back over past jobs: merge repeated lessons and spot mistakes that keep happening.

Command: `/f-dream`

Stage: Merge, close and Logbook · The Logbook
Source: `skills/f-dream/SKILL.md`

## On site

The Logbook: automatically every 10th close, applying only merges and supersessions its guards allow and leaving the rest for you; or by hand any time, dry run first. Every change can be undone, and it never removes a card marked critical.

## Say it

- "reflect across the jobs"
- "are we repeating mistakes"
- "clean up contradictions in the logbook"

## When to use it

Automatically every 10th close, with guards; by hand any time.

## Not for

Reconciles content: not for promoting knowledge upward (f-distill), nor for rotating by count (f-archive).

## It's working if

- By default it reads the last ten completed jobs and returns a numbered proposal, writing nothing.
- Each proposed change cites its evidence, its target cards, the relationship changes, a confidence and a rollback.
- The proposal holds at most 10 changes and never retires a CRITICAL card on its own.
- The output gives the proposal ID, the corpus size, merges, supersessions, new patterns and anything skipped or flagged.
- When applied, each retired card is copied and the copy checked before the live copy is removed, and an applied manifest can reverse every change.
- It staged, committed and pushed nothing.

## Common questions

### Does a plain run change anything?

No. The default is a dry run. It suggests a path for the proposal, but saves it only with `--save-proposal` and your explicit write authority.

### How do I apply a proposal?

Run `--apply --proposal <id>` with the saved proposal's id. It applies only the accepted items, and there is no "most recent" default.

### What does it treat as a duplicate or a contradiction?

It checks every candidate against its source. The same lesson in different contexts is not a duplicate, and advice that depends on context is not a contradiction.

### Can I choose which jobs it reads?

Yes: `--since` and `--jobs` bound the set.

### When does it stop partway?

On an unclear card identity, missing provenance, a copy that fails its check, or links that don't add up.

### How is it different from `/f-archive`?

`/f-archive` rotates cards out by count and judges nothing. This reads the content and reconciles it.
