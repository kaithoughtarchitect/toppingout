---
name: f-status
description: >
  Catch the owner up in plain English on a Topping Out job: where we are,
  what got done, the state now, what's next. Reads ONLY the live session; no
  subagents, no git, no file reads, no writes. Use when the user runs /f-status,
  says "catch me up", "where are we", "I'm lost", "refresh me", or comes back
  after stepping away. Not the 5-line status block every reply ends with
  (templates/J-STATUS.md).
---

# Topping Out: Status refresher

Give the owner the big picture in fifteen seconds of reading. For the moment they step back, or step away and come back lost.

---

## Usage

```
/f-status              # refresh on the whole session
/f-status <topic>      # narrow to one thread
```

---

## Hard constraint: conversation only

Read **only what is already in this session's context**. This skill must answer instantly.

**Forbidden here:** subagents, `git` commands, file reads, file writes, MCP calls, web fetches, any tool at all. If you reach for a tool, the skill has failed, the owner wanted a refresher, not an investigation.

You already know what happened. Say it.

If the session was compacted, work from the summary and say so in one clause (`earlier detail is summarised`). Never invent specifics to fill a gap.

If the session is genuinely thin, just started, nothing done yet, say that in two lines and stop. A short honest answer beats a padded one.

---

## Output

Five blocks, in this order. Skip any block with nothing real in it. **Hard cap ~200 words.**

```
Where we are
<one sentence a non-engineer understands>

Done this session
 • <what changed in the world>
 • <3-5 bullets max>

Right now
<health line>

Next
<the single next action, and who does it, you or me. If nothing is needed from them: `nothing from you`>

Watch out
<only a real trap; otherwise omit entirely>
```

**Health line** uses the house vocabulary: `Healthy, <scope>: <evidence>` · `Blocked, <scope>: <what's in the way>` · `Waiting, <scope>: <on what>` · `Unknown, <scope>: <what we'd need to check>`. Name the scope you actually checked. Never imply whole-system health from one green gate.

---

## Language rules

Write it the way you'd explain it to a sharp friend who missed the last hour.

- **Plain words.** No jargon unless the owner has been using that word themselves this session. If a term is load-bearing and new to them, define it in four words inline.
- **One idea per bullet.** If a bullet needs a comma-spliced second clause, it's two bullets or it's cut.
- **What changed in the world, not what tool ran.** `the login page now remembers you`, not `edited auth-core.ts and ran typecheck`.
- **No file paths, no command names, no SHAs** in the body. They raise cognitive load and the owner can ask.
- **Numbers beat adjectives** where a number exists. `4 of 7 tests pass`, not `mostly passing`.
- **No process replay.** They don't need the order things happened in, only where it landed.
- **No reasoning.** State the situation; don't re-derive it.
- **Status is not an action.** `Right now` is state. `Next` is a thing the owner does. Never write a non-action in imperative form (`keep X`, `leave Y alone`, `don't touch Z`) inside `Next`, `keep X` is shaped exactly like `delete X`, so it reads as a task when it is the absence of one. If there is nothing for them to do, `Next` reads `nothing from you` and stops.
- **Say a caveat once.** A constraint already stated earlier in the session is a settled fact, not an open item. Repeating it makes it look unmet.

---

## What this is not

Not a report card. Don't congratulate, don't hedge, don't apologise for what isn't done. If something failed, one flat line: what failed, and whether it blocks the next step.

Don't re-open settled decisions. If the owner already chose something, it's a fact now, not an option.

Don't append offers, next-step menus, or "let me know if…". End on `Next`.

---

## Example

> **Where we are**
> We're building a small skill that tells you where you are, so you can step away and come back without re-reading everything.
>
> **Done this session**
> • Checked two public skill collections, neither had what you wanted, but both had usable parts
> • Settled the design: plain English, five blocks, reads only this conversation
> • Moved off the main branch so nothing can reach production by accident
>
> **Right now**
> Healthy, the new skill file: written and mirrored, nothing committed yet.
>
> **Next**
> You read it and tell me if the tone is right. Nothing is staged until you say so.
