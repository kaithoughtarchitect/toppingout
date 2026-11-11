---
name: f-dream
description: >
  Reflect across completed jobs and the Logbook to propose verified
  deduplication, supersession, and recurring-pattern updates. Use for
  /f-dream, "reflect across the jobs", "are we repeating mistakes",
  "clean up contradictions in the logbook", or when entries may contradict
  or repeat. Reconciles content: not for promoting knowledge upward
  (f-distill), nor for rotating by count (f-archive).
---

# Topping Out: Logbook dream

Default is a read-only dry run over the last ten completed jobs (`foreman/completed-jobs/*/JOB_*.md`). `--since` and `--jobs` bound the corpus. `--save-proposal <id>` requires explicit write authority. `--apply --proposal <id>` applies that saved proposal only, no most-recent default.

## Automatic mode (from `/f-signoff` Step 3.2c only)

The close is the mutation authority, for this one proposal. Run the dry run over the jobs since the last dream line in `foreman/logbook/upkeep.md`, save it (`--save-proposal <date>-J<n>`), then apply **only** the items that pass every guard:
- a **merge** of two cards with the same lesson in the same context, or a **supersession** where the newer card cites the evidence that overturns the older one, at the proposal's highest confidence;
- **never** a CRITICAL card, a contradiction that needs judgement, or an item whose provenance can't be verified: those stay in the saved proposal, listed for the owner;
- a new recurring-pattern card only with three or more cited jobs.
The Apply steps below run unchanged (copy, verify, update, verify, then remove the active copy, with a manifest that reverses every change), so nothing is ever lost: a retired card sits in the proposal's retired area. Report the proposal id and every change for the dev report. Never stage, commit or push; the close's records commit carries it.

## Dry-run

1. Read the selected jobs, active cards, Logbook index, relationships, and earlier dream proposals.
2. Root does three non-mutating passes with fresh notes: duplication, contradiction/supersession, recurring mistakes. Do not dispatch unnamed roles. Do not apply during these passes.
3. Verify every candidate against its cited source. Same lesson in different contexts is not a duplicate. Context-dependent advice is not a contradiction.
4. Numbered proposal: evidence, target cards, relationship changes, proposed bodies, confidence, rollback, unresolved. Cap 10 changes. Never auto-retire CRITICAL.
5. Return the proposal and suggested `foreman/logbook/archived/dreams/<id>/` path. Dry-run writes nothing. Persist only via `--save-proposal`.

## Apply

Existing proposal + explicit mutation authority. Accepted items only. Retire/merge/supersede:

1. copy original to the proposal's retired area
2. verify the copy
3. update canonical content and relationships
4. verify references and index
5. only then remove the retired active copy

Stop on ambiguous identity, missing provenance, copy-verify failure, or relationship inconsistency. Keep an applied manifest that can reverse every change.

## Output

Proposal ID, corpus size, merges, supersessions, new patterns, skipped/flagged, files changed if apply, validation evidence, follow-up. Follow-up distill writes the constitution (the repo profile names it: `AGENTS.md`, or `CLAUDE.md` where that is the constitution) only, on the owner's word. Never stage, commit, or push.
