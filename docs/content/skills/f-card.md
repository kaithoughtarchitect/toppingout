---
sample: Step 8: Write Card File | 2
sample_title: What it prints when the card is written
sample_note: Once you approve the card, it confirms the write in this shape, exactly as the skill prints it.
---

## It's working if

- It shows you the full card, its quality score and its file path, and asks "Create this card? (y/n)" before writing anything.
- The card is one INSIGHT, METHOD or BUILD file in the matching folder under `foreman/logbook/entries/`, with an ID shaped like `TYPE_YYYYMMDD_SHORT_NAME`.
- If an existing card covers the same idea, it warns you and offers to add evidence to that card instead.
- The new card has a row in `foreman/logbook/logbook_index.md`, and the total card count there is recounted from the files.
- Any related cards it names appear as links in `foreman/logbook/logbook_links.md`.
- It writes one card per run and leaves the constitution alone.

## Common questions

### What if I run it with no arguments?

It reads the conversation and suggests up to three candidates, each tagged with its type. You pick one, and run it again for more.

### What happens if the card is thin?

Each card gets a quality score, a rough check rather than a measurement. Below 75 out of 100, it shows the score and what is missing, and asks whether to fix the card or create it anyway.

### Do I need an open job?

No. It needs no job and no session file. Without a session, the card records the conversation date instead.

### Does the card become a rule?

Not by itself. Promoting a card into the constitution is `/f-distill`, which it suggests once the card is written.

### What is the `project` type?

An old name for BUILD. It is still accepted, and the card is written as BUILD.

### What happens when the Logbook gets big?

If the live card count passes 250 after the write, it runs `/f-archive` as a dry run. Nothing is archived unless you say go.
