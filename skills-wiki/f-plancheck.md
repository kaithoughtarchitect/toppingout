---
title: f-plancheck
id: f-plancheck
type: skill
status: confirmed
relates:
  - index
  - agents/plan-validator
  - f-blueprint
updated: 2026-09-25
---

# f-plancheck

Slash: `/f-plancheck`. Folder: `skills/f-plancheck/SKILL.md`.

Have AI models from other companies read the plan fresh and point out problems.

**On site:** Before a job, step 3, between [[f-blueprint]] and [[f-schedule]]: the plan has to pass this check before it's split into jobs.

One to five AI models from other companies read the plan side by side, all with the same checklist, and their findings are combined, never voted on.

**When to use it:** After a plan is written and before it's split into jobs; also on a job's own plan before its second work order.

## Links

- uses [[agents/plan-validator]]
- used after [[f-blueprint]]

## See also

- [[index]]
