# Project: <title>

**Slug:** `<project-slug>` · **Lives in:** `<records repo>/foreman/projects/<project-slug>/` · **Source plan:** `<path to the /f-blueprint BLUEPRINT>` (the decisions and acceptance below are quoted from it, never reworded) · **Decomposed by:** `/f-schedule`, <date> · **Board:** `BOARD.json` → `board.html`, published at <link or "not yet published">

## The head (the outcome every job feeds)
<One sentence, from the plan's objective.>
**Judged by:** <the plan's final acceptance, e.g. the owner's walkthrough; never a green gate alone>.

## Locked decisions (inherited by every ticket)

| ID | Decision (verbatim from the plan) |
|---|---|
| D0 | |

## Global acceptance → jobs

Every verification point in the plan maps to at least one job. A VP no job carries is a gap in the decomposition.

| VP (verbatim) | Carried by jobs |
|---|---|
| VP0 … | 01, 05 |

## Jobs

| Job | Ticket | Tracker key | Needs | One line |
|---|---|---|---|---|
| 00 | `tickets/TICKET-00-….md` | <key or , > | none | |

**State is not kept here.** It lives only in `BOARD.json` (and on the board page), so it can't go stale in three places.

## Plan check findings on the blueprint

`gate: plancheck` <the line f-plancheck wrote>. One read per plan; a second only on the owner's word. The decisions above are not rewritten: each finding's fate is recorded here.

| # | Finding (with its evidence) | Fate | Why |
|---|---|---|---|
| P1 | <claim, file:line or scenario> | applied / rejected / answered | <what changed, or why not: e.g. reopens D-3, no evidence, style only> |

## Decisions and research the owner owns
Each decision job: what must be decided, the options with their evidence, and which jobs each answer unblocks.

## What the plan says that no job carries (on purpose)
Out-of-scope items and superseded parts of the plan, with the reason, so they aren't rediscovered as gaps.

## Reconciliation with what's already built
What the repository already holds for this project (commits, partial work, open jobs), measured on disk with the commands, and which job each piece belongs to.
