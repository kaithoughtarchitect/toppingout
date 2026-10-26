---
name: f-catchup
description: >
  Bulk-extract Logbook cards from completed jobs that were never captured.
  Use when card maintenance has fallen behind. Not for a session status refresh
  (f-status). Not one card from this conversation (f-card). Not close of the
  current job (f-signoff).
disable-model-invocation: true
---

Owner-invoked only. This pass writes many card files, so it fires when the owner types it and never on description match.

# Topping Out: Logbook catch-up

## Halt

- Preview the gap. **Wait for y/n** before writing any card.
- Do not invent learnings. Do not auto-run `/f-distill`. Distill, if offered later, writes the constitution (the repo profile names it: `AGENTS.md`, or `CLAUDE.md` where that is the constitution) only, on the owner's word.
- Do not modify completed jobs. Never stage, commit, or push.

## Scope

Optional `--since YYYY-MM-DD`. Otherwise compare completed-job dates (`foreman/completed-jobs/*/JOB_*.md`) with the latest indexed cards. Read the three templates and `logbook_index.md` before proposing.

## Process

1. Enumerate completed jobs in scope and map existing card provenance. Keyword overlap is a hint; coverage is semantic.
2. Identify jobs with no coverage or clearly incomplete coverage.
3. Present covered vs uncovered. Estimated card counts. **Proceed? (y/n)**
4. After go: root may dispatch bounded `code-explorer` batches of non-overlapping jobs. Children return candidates only and never recursively dispatch.
5. Verify each candidate against the source. Deduplicate against current IDs.
6. Write only high-value cards from the installed templates: reusable INSIGHTs, repeatable METHODs, compact BUILDs. Skip routine jobs (“no cards warranted”). Do not force one BUILD per job.
7. Update `logbook_index.md` and `logbook_links.md` as `/f-card` Step 9 does: a row per card, counts **recounted from the card files** (templates excluded), never incremented. Preserve IDs and provenance.

## Report

Jobs inspected, cards created/skipped, remaining gaps. Stop. Offer `/f-distill` as a separate owner step.
