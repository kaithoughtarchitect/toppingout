---
name: f-distill
description: >
  Promote the highest-value Logbook cards into halt-shaped NEVER/ALWAYS rules:
  product lessons into the repo's constitution, method lessons into Topping Out's own
  RULES.md or playbooks, and propose a check (a job, or a Topping Out change) for each
  lesson a machine can check. Preview first; write only on the owner's word. Use for
  /f-distill, "distill the logbook", "pull the best learnings into the rules".
  Not for capturing one card (f-card), not for merging or retiring cards (f-dream).
---

# Topping Out: Distill

Score Logbook cards. Preview halt-shaped bullets. **Write nothing until the owner approves the exact bullets.**

## Two destinations

- **Product lessons** (about this codebase): the repo's **constitution**, which the repo profile names (`AGENTS.md`, or `CLAUDE.md` where that is the constitution). If `CLAUDE.md` is only `@AGENTS.md`, write `AGENTS.md` and leave `CLAUDE.md` alone.
- **Method lessons** (about how Topping Out works): a proposed change to `RULES.md` in the Topping Out package (the foreman rules) or `Foreman-Playbook.md` / `Builder-Playbook.md`. Show it as a diff; the package is changed only on the owner's word.

## Halt

- Preview first. No write until the owner approves the exact bullets.
- No auto-synced "distillation" section, no HUD, no "run /f-distill to refresh" inside the constitution or the rules.
- **Preview mode** (from `/f-signoff` Step 3.2a): steps 1 to 3 only, written to `<day folder>/DISTILL-PREVIEW.md` with its date and the cards it read; it asks nothing and writes nowhere else. The owner applies it later with `/f-distill`, which re-scores before showing the bullets (cards may have changed).
- A card never overrides a rule by itself: a bullet that contradicts an existing rule is shown as a proposed change to that rule, with both texts.
- **Distill never writes a check itself.** A product check is product code, and the foreman never writes product code: it becomes a job on the board. A method check is a Topping Out change: it is proposed, and made only on the owner's word. A bullet says `checked by` only once its check exists and has been shown failing on the past mistake.
- Not `f-card`. Not `f-dream`.

## 1. Gather

Read `foreman/logbook/logbook_index.md` and `foreman/logbook/logbook_links.md`, and the current constitution and Topping Out's `RULES.md`.

## 2. Score (a ranking heuristic)

The multipliers can push a score past 100: it orders candidates, it isn't a probability or a percentage. Inputs a card type doesn't have count as 0 (BUILD has no `confidence`: use 0 and rely on relationships, recency and impact).

```
confidence (0–100)             × 0.25
relationship_count (cap 10)    × 2.5
recency (<14d=100, <30=80, <90=60, else 40) × 0.15
actionability                  × 0.15
impact (CRITICAL=100, HIGH=75, MEDIUM=50, LOW=25) × 0.20

× 1.5 anti-pattern · × 1.4 CRITICAL · × 1.3 cross-cluster · × 1.2 HIGH · × 0.7 product-specific
```

Prefer CRITICAL/HIGH on ties. One card, one bucket. Caps: 5 anti-patterns, 5 insights, 3 methods, 3 recent (last 14 days), 3 builds (last 30 days).

## 3. Preview

Halt-shaped bullets only (one or two lines, NEVER/ALWAYS), each tagged with its destination (the repo's constitution, or Topping Out's `RULES.md` and playbooks), its source card ids, and what carries it (3a). Also list HIGH/CRITICAL cards that missed the cutoff only on recency or relationship decay; don't auto-promote them.

### 3a. Can a check carry it?

A written rule holds only for an agent that reads it and remembers it. A check fails the work that breaks it, even when nobody read the rule. So for each bullet, ask whether a machine can tell the mistake from the right thing, and try the highest level that works:

1. **Remove the wrong way:** one supported way to do the thing, the old way deleted, so there is nothing wrong to copy.
2. **Make it unwritable:** a type or a schema that refuses the bad state.
3. **A check whose error names the fix:** a lint, a CI step, or a script the foreman or builder already runs. Where the pattern is already common, fail only when a change adds more of it.
4. **A test** of the behaviour.
5. **Text, last:** a judgment call nothing can test stays a bullet, as before.

Each bullet then says one of:

| Carried by | The preview shows |
|---|---|
| **text** | the bullet, as before |
| **a product check** (levels 1 to 4, in this repo's code) | the bullet, plus a proposed **job**: a board id, a title, the check, where it lives, and its acceptance line: *the check fails on `<the past mistake>` and passes on main*. The past mistake comes from the card's evidence (the commit, the diff or the work order it cites), shown red on that commit or on a broken copy of main that puts the mistake back, the same way a mutation probe is shown to bite. A card with no such evidence gets no check: say so, and keep the bullet as text. |
| **a method check** (a script in Topping Out) | the bullet, plus a proposed Topping Out change: what the script checks, where it would live (`skills/` or `snippets/`), and the past mistake it must fail on |

One check can carry several bullets. A bullet that is half judgment keeps its text for that half.

Ask: **Proceed with these bullets, and add these jobs?** (The owner can approve the bullets and leave a proposed job or change out.)

## 4. Write (after the owner's go)

Merge the approved bullets into the existing NEVER/ALWAYS (or matching) sections of each destination. No new "Distillation" heading. A bullet with an approved check ends `(check owed: job <id>)` or `(check owed: Topping Out change)`; the job that builds the check changes it to `(checked by <path>)` when it lands. Record in each source card's front matter `distilled: <date> -> <destination>`, plus `; check: job <id>` where one was approved.

For each approved product check, add its job to the project board the way `/f-board` says (`render_board.py <project>/BOARD.json add <id> …`; with lanes, through `snippets/board_push.sh`; a v2 board needs the job's ticket, footprint, estimate and uses, so write its ticket first, `METHOD.md` §10 step 8). No open board: list the job as owed in the report, for the next board. An approved method check goes into the report as a proposed Topping Out change, with its past mistake.

## 5. Report

Cards analysed, bullets written per destination, checks proposed and the jobs added (or owed), the aged-out table (or empty).
