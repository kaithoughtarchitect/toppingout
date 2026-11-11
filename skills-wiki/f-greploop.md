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

**On site:** On every pull request, right after it opens and before you say "merge"; a fourth round is your word, "greploop". Then the pull request's description is checked, on every job.

Each finding is checked, the builder makes the fixes, the tests run again every round, and the fixes are pushed with your permission.

**When to use it:** On every pull request, right after it opens.

## Links

- uses [[adjudicate]]
- used after [[f-inspect]]

## See also

- [[index]]
