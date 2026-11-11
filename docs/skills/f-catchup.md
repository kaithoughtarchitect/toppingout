# f-catchup

Write Logbook cards for past jobs that never got any.

Command: `/f-catchup`

Stage: Merge, close and Logbook · The Logbook
Source: `skills/f-catchup/SKILL.md`

## On site

The Logbook: once to fill it from past jobs, or after a gap. It shows you what's missing and waits for a yes. Checks each lesson against its job before writing it, and skips jobs with nothing to learn.

## When to use it

Automatically at every close, for up to three past jobs without lessons; by hand to seed many at once.

## Not for

A session status refresh (f-status).

## It's working if

- It shows which completed jobs are covered by cards and which are not, with estimated card counts, then waits for your yes before writing any card.
- Each card it writes was checked against its source job and against existing card IDs.
- Routine jobs are skipped with "no cards warranted", rather than given a card each.
- New cards appear as rows in `logbook_index.md`, with the counts recounted from the card files.
- The report lists jobs inspected, cards created and skipped, and the gaps left.
- Completed jobs are untouched, `/f-distill` did not run, and nothing was staged, committed or pushed.

## Common questions

### Will it run on its own?

Not from a description match: it writes many card files. It runs in two ways: when you type it, and automatically at every job's close (`/f-signoff`), for up to three finished jobs that have no cards yet.

### Can I limit how far back it looks?

Yes: `--since YYYY-MM-DD`. Without it, it compares completed-job dates with the latest indexed cards.

### How is it different from `/f-card`?

`/f-card` writes one card from the conversation you are in. This works through past completed jobs in bulk and fills in the ones that never got cards.

### Does it update the rules too?

No. When it finishes it offers `/f-distill` as a separate step for you to choose.

## Connections

- Uses: code-explorer
