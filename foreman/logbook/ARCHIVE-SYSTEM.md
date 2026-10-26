# Logbook Archive System

**Storage**: File-based (no database required)
**Helper**: `foreman/logbook/archive_cards.py` (Python 3, standard library only)
**Threshold**: rotate when the live card count is **greater than 250**

---

## Problem

At 250+ cards:

- `logbook_index.md` grows past a comfortable context size
- Relationship complexity explodes
- Loading and searching slow down

**Solution**: Archive cards to files, keep the top 50 "index" cards in the active Logbook.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    ARCHIVE WORKFLOW                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Current Logbook (more than 250 cards)                          │
│         │                                                        │
│         ▼                                                        │
│   /f-archive            (dry run, the default)                   │
│         │                                                        │
│         ├──► Score all cards, select 50 index cards              │
│         ├──► archive_cards.py plan: what would be copied/deleted │
│         │                                                        │
│         ▼                                                        │
│   /f-archive --execute  (only on the owner's word)               │
│         │                                                        │
│         ├──► 1. archive_cards.py archive: manifest, copy,        │
│         │       hash every destination, then delete the          │
│         │       non-index cards                                  │
│         ├──► 2. Write MANIFEST.md (human summary)                │
│         ├──► 3. Regenerate logbook_index.md for the 50 cards     │
│         ├──► 4. Regenerate logbook_links.md for the 50 cards     │
│         └──► 5. archive_cards.py verify                          │
│                                                                  │
│   New Logbook (50 index cards) → grows past 250 → repeat         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure

### Before Archive

```
foreman/logbook/
├── logbook_index.md          # every live card
├── logbook_links.md          # all relationships
├── archive_cards.py          # the archive helper
├── entries/
│   ├── methods/              # METHOD cards + METHOD-TEMPLATE.md
│   ├── insights/             # INSIGHT cards + INSIGHT-TEMPLATE.md
│   └── builds/               # BUILD cards + BUILD-TEMPLATE.md
└── sessions/                 # Historical archive (frozen)
```

**Cards** are the files matching `[A-Z]*_20*.md` anywhere under `foreman/logbook/entries/`, excluding `*TEMPLATE*`. Templates are never archived, counted or deleted.

### After First Archive

```
foreman/logbook/
├── logbook_index.md          # 50 index cards (regenerated)
├── logbook_links.md          # links between index cards only (regenerated)
├── entries/
│   ├── methods/              # index METHOD cards + template
│   ├── insights/             # index INSIGHT cards + template
│   └── builds/               # index BUILD cards + template
├── archived/
│   └── 001/                  # First archive
│       ├── MANIFEST.json     # machine manifest: relative paths, sha256, size
│       ├── MANIFEST.md       # human summary
│       ├── logbook_index.md  # the index as it was before the archive
│       ├── logbook_links.md
│       └── entries/
│           ├── methods/      # every METHOD card (index cards included)
│           ├── insights/
│           └── builds/
└── sessions/
```

Every card is in the archive, including the 50 index cards, which also stay live in `entries/`.

### After Multiple Archives

```
foreman/logbook/archived/
├── 001/
├── 002/
└── 003/
```

The next archive number is the highest existing `archived/NNN/` plus one (`001` when there is none).

---

## The helper: `archive_cards.py`

Run from the repository root. Exit codes: **0** ok, **1** verification failure or data problem, **2** usage error.

| Command | What it does |
|---|---|
| `python foreman/logbook/archive_cards.py plan --archive NNN [--keep FILE]` | Dry run. Lists the card files, `logbook_index.md` and `logbook_links.md` that would be archived (and, with `--keep`, which cards stay). Writes nothing. Fails if `archived/NNN/` exists with different content |
| `python foreman/logbook/archive_cards.py archive --archive NNN --keep FILE` | Writes `MANIFEST.json` first, copies each file preserving the `entries/<type>/` layout, hashes each **destination** and compares it with the manifest, and only if every destination matches deletes the non-kept source cards |
| `python foreman/logbook/archive_cards.py verify --archive NNN` | Re-hashes every archived file against `MANIFEST.json` |
| `python foreman/logbook/archive_cards.py restore --archive NNN` | Verifies first (refuses on any mismatch), copies back only the cards missing from `entries/`, re-hashes each restored file. Never overwrites a live card that differs (it reports it), never deletes the archive |

`--keep FILE` is a text file of index-card ids, one per line (blank lines and `#` comments ignored). An id is the card's filename without `.md` (or its frontmatter `id:`). An id that matches no card is refused before anything is written. Keep the file outside `archived/NNN/` (a temporary file is fine); the kept ids are recorded in `MANIFEST.json`.

`MANIFEST.json` holds `archive`, `created`, `base` (`foreman/logbook`), `kept`, and `files`: one `{path, sha256, size}` per file, paths relative to `foreman/logbook/` with `/` separators. It works the same on Windows and Linux.

---

## Commands

### `/f-archive [--dry-run|--execute]`

**Purpose**: Archive the current cards and start fresh with the top 50 as the index.

**Flags**:

- `--dry-run` (default): Preview what will happen
- `--execute`: Actually perform the archive, only on the owner's word

**Process**:

1. Count live cards from the files (`[A-Z]*_20*.md` under `foreman/logbook/entries/`, excluding `*TEMPLATE*`). If the count is **250 or fewer**, archive nothing and say so; an empty or small Logbook is never archived.
2. Parse each card's YAML frontmatter for `id:`, `created:` and `cluster:`.
3. Count relationship occurrences of each `id:` in `logbook_links.md`.
4. Score all cards and select 50 index cards (see Index Selection).
5. Pick the archive number `NNN` and write the kept ids (the 50, plus every `ruled-out` card) to a keep file.
6. Run `archive_cards.py plan --archive NNN --keep FILE` and show the preview. **Dry run stops here.**
7. On `--execute`: run `archive_cards.py archive --archive NNN --keep FILE`. Continue only on exit 0; on exit 1 nothing was deleted, report the output and stop.
8. Write `archived/NNN/MANIFEST.md` (the human summary below).
9. Regenerate `logbook_index.md` with the kept cards only, ruled-out cards included (recount from the files).
10. Regenerate `logbook_links.md` keeping a link only if **both** ends are index cards.
11. Run `archive_cards.py verify --archive NNN`.

**Output (dry-run)**:

```markdown
# Archive Preview (Dry Run)

**Current cards**: <n> (excluding templates)
**Will archive**: <n>
**Will keep as index**: 50
**Archive number**: <NNN>

## Index Selection Preview

| Cluster | Total | Index | Archived Only |
| ------- | ----- | ----- | ------------- |
| <cluster slug from the corpus> | ... | ... | ... |

## Top Index Cards (by score)

| Rank | Card | Relationships | Recency | Score |
| ---- | ---- | ------------- | ------- | ----- |
| 1    | METHOD_<YYYYMMDD>_<NAME> | ... | ... | ... |

## Sample Cards Being Archived Only

- INSIGHT_<YYYYMMDD>_<NAME> (rel: 2, score: 6)

---

This is a preview. Run `/f-archive --execute` to proceed.
```

**Output (execute)**:

```markdown
# Archive Complete

**Archive**: <NNN>
**Cards archived**: <n>
**Index cards kept**: 50
**Archived at**: <timestamp>

## Active Logbook Reset

- logbook_index.md: 50 index cards
- logbook_links.md: index relationships only
- entries/: 50 card files + templates

Search archived cards: `/f-archive-search [query]`
```

---

### `/f-archive-search [query]`

**Purpose**: Search all archived cards.

**Process**:

1. Search the query across all `archived/*/entries/**/*.md`, excluding `*TEMPLATE*`
2. Parse matching cards' frontmatter for metadata
3. Show results with archive number
4. Include related cards (1-hop from that archive's `logbook_links.md`)

**Output**:

```markdown
# Archive Search: "<query>"

**Searching**: Archives 001
**Query**: <query>

## Direct Matches (1)

### 1. METHOD_<YYYYMMDD>_<NAME>

**Archive**: 001 | **Type**: METHOD | **Cluster**: <cluster>

> <one-line summary>

**File**: `archived/001/entries/methods/METHOD_<YYYYMMDD>_<NAME>.md`

## Related Cards

From `archived/001/logbook_links.md`:

- METHOD_<...> → refines → INSIGHT_<...>
```

---

## Archive MANIFEST.md Format

`MANIFEST.json` is the helper's integrity record. `MANIFEST.md` is the human summary the skill writes after a successful `archive`:

```markdown
# Archive <NNN>

**Created**: <timestamp>
**Cards**: <n>
**Relationships**: <n>
**Index Cards**: 50 (kept in the active Logbook)

## Statistics

| Type    | Count |
| ------- | ----- |
| METHOD  | ...   |
| INSIGHT | ...   |
| BUILD   | ...   |

## Clusters

| Cluster | Count |
| ------- | ----- |
| <slug>  | ...   |

## Index Cards (carried forward)

1. <id>
   ... (all 50 listed)

## Date Range

- Oldest card: <date>
- Newest card: <date>
```

---

## Index Selection Algorithm

**Ruled-out cards are always kept.** Every card tagged `ruled-out` stays in the live Logbook, on top of the 50 index cards: `/f-survey` finds them through `/f-search`, which doesn't read `archived/`.

### Scoring

A heuristic for which cards stay visible, not a measure of worth: every card is kept in the archive either way.

```
Score = (relationship_count × 3) + recency_bonus

Where:
- relationship_count = times the card's `id:` appears in logbook_links.md
- recency_bonus (from the YYYYMMDD in the filename):
  - Created in last 30 days: +20
  - Created in last 60 days: +10
  - Older: +0
```

### ID Extraction for Relationship Counting

Extract `id:` from each card's YAML frontmatter, then count that exact ID in `logbook_links.md`. Do not derive the ID from a shortened name.

### Clusters

Clusters come from **this Logbook's own corpus**: each card's `cluster:` line (the first slug when it is a list), as listed under `## Clusters` in `logbook_index.md`. There is no fixed or target distribution. A card with no or unknown cluster is grouped as **other**; it is never dropped from selection.

### Selection Process

```
1. Score every live card (templates excluded).
2. Sort by score descending (ties: newer card first, then id).
3. Capped pass: take cards in order, at most 10 per cluster, until 50 are kept.
4. Fallback: if the capped pass keeps fewer than 50 (for example fewer than
   five clusters), fill the remaining slots by score from the cards not yet
   kept, ignoring the cap.
5. An archive only runs above 250 live cards, so an empty or small Logbook
   archives nothing (the skill says so and stops).
```

---

## Search Implementation

Archive search is a case-insensitive substring search over `foreman/logbook/archived/*/entries/**/*.md` (templates excluded), then a lookup of each hit's `id` in the same archive's `logbook_links.md`. File search scales well to a few thousand cards.

---

## Safety Features

### 1. Mandatory Preview

```
/f-archive           → Shows dry-run (default)
/f-archive --execute → Archives (only on the owner's word, after the dry run)
```

### 2. Manifest, copy, verify destinations, then delete

`archive_cards.py archive` does all of this; do not hand-roll shell recipes with `sha256sum`/`sed` (their output format differs by platform, and a rewrite that silently fails re-hashes the source instead of the copy).

1. **Manifest first.** `MANIFEST.json` lists every card file plus `logbook_index.md` and `logbook_links.md`, each with its relative path, SHA-256 and size. Templates are never in it.
2. **Copy** exactly the manifest's files into `archived/NNN/`, keeping the `entries/<type>/` layout.
3. **Verify the destinations.** Each copied file in `archived/NNN/` is hashed and compared with the manifest. Any mismatch or missing copy: exit 1, **nothing is deleted**.
4. **Delete** only the manifest's non-kept cards. Never templates, never kept index cards, never `logbook_index.md` / `logbook_links.md` (the skill regenerates those). A card whose source changed since the manifest was written is left in place and reported (exit 1).

A card that isn't in the manifest (written during the archive) is never touched. If `archived/NNN/` already exists with different content, the helper refuses; an identical earlier attempt (same manifest files) is resumed.

### 3. Full restore

```
python foreman/logbook/archive_cards.py restore --archive NNN
```

Restore verifies the archive against `MANIFEST.json` first and refuses on any mismatch (`ARCHIVE DAMAGED`: stop and tell the owner). It then copies back only the cards missing from `entries/`, reports any live card that differs from its archived copy without overwriting it, and re-hashes every restored file. `logbook_index.md` and `logbook_links.md` are not overwritten; for a full rollback, copy them from `archived/NNN/` by hand after the restore succeeds.

The archive folder stays after a restore. It's a second copy, not a staging area.

### 4. Error recovery

**The archive is never deleted as a rollback.** Once any card has been removed from `entries/`, the archive is the only copy of it.

| State | Recovery |
|---|---|
| `archive` exited 1 on verification (mismatch or missing copy) | Nothing was deleted. Read the `VERIFY FAILED` lines, fix the cause, and re-run the same `archive` command: an identical earlier attempt is resumed and every file re-copied and re-verified |
| `archive` refused an existing `archived/NNN/` | Nothing was written. Do not delete that folder; pick the next number or ask the owner |
| Interrupted while deleting | Run `restore --archive NNN` (verifies the archive, re-copies only missing cards), then retry the archive from the dry run |
| Index regeneration failed | Copy `logbook_index.md` and `logbook_links.md` back from `archived/NNN/`, then regenerate |
| `verify` or `restore` reports a mismatch | Do not overwrite or delete anything in `archived/NNN/`. Cards already deleted from `entries/`: stop and tell the owner (below). None deleted yet: the live cards are still the originals; report and ask the owner |

If any hash check fails in a state where cards were already deleted, **stop and tell the owner**: that is data loss, not a retry.

---

## Comparison: File-Based vs Database

| Aspect         | File-Based (chosen)        | Database                 |
| -------------- | -------------------------- | ------------------------ |
| Setup          | None                       | Create tables, functions |
| Storage        | In repo                    | Separate DB              |
| Search         | Grep                       | SQL                      |
| Portability    | Clone repo = have archives | Need DB access           |
| Backup         | Git handles it             | Separate backup          |
| Complexity     | Low                        | Medium                   |

**Decision**: File-based is simpler, keeps everything in the repo, and performs well enough at this scale.

---

## FAQ

**Q: Why 250 cards as threshold?**
A: `logbook_index.md` at 250 cards is large enough to strain a context window. 50 index cards is comfortable.

**Q: Why keep 50 index cards?**
A: Enough to maintain continuity. The most-connected cards represent core learnings that inform new work.

**Q: What if I need an archived card frequently?**
A: Bring it back by hand into `entries/` and the index; `restore` restores whole archives, not single cards.

**Q: Can I search active and archived together?**
A: `/f-search` searches active only. `/f-archive-search` searches archives only. For both, run both commands.

**Q: How do I check the helper works here?**
A: `python foreman/logbook/test_archive_cards.py` from the repository root (temporary folders only; the real Logbook is not touched).
