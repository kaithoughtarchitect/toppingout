---
title: f-inspect
id: f-inspect
type: skill
status: confirmed
relates:
  - index
  - agents/lens-code
  - agents/lens-tests
  - agents/lens-errors
  - agents/lens-types
  - agents/lens-comments
  - agents/lens-instructions
  - agents/lens-migrations
  - agents/lens-simplify
updated: 2026-09-25
---

# f-inspect

Slash: `/f-inspect`. Folder: `skills/f-inspect/SKILL.md`.

Have specialist reviewers check the finished job's changes and report only problems.

**On site:** Near the end of a job, the first of two reviews: the foreman runs it once the build is finished, before any pull request. Small, low-risk jobs skip it.

It reviews only this job's changes, makes no fixes and gives no verdict, just findings. The record goes in `templates/LENS-INSPECTION.md`.

**When to use it:** When a job's build is finished and its tests pass, before the pull request is opened.

## Links

- uses [[agents/lens-code]]
- uses [[agents/lens-tests]]
- uses [[agents/lens-errors]]
- uses [[agents/lens-types]]
- uses [[agents/lens-comments]]
- uses [[agents/lens-instructions]]
- uses [[agents/lens-migrations]]
- uses [[agents/lens-simplify]]

## See also

- [[index]]
