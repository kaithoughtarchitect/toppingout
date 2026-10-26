# f-search

Find Logbook cards about a topic.

Command: `/f-search`

Stage: Merge, close and Logbook · The Logbook
Source: `skills/f-search/SKILL.md`

## On site

The Logbook: any time. f-shift uses it to load the lessons that apply to a job. Searches current cards only; older ones are in f-archive-search.

## When to use it

When you want to know what past jobs learned about a topic.

## It's working if

- It returns at most 10 cards, each with its id, type, cluster, tags, a short overview and its path.
- Every hit is a live card under `foreman/logbook/entries/`, never one from `foreman/logbook/archived/`.
- The card templates never show up as hits, even in an empty Logbook.
- When nothing matches, it says so and points you to `/f-archive-search`, with no made-up list of cards.
- There are no ranking scores or stats tables in the output.

## Common questions

### How do I write a query?

Mix plain keywords, `#tag`, `@cluster` and `type:insight`, `type:method` or `type:build`. The filters combine with AND; a card matches the keywords if it contains any of them, ignoring case.

### Where do the cluster names come from?

From your own cards. The `## Clusters` section of `logbook_index.md` lists the ones in use. If a cluster search finds suspiciously few cards, it retries the same word as a keyword before saying they don't exist.

### Why can't it find a lesson I know we learned?

It reads live cards only. If the card was rotated out by `/f-archive`, search for it with `/f-archive-search`.

### Does it look anywhere besides the Logbook files?

No. It is told to read only the live Logbook files, even if the repo has its own card database or search service.

## Connections

- Leads to: f-archive-search
- Used by: f-shift
