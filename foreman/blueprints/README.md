# Blueprints and ideas

The index of everything planned but not yet built. **Trust the disk:** a file listed here but missing, or on disk but not listed, means this index is wrong; fix it.

| Folder | Holds | Written by |
|---|---|---|
| `foreman/ideas/` | `IDEA-<date>_<slug>.md`: half-formed ideas with their open questions kept. Not plans; never built directly | `/f-sketch` |
| `foreman/blueprints/ready/` | `BLUEPRINT-<date>_<slug>.md`: decision-complete plans. Each carries its `**gate: plancheck**` line once cold-read, then `/f-schedule` cuts it into a project | `/f-blueprint`, `/f-plancheck` |
| `foreman/blueprints/deferred/` | blueprints deliberately postponed before any build, each with the trigger that brings it back | the owner's call |
| `foreman/projects/<slug>/` | a decomposed blueprint: `PROJECT.md`, `tickets/`, `BOARD.json`, `board.html` | `/f-schedule`, `/f-board` |

A blueprint is never retired at a job close. When its board tops out (every job merged or decided, or the owner's topping out with jobs carried over), the owner may say to archive it: it moves to `foreman/blueprints/archived/` (created then) and its entry moves to an **Archived** list here. An idea that's folded into a blueprint, superseded or dropped moves to `foreman/ideas/archived/` the same way. **Options ruled out** aren't kept here: each one that could plausibly come back is a Logbook **ruled-out** card (tag `ruled-out`, with Why and Revisit if), so `/f-survey` and `/f-search` find it.

## Ready

_None yet._

## Deferred

_None yet._

## Ideas

_None yet._
