---
name: f-archive
description: >
  Rotate the Logbook when it exceeds 250 cards, archiving the rest and keeping
  50 index cards for continuity. Use for /f-archive, "the logbook is too big",
  "rotate the logbook", "archive old cards", or when the card count has grown
  past the threshold. Also fires automatically from /f-card, /f-signoff, /f-shift
  and /f-context when the live count is over 250, and then runs through itself. Rotates by count and judges
  nothing: to reconcile duplicates and contradictions, use f-dream. Not
  archived-card search (f-archive-search).
---

# Topping Out: Logbook archive

Rotate by count. Protocol: `foreman/logbook/ARCHIVE-SYSTEM.md`. All copying, hashing, deleting and restoring goes through the helper `foreman/logbook/archive_cards.py` (Python 3, stdlib only, run from the repo root). Never hand-roll shell copy/hash/delete recipes.

## Halt

- Typed by hand, the default is **dry-run**: `--execute` writes only on the owner's word, and without it you get a preview only (`archive_cards.py plan`), no copies, no deletes.
- **Started automatically** (below) over 250 live cards, it **executes by itself**, with no owner input: the plan, then `archive`, under every guard here (manifest, copy, hash every copy, only then delete; the 50 index cards and every `ruled-out` card kept). It reports the archive number and counts for the close or shift report. Any guard that fails stops it with nothing deleted, and the job carries on.
- **Manifest → copy → hash every destination → then delete.** Never `mv`. The helper exits 1 and deletes nothing on any mismatch or missing copy; then stop, report its `VERIFY FAILED` lines, leave the active Logbook untouched.
- Count live cards from the files at run time (`[A-Z]*_20*.md` under `foreman/logbook/entries/`, excluding `*TEMPLATE*`); the index's total is a cache, and if it disagrees, the files win. Do not assume any number from the protocol file.
- **250 or fewer live cards (including an empty Logbook): archive nothing and say so.**
- Never delete an `archived/NNN/` folder, not even as a rollback. Any hash failure after cards were deleted: **stop archiving and tell the owner**. Typed by hand: stop and say so. In automatic mode: write nothing more to the Logbook, report `ARCHIVE CHECK FAILED` with the helper's lines to the caller (it goes into the dev report and the close report as owed to the owner), and return; the job carries on.
- Do not judge, merge, or supersede cards. That is `f-dream`.
- Never stage, commit, or push. Report **every path** created or deleted (the cards removed from `entries/`, the new `archived/NNN/`, the rebuilt index and links), so the caller's records commit stages them all.

**Auto-invoke.** `/f-card` (after a write, except during a close), `/f-signoff` (once, at the end of its Step 3.2a) and `/f-shift` (at the start of a shift) count live cards and run this skill when the count is **greater than 250**, through to the end (`--execute`): nothing is lost, every card stays readable through `/f-archive-search`, and `restore` puts an archive back. `/f-context` is a read-only orientation: it runs only the dry run and reports that an archive is due.

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
