---
sample: Usage | 1
sample_title: The two ways to run it
sample_note: The two forms of the command, exactly as the skill lists them.
---

## It's working if

- On a plan without the `gate: plancheck` line, it stops and tells you to run `/f-plancheck` first. A findings row with a blank fate stops it too.
- Before writing anything, it shows you the head, the job table, the decision jobs, any unmapped verification points or tasks, any disagreements, and the job it recommends first.
- It writes nothing until you say "go" for the project.
- Research and owner decisions are their own jobs, never hidden inside another: a question that ends in your answer is a decision job; research that produces a file is a build job and goes through a PR.
- Every verification point is carried by at least one job, and every plan task maps to a job or to "not carried, on purpose" with its reason.
- `foreman/projects/<slug>/` holds `PROJECT.md`, one ticket file per job with the acceptance quoted and a "Why this job" that says in plain sentences what the job makes possible, never only its plan task, and a `BOARD.json` that `render_board.py` validated and rendered.
- Each job on the board has a summary: one plain sentence saying what it builds, taken from the blueprint task's Outcome, with plan references after it in brackets, never a summary of references alone.
- It committed nothing, and never deleted or rewrote the source plan.

## Common questions

### How big is one job?

One ticket, one PR, one module area, sized for roughly 8 to 9 work orders. A plan bigger than that becomes a project.

### Does it publish the board page straight away?

No. Publishing the board page and adding a note to the source plan are each a separate word from you, after the project is written.

### What if scoping later finds a job is too big?

Run `/f-schedule --split <project-slug> <job-id>`. The children replace the job, dependents are rewired, and every verification point is still carried. A merged or decision job can't be split.

### We use a ticket tracker. Will it create tickets there?

No. It maps each job to an existing key where one fits and never mints a new one. Where the tracker and the plan disagree, the difference goes on your list.

### It used to be called something else?

Yes: `/f-decompose` still works.
