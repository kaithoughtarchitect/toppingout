## It's working if

- If the last job's close-out isn't finished, it stops at the end-game lock and names the missing steps.
- It reads the method files in full: `README.md`, `RULES.md` with its "Foreman rules" section, `METHOD.md`, `OVERRIDES.md`, `Foreman-Playbook.md` and `BUILDER-PROFILES.md`, then the job's own handover and ticket.
- Its first reply confirms the job's facts: the ticket and project, the builder, form A or B, the delivery, the repos and day folder, the gates, and what needs your word this job (and, if you started an autonomous run, which of those acts its goal covers).
- Anything unclear is measured or listed as an owed question, not assumed.
- It lists the Logbook cards in force for the job's area, CRITICAL and HIGH first.
- It runs the site walk, then stops and waits for your "go".
- Every reply ends with the 5-line status block.

## Common questions

### When do I run it?

At the start of every job, before scoping a ticket. It is what makes the session the foreman.

### Does the builder use it?

No. The builder only gets work orders, never this skill.

### What if this is the first Topping Out job in the repo?

There is no shift handover yet. It reads the repo profile instead, measures every fact itself, and marks the handover rows "not applicable: first job".

### Why does it read everything in full instead of summarising?

The foreman makes every design decision and writes every work order, and the builder's discipline can't rescue a wrong decision. Loading the role line by line keeps any of it from being skimmed.

### What if there are a lot of Logbook cards?

More than 250 live cards means it runs `/f-archive` first.
