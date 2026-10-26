---
name: f-archive
description: >
  Rotate the Logbook when it exceeds 250 cards, archiving the rest and keeping
  50 index cards for continuity. Use for /f-archive, "the logbook is too big",
  "rotate the logbook", "archive old cards", or when the card count has grown
  past the threshold. Also fires automatically from /f-card, /f-signoff, and
  /f-context when the live count is over 250. Rotates by count and judges
  nothing: to reconcile duplicates and contradictions, use f-dream. Not
  archived-card search (f-archive-search).
---

# Topping Out: Logbook archive

Rotate by count. Protocol: `foreman/logbook/ARCHIVE-SYSTEM.md`. All copying, hashing, deleting and restoring goes through the helper `foreman/logbook/archive_cards.py` (Python 3, stdlib only, run from the repo root). Never hand-roll shell copy/hash/delete recipes.

## Halt

- Default is **dry-run**. `--execute` required to write, and only on the owner's word. No `--execute` → preview only (`archive_cards.py plan`), no copies, no deletes.
- **Manifest → copy → hash every destination → then delete.** Never `mv`. The helper exits 1 and deletes nothing on any mismatch or missing copy; then stop, report its `VERIFY FAILED` lines, leave the active Logbook untouched.
- Count live cards from the files at run time (`[A-Z]*_20*.md` under `foreman/logbook/entries/`, excluding `*TEMPLATE*`); the index's total is a cache, and if it disagrees, the files win. Do not assume any number from the protocol file.
- **250 or fewer live cards (including an empty Logbook): archive nothing and say so.**
- Never delete an `archived/NNN/` folder, not even as a rollback. Any hash failure after cards were deleted: **stop and tell the owner**.
- Do not judge, merge, or supersede cards. That is `f-dream`.
- Never stage, commit, or push.

**Auto-invoke.** `/f-card` (after a write), `/f-signoff` (after Logbook index writes), `/f-shift` (at the start of a shift), and `/f-context` (on orientation) count live cards and run this skill when the count is **greater than 250**. They do not wait to be asked. Still dry-run until the owner says `--execute`.

## Job

When active cards (excluding templates) exceed 250:

1. Score each card: `(relationship_count × 3) + recency_bonus` (≤30d = 20, ≤60d = 10, else 0). Recency from the `YYYYMMDD` in the filename; relationship count = occurrences of the frontmatter `id:` in `logbook_links.md`.
2. Keep **50** index cards. Clusters come from the corpus (each card's first `cluster:` slug, as under `## Clusters` in `logbook_index.md`); a missing or unknown slug goes to **other**, never dropped. Capped pass: score descending, at most 10 per cluster. **Fallback:** if the capped pass keeps fewer than 50 (e.g. fewer than five clusters), fill the remaining slots by score from the rest, ignoring the cap.
2a. **Every `ruled-out` card is also kept**, on top of the 50: `/f-survey` looks for them through `/f-search`, which never reads `archived/`, so an archived one would silently stop flagging the option it ruled out.
3. Archive number `NNN` = highest existing `foreman/logbook/archived/NNN/` + 1 (`001` if none). Write the kept ids (the 50, plus every `ruled-out` card), one per line, to a keep file outside `archived/NNN/`.
4. Dry run: `python foreman/logbook/archive_cards.py plan --archive NNN --keep <file>`. Stop here without `--execute`.
5. Execute: `python foreman/logbook/archive_cards.py archive --archive NNN --keep <file>`. Continue only on exit 0 (it writes `MANIFEST.json`, copies every card plus index and links, verifies each destination hash, then deletes only the non-kept cards; templates, kept cards, index and links stay).
6. Write `archived/NNN/MANIFEST.md` (human summary, format in the protocol).
7. Rebuild `logbook_index.md` and `logbook_links.md` for the index only (keep a relationship only if **both** ends are in the index; recount from the files).
8. `python foreman/logbook/archive_cards.py verify --archive NNN` must exit 0.

Recovery: `archive_cards.py restore --archive NNN` verifies the archive first, copies back only missing cards, never overwrites a differing live card, never deletes the archive. Exit codes: 0 ok, 1 verification/data problem, 2 usage.

## Preview / report

Dry-run: current count, archive number, the 50 ids with scores and clusters (say if the fallback filled slots past the cap), a few low-scorers that would leave, the helper's `plan` summary. Then stop. If 250 or fewer cards: say nothing will be archived and why.

Execute: archive path, counts archived vs kept, timestamp, the helper's exit and verify result. Search leftovers with `/f-archive-search`.
