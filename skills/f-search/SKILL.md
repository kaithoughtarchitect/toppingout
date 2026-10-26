---
name: f-search
description: >
  Find cards in the file-based Logbook (foreman/logbook/). Use when the
  user runs /f-search, or when looking for past learnings, gotchas, or
  methods. Live cards only: archived cards are f-archive-search.
---

# Topping Out: Logbook search

Search live Logbook cards under `foreman/logbook/entries/`.

Never search `foreman/logbook/archived/`. Never query any other knowledge store in place of the files (a repo may keep its own card database or search service; this skill reads only the live Logbook files). Never invent a card.

## Query

Parse `$ARGUMENTS` as any mix of:

- keywords, words not starting `#`, `@`, or `type:`
- `#tag`, match inside the YAML `tags:` array
- `@cluster`, match the slug anywhere on the `cluster:` line (scalar or YAML array)
- `type:insight` | `type:method` | `type:build`, restrict to that type folder (`type:project` is an old alias for `type:build`)

Apply filters sequentially (AND). Keywords are case-insensitive OR.

Cluster slugs are the repo's own: they emerge from its cards (the `## Clusters` section of `logbook_index.md` lists the ones in use). Treat `@cluster` as the literal slug. A Logbook imported from an older system may carry legacy or near-duplicate slugs; if the index records an alias (old slug → current slug), search both.

If a `@cluster` search returns suspiciously few hits, retry the same token as a keyword before concluding the cards do not exist.

Empty live results: say so, and point at `/f-archive-search`. Do not print a fake card inventory.

## How

Type folders (do not use Unix `find`):

- `type:insight` → `foreman/logbook/entries/insights/`
- `type:method` → `foreman/logbook/entries/methods/`
- `type:build` (or `type:project`) → `foreman/logbook/entries/builds/`
- no type → `foreman/logbook/entries/` with `**/*.md`

Cluster: `rg -l "^cluster:.*<slug>" <root> --glob "**/*.md" --glob "!*TEMPLATE*"`
Tag: `rg -l "tags:.*<tag>" <root> --glob "**/*.md" --glob "!*TEMPLATE*"`
Keywords: `rg -l -i "kw1|kw2|kw3" <root> --glob "**/*.md" --glob "!*TEMPLATE*"`

**Always exclude `*TEMPLATE*`**: the templates carry every field and example cluster, so an empty Logbook would otherwise return three false hits.

For each match, read frontmatter (`id`, `type`, `cluster`, `tags`, `confidence` / `success_rate`) and the first 2–3 Overview paragraphs. Do not read every card in full.

## Output

Cap at 10. For each hit: id, type, cluster, tags, a short overview, path. No ranking scores, no stats table.
