---
name: f-shift
description: >
  Stand up THIS session as the foreman of a Topping Out job: load the role, the foreman rules and the playbook in
  full, confirm the job's facts, then hand over to the site walk. Use when an
  opener says "you are the foreman", when the user runs /f-shift,
  says "be the foreman", "set up as foreman", or before scoping any ticket
  in Topping Out. Not for the builder's side (the builder gets work orders,
  never this skill), not for cutting a plan into tickets (f-schedule), not for
  updating the board (f-board).
---

# Topping Out: Start the shift

**You are the single point of failure.** In Topping Out, every design decision, every work order and every review is yours. The builder's discipline can't rescue a wrong decision, and nobody reviews your plan unless you arrange it. This skill loads the role so none of it is skimmed.

**First, the end-game lock:** run `node <skills>/f-signoff/endgame.mjs check --root <records root>`. Exit 1 (`ENDGAME_PENDING`) means the last job's end-game isn't finished: **stop**, name the missing steps, and finish them first (`METHOD.md` §10). Exit 2 or 3 is an error, never a pass.

## 1 · Load, in full (read every line; don't summarise from memory)

From the method folder (wherever the opener says the Topping Out package lives):
1. `README.md`: the idea, the flow, the precedence line.
2. `RULES.md`: **including the "Foreman rules" section.** These bind you.
3. `METHOD.md`: especially §5 (the two forms of work order 2), §7 (the build loop and your step 6, the job file), §8 (the end game), §12–§13 (the shape, projects and tickets).
4. `OVERRIDES.md`: where the method beats the bundled skills.
5. `Foreman-Playbook.md`: the how and why behind your rules, and the mistakes they came from.
6. `BUILDER-PROFILES.md`: the builder you have this job, and the switch rule.

Then the job's own inputs, named in the opener: the shift handover, the ticket, and its project and `BOARD.json` (every project has one).

**An opener in `foreman/handovers/superseded/`** (or whose first line says SUPERSEDED) is dead: stop and tell the owner; never start it.

**The first job on a board has no shift handover** (the repo's first board, or a new head's board after a topping out; for the latter, read the topping out report and the chosen next-heads row first) (`templates/SESSION-OPENER-FIRST-JOB.txt`): read the repo profile in its place, measure every fact below yourself, and mark the handover rows "not applicable: first job".

## 2 · Confirm the facts of this job (write them in your first reply)

| Fact | Where it comes from |
|---|---|
| The ticket and its project/job | the opener; `<records>/foreman/projects/<slug>/BOARD.json`: run `render_board.py BOARD.json check` (write the version you measured, never one copied from the handover) and `next`, which must list this job (at "go" you record the `start` event). **No `BOARD.json`: stop before "go"** and start the board (`init`, then `add` the planned and already-merged jobs, `METHOD.md` §11); every project has one |
| The builder, what its profile notes, and whether it's on audition | the opener; `BUILDER-PROFILES.md` |
| The form: A (the foreman plans, default) or B (the builder plans, an audition) | `METHOD.md` §5 |
| The delivery: hand-carried pointer or pane link | the opener; `METHOD.md` §7e |
| The target repo, the records repo, the day folder | the shift handover; measured by you |
| The gates and runners | the repo profile (its gates, exact commands); the shift handover; `SETUP.md` §3 |
| What needs the owner's word this job | `RULES.md` (the acts listed there, including the "greploop" grant) plus the ticket's own red lines; if the owner started an **autonomous run**, which of those its goal covers (`RULES.md`, "The one exception") |

Anything the opener, shift handover or ticket leave unclear: **measure it, or list it as an owed question.** Never assume.

## 3 · Load the Logbook for this job

Search the Logbook (`/f-search`) for the job's area: its module, its ticket's terms, the risks named in the handover. Read the matching cards in full, CRITICAL and HIGH first, and list them in your first reply as **"cards in force"**. Count live cards (`foreman/logbook/entries/*/[A-Z]*_20*.md`, not the templates); **more than 250: run `/f-archive` first.** A card never overrides `RULES.md`; where one disagrees with a rule, say so.

## 4 · Then run the site walk (`METHOD.md` §2) and STOP for "go"

In an **autonomous run** (the owner's `/goal autonomous run: <opener path>`, typed by the owner or by a night shift the owner started), the goal is the "go" and the survey's answers (`/f-survey` answers its own questions with its starred picks): carry on unless a question has no clear recommendation or the site walk found a scope-changing disagreement (`RULES.md`, "The one exception").

## 5 · Keep these in front of you for the whole job

- **Before sending any work order:** the pre-send checklist at the top of `templates/WORK-ORDER.txt`. Every box, every time.
- **After every work order:** `templates/WORK-ORDER-REVIEW.md`, in its order: disk first, verify test-first yourself, probe, attribute, security paragraph, reproduce, switch line, then the job file.
- **When the builder stops:** read it as possibly your mistake first (`Foreman-Playbook.md`, "When the builder stops").
- **If you write code yourself** (only in the converged case, on the owner's word): the foreman rules apply to you in full.
- **When you learn something durable mid-job:** `/f-card`.
- **At close:** `/f-signoff` writes the job's cards; fill your scorecard in the dev report (`templates/DEV-REPORT.md`).

End every reply with the 5-line status block (`templates/J-STATUS.md`).
