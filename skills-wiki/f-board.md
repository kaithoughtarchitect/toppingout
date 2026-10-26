---
title: f-board
id: f-board
type: skill
status: confirmed
relates:
  - index
  - f-schedule
  - f-shift
  - f-signoff
updated: 2026-09-25
---

# f-board

Slash: `/f-board`. Folder: `skills/f-board/SKILL.md`.

Update the project board when a job starts, merges, gets stuck or is added.

**On site:** Throughout a project: marks a job as started when you say go, merged after the merge, and stuck when it stops.

It works out by itself which jobs are ready and which are waiting, counts each change as a new version, and republishes the board page at the same link. When every job is done the board tops out: it is frozen as the project's record, and the next head gets a new board. An iteration board takes small jobs as they are found.

**When to use it:** Whenever a job starts, merges, gets stuck or is added, so the board stays true.

## Links

- used by [[f-schedule]]
- used by [[f-shift]]
- used after [[f-signoff]]

## See also

- [[index]]
