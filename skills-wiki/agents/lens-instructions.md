---
title: lens-instructions
id: agents/lens-instructions
type: agent
status: confirmed
relates:
  - index
  - f-inspect
updated: 2026-09-25
---

# lens-instructions

Agent: `agents/lens-instructions.md`.

Check prompts, skills and templates for contradictions and broken references.

**On site:** Used as a reviewer inside [[f-inspect]] when skills, prompts or templates change; also used to check Topping Out itself after an edit.

**When to use it:** When skills, prompts, agents or templates changed. It also runs on demand, outside any job, whenever you decide: ask the session "run lens-instructions over <files or folder>" (`/f-setup` installs it in `.claude/agents/`). Same agent as the one some repos call `instruction-reviewer`.

## Links

- used by [[f-inspect]] (the lens inspection, inside a job)

## See also

- [[index]]
