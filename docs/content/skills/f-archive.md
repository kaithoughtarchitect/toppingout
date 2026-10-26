## It's working if

- Without `--execute` it only previews: the live count, the archive number, the 50 kept cards with scores and clusters, and a few that would leave. Nothing is copied or deleted.
- With 250 live cards or fewer, it archives nothing and says why.
- After a real run, the archived cards sit in a new numbered folder under `foreman/logbook/archived/`, with a `MANIFEST.json` and a `MANIFEST.md`.
- The live Logbook keeps 50 index cards, plus every `ruled-out` card.
- The index and links are rebuilt for the kept cards, with counts taken from the files.
- The report ends with the helper's exit and its `verify` result. It staged, committed and pushed nothing.

## Common questions

### Will it archive cards without asking me?

No. Other skills start it automatically when the live count passes 250, but it stays a dry run until you say `--execute`.

### What stops it losing cards?

All copying, hashing and deleting goes through the helper script `foreman/logbook/archive_cards.py`. It copies every card, checks each copy's hash, and only then deletes. On any mismatch or missing copy it exits 1, deletes nothing, and prints `VERIFY FAILED` lines.

### Which cards stay live?

It scores each card on how many links it has and how recent it is, then keeps the top 50, at most 10 per cluster, filling any spare slots by score. Every `ruled-out` card is kept as well, so `/f-survey` can still find it.

### Can I undo an archive?

Yes. `archive_cards.py restore` checks the archive first, copies back only cards that are missing, and never overwrites a live card that differs. Archive folders are never deleted.

### Does it merge or retire duplicate cards?

No. It rotates by count and judges nothing. Reconciling duplicates and contradictions is `/f-dream`.
