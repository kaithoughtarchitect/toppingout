# f-sketch

Write down a rough idea and its open questions, before anything is decided.

Command: `/f-sketch` (old name `/f-idea`)

Stage: Plan · Before a job · step 1 of 11 in the order of works (Shape the idea)
Source: `skills/f-sketch/SKILL.md`

## On site

Before a job, the very first step: when an idea is worth keeping but not ready to decide. A notes file, not a plan: what's agreed so far, the open questions and the options turned down. When it's ready it moves on to f-survey.

## Say it

- "capture this idea"
- "spec this concept out"

## When to use it

When you have an idea worth writing down but you're not ready to decide anything about it yet.

## Not for

Decision-complete work (f-blueprint), settling decisions (f-survey), a job's own plan (the foreman's PLAN.md), or single Logbook cards (f-card).

## It's working if

- It wrote exactly one file, `foreman/ideas/IDEA-YYYY-MM-DD_<short-slug>.md`, or placed it inside an existing idea directory and said so.
- The file opens with a title, a date, a status saying the discussion is open, a banner saying it is not a plan of record and not executable, and one line on where it came from.
- Settled points appear as `A0…` agreements and open questions as `Q0…`, with the options as they were discussed, not resolved.
- Nothing in it was invented: no locked decision tables, no ordered tasks, no answers to questions you never answered.
- `foreman/blueprints/README.md` has one new bullet for it in the **Ideas** section, naming what blocks promotion.
- The report gives the path, a one-line summary, the counts of agreements, open questions and rejected options, and the blocking questions.
- It opened no job, wrote no plan or code, and staged, committed and pushed nothing.

## Where it sits

The path an idea takes from a brainstorm to jobs, exactly as the skill draws it.

```
brainstorm → /f-sketch → more discussion → /f-survey → /f-blueprint → /f-plancheck
  → foreman/blueprints/ready/ (plan carries its `gate: plancheck` line) → /f-schedule → jobs
```

## Common questions

### Why does it keep my open questions instead of answering them?

Its rule is fidelity over closure. An idea file with honest open questions is complete; one with invented answers is treated as corrupt.

### What if we have actually settled everything?

It says so and points you to `/f-blueprint` instead, so a finished decision doesn't end up as a weaker thinking file.

### How does an idea become a job?

Once its open questions close, it goes through `/f-survey`, then `/f-blueprint`, `/f-plancheck` and `/f-schedule`. The idea file itself is never executed.

### We talked about two ideas. Can it capture both?

One spec per run. If several distinct concepts came up, it asks which one to capture.

### It used to be called something else?

Yes: `/f-idea` still works.

## Connections

- Leads to: f-survey
