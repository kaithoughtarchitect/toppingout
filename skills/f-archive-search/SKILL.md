---
name: f-archive-search
description: >
  Search across all ARCHIVED Logbook cards. Use when the user runs
  /f-archive-search, says "look in the archive", "we knew this before", "search
  the old cards", or when /f-search came back empty and the knowledge may
  predate the last rotation. Archived cards only: for live cards use f-search.
---

# Topping Out: Logbook archive search

Search archived Logbook cards under `foreman/logbook/archived/*/entries/`.

Never search live `foreman/logbook/entries/`. Never query any other knowledge store in place of the files (a repo may keep its own card database or search service; this skill reads only the archived Logbook files). Never invent a card.

If `archived/` has no `NNN/` batches (only `.gitkeep` or empty), say so and point at `/f-search`. Do not print a sample dump as if Archive 001 exists.

## Query

Case-insensitive substring over card files. Keep terms simple. Protocol detail: `foreman/logbook/ARCHIVE-SYSTEM.md`.

## How

1. Glob `foreman/logbook/archived/*/entries/**/*.md` (do not use Unix `ls -d`), excluding `*TEMPLATE*`. Skip missing folders.
2. Find matches, group by archive number (`NNN`).
3. For each hit, read frontmatter: `id`, `type`, `cluster` (cards use `cluster:`, not `section:`), `title`, plus a one-line summary.
4. One-hop related: grep that card's `id` in the same archive's `logbook_links.md`.

## Output

Per archive: id, type, cluster, summary, path, related ids if any. Empty query hits: say none found in the batches that exist.
