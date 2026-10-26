## It's working if

- Results are grouped by archive number, each with the card's id, type, cluster, summary and path.
- Related ids from the same archive's `logbook_links.md` are listed next to a hit when there are any.
- It searches only `foreman/logbook/archived/*/entries/`, never the live Logbook.
- If there are no archive batches yet, it says so and points you to `/f-search`.
- When nothing matches, it says none were found in the batches that exist, with no sample cards.

## Common questions

### When should I use this instead of `/f-search`?

When `/f-search` comes back empty and the lesson may be older than the last rotation. `/f-search` reads live cards only; this reads archived cards only.

### How should I phrase the search?

Keep the terms simple. It matches text inside the card files, ignoring case.

### Why does it say there is nothing to search?

The Logbook has not been rotated yet, so `archived/` holds no numbered batches. Your cards are all still live.
