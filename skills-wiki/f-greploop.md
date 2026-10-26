---
title: f-greploop
id: f-greploop
type: skill
status: confirmed
relates:
  - index
  - adjudicate
  - f-inspect
updated: 2026-09-25
---

# f-greploop

Slash: `/f-greploop`. Folder: `skills/f-greploop/SKILL.md`.

Run an open pull request through Greptile's review, up to three rounds.

**On site:** After you open the pull request and say "greploop", before you say "merge". Then the pull request's description is checked, on every job.

Each finding is checked, the builder makes the fixes, the tests run again every round, and the fixes are pushed with your permission.

**When to use it:** After the pull request is open, when you say "greploop".

## Links

- uses [[adjudicate]]
- used after [[f-inspect]]

## See also

- [[index]]
