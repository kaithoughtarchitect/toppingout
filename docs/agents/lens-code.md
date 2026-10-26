# lens-code

Look for bugs and broken project rules in the changed code.

Stage: Inspect · Agents used as review lenses
Source: `agents/lens-code.md`

## On site

Used as a reviewer inside f-inspect, the first end-of-job review.

## When to use it

In every end-of-job review; it always runs.

## It's working if

- It starts by saying what it reviewed: the job's range, a PR, or named files.
- It reports only issues it rates 80 or above for confidence, grouped as Critical (90 to 100) and Important (80 to 89).
- Each finding gives the `file:line`, the repo rule or the bug it breaks, and a concrete fix.
- A finding rated 90 or above shows the snippet, the input that reaches it with the wrong outcome, and why existing guards miss it.
- It says what it did not cover and why, and a clean diff gets zero findings, not invented ones.
- It changed no code and moved no git state.

## Common questions

### Do I call it directly, or does `/f-inspect` run it?

In Topping Out, `/f-inspect` runs it on every lens inspection, as a fresh subagent with no context from the job. You can also run it on its own, for example before opening a PR.

### Does it change code?

It is told not to: it reports only. Its tools are read and search, plus a shell it is told to use only for read-only git, so this rests on its instructions, not on a lock. Accepted findings become the builder's test-first repair work orders.

### Does it give a verdict?

Only when run on its own: it then closes with `APPROVE`, `WARNING` or `BLOCK`. Under `/f-inspect` it is asked for findings only, with no verdict.

### What does it check besides bugs?

The rules in the repo's own `AGENTS.md` or `CLAUDE.md`, code quality, and minimalism: whether an addition duplicates an existing helper or adds more than the task needed. It also keeps a list of house conventions that look like findings and are not.

### Does it run on QUICK jobs?

No. QUICK jobs skip the lens inspection, and the record says so.

## Connections

- Used by: f-inspect
