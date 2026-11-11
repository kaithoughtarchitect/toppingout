---
title: lens-loose-ends
id: agents/lens-loose-ends
type: agent
status: confirmed
relates:
  - index
  - f-inspect
updated: 2026-09-25
---

# lens-loose-ends

Agent: `agents/lens-loose-ends.md`.

Find what a change should also have touched: an untouched copy, a sibling line, a companion piece, an existing function.

**On site:** Used as a reviewer inside [[f-inspect]]; the only lens that reads the rest of the repo rather than the diff. Its candidate list comes from a local script in f-inspect's folder.

**When to use it:** When the changes add functions or edit existing code, which is nearly every job.

## Links

- used by [[f-inspect]] (the lens inspection, inside a job)

## See also

- [[index]]
