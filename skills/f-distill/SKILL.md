---
name: f-distill
description: >
  Promote the highest-value Logbook cards into halt-shaped NEVER/ALWAYS rules:
  product lessons into the repo's constitution, method lessons into Topping Out's own
  RULES.md or playbooks. Preview first; write only on the owner's word. Use for
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
- No auto-synced "distillation" section, no HUD, no "run /f-distill to refresh".
- A card never overrides a rule by itself: a bullet that contradicts an existing rule is shown as a proposed change to that rule, with both texts.
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

Halt-shaped bullets only (one or two lines, NEVER/ALWAYS), each tagged with its destination (the repo's constitution, or Topping Out's `RULES.md` and playbooks) and its source card ids. Also list HIGH/CRITICAL cards that missed the cutoff only on recency or relationship decay; don't auto-promote them.

Ask: **Proceed with these bullets?**

## 4. Write (after the owner's go)

Merge the approved bullets into the existing NEVER/ALWAYS (or matching) sections of each destination. No new "Distillation" heading. Record in each source card's front matter `distilled: <date> -> <destination>`.

## 5. Report

Cards analysed, bullets written per destination, the aged-out table (or empty).
