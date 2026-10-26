---
title: f-schedule
id: f-schedule
type: skill
status: confirmed
relates:
  - index
  - f-board
  - agents/simplicity-critic
  - f-plancheck
updated: 2026-09-25
---

# f-schedule

Slash: `/f-schedule`. Folder: `skills/f-schedule/SKILL.md`.

Split a big plan into jobs, in order, and draw the project board.

**On site:** Before a job, step 4: it won't start on a plan that hasn't passed the plan check, and it waits for your go before writing anything.

Anything that needs research or your decision becomes its own job, every requirement belongs to a job, and the ticket wording is copied exactly. It writes the project's folder and its board.

**When to use it:** When a plan has passed the plan check and is ready to be split into jobs.

## Links

- uses [[f-board]]
- uses [[agents/simplicity-critic]]
- used after [[f-plancheck]]

## See also

- [[index]]
