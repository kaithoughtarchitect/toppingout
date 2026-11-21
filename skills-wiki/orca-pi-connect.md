---
title: orca-pi-connect
id: orca-pi-connect
type: skill
status: confirmed
relates:
  - index
updated: 2026-09-25
---

# orca-pi-connect

Slash: `/orca-pi-connect`. Folder: `skills/orca-pi-connect/SKILL.md`.

Link the foreman to a Pi, Claude Code or agy builder in the Orca pane beside it, and know when it finishes.

**On site:** Handing work to the builder in Orca: the foreman sends each work order itself and is woken up when the builder finishes.

Comes with a finish signal for each builder (Pi's extension, a Stop hook for Claude Code and for agy), starts the builder inside the job's folder without the trust question, and binds a pane it opened itself without asking.

**When to use it:** When the builder runs in an Orca pane next to the foreman.

## See also

- [[index]]
