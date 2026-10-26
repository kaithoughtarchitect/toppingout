## It's working if

- It shows which completed jobs are covered by cards and which are not, with estimated card counts, then waits for your yes before writing any card.
- Each card it writes was checked against its source job and against existing card IDs.
- Routine jobs are skipped with "no cards warranted", rather than given a card each.
- New cards appear as rows in `logbook_index.md`, with the counts recounted from the card files.
- The report lists jobs inspected, cards created and skipped, and the gaps left.
- Completed jobs are untouched, `/f-distill` did not run, and nothing was staged, committed or pushed.

## Common questions

### Will it run on its own?

No. It is set to run only when you type it, because it writes many card files.

### Can I limit how far back it looks?

Yes: `--since YYYY-MM-DD`. Without it, it compares completed-job dates with the latest indexed cards.

### How is it different from `/f-card`?

`/f-card` writes one card from the conversation you are in. This works through past completed jobs in bulk and fills in the ones that never got cards.

### Does it update the rules too?

No. When it finishes it offers `/f-distill` as a separate step for you to choose.
