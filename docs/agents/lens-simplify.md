# lens-simplify

Spot code that could be simpler, without changing what it does.

Stage: Inspect · Agents used as review lenses
Source: `agents/lens-simplify.md`

## On site

Used as a reviewer inside f-inspect; it never edits code while a job is being built.

## When to use it

Last in every end-of-job review, as a report only.

## Not for

Finding bugs (lens-code), not for "is this more than we need?" on a plan (simplicity-critic), not for git (the caller owns staging).

## It's working if

- Under `/f-inspect` it writes nothing: no edits, no snapshots, no gate run that writes files.
- Each proposal gives the `file:line`, the exact change, why behaviour stays the same, and what a future reader gains.
- Its ledger always says what it chose not to simplify and why, with reasons you can act on without opening the file.
- No proposal touches public interfaces, tests, migrations, transaction boundaries, access scoping, privacy, or how errors fail and get logged.
- It ran no git command that writes.

## Common questions

### Do I call it directly, or does `/f-inspect` run it?

`/f-inspect` runs it last, always with the words "report-only", so it returns proposals instead of edits. It does not start on its own: it waits for a caller.

### Does it change code?

Not under `/f-inspect`. Called without "report-only" or "findings-only", it does edit: it snapshots each file outside the repository first, and puts a file back if a change turns a gate red.

### How is it different from `simplicity-critic`?

This lens tidies code that was just written, without changing what it does. `simplicity-critic` asks whether a plan or design is more than you need, before anything is built.

### Will it make the code shorter?

Not as a goal. It is told to prefer clarity over fewer lines, for example by taking out nested ternaries.

## Connections

- Used by: f-inspect
