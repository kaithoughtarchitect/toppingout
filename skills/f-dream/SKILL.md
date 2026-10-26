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
