---
sample: Usage | 1
sample_title: How to call it
sample_note: The two forms it takes, shown exactly as the skill lists them.
---

## It's working if

- It answers at once, without running any tool: no git, no file reads, no subagents.
- The reply uses up to five blocks in order (where we are, done this session, right now, next, watch out) and skips any that would be empty.
- It stays around 200 words or fewer.
- The body has no file paths, command names or commit hashes.
- "Right now" is a health line naming the scope checked: `Healthy`, `Blocked`, `Waiting` or `Unknown`.
- "Next" is one action and says who does it, or reads `nothing from you`, and the reply ends there.

## Common questions

### Why won't it check the code or the repo?

It reads only what is already in the session, so it can answer instantly. If it reaches for a tool, the skill has failed.

### What if the session was compacted?

It works from the summary and says so in one clause. It never invents details to fill a gap.

### Can I narrow it to one thread?

Yes: `/f-status <topic>` refreshes you on that thread only.

### Is it the same as the status block at the end of every reply?

No. That 5-line block comes from `templates/J-STATUS.md`. This is a fuller catch-up you ask for when you step back or come back lost.

### Will it reopen decisions?

No. A choice you already made is stated as a fact, not an option, and a settled caveat isn't repeated.
