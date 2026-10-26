## It's working if

- It wrote exactly one file, `foreman/blueprints/ready/BLUEPRINT-YYYY-MM-DD_<short-slug>.md`, with a status of `ready` or `blocked-on-decision`.
- The plan names the head, the locked decisions (`D0…`), the verification points, the ordered tasks (`T0…`) and every assumption, HALT and outward item, with research and owner decisions listed as such, not hidden inside a task.
- Every unresolved row carries a default if silent, or `HALT until decided`.
- Each task names the paths it owns, its prerequisites, its outcome, what it traces to, and a verify step that uses a gate the repo already has.
- The plan ends with a `## Plan check findings` heading and an empty findings table, ready for `/f-plancheck`.
- `foreman/blueprints/README.md` has a **Ready** entry for it, usually saying it needs `/f-plancheck`.
- It implemented nothing, opened no job, did not run `/f-plancheck`, and staged, committed and pushed nothing.

## Common questions

### Why did it stop and send me back to the survey?

A load-bearing choice was still open: architecture, data model, API, acceptance or scope. It won't invent one to finish the plan; `/f-survey` settles it first.

### Why did it stop before writing anything?

Its first step checks the end-game lock. If the last job's close-out isn't finished, it stops and names the missing steps.

### Does it look at the code?

Yes, to ground the agreement, not to grow it. It confirms the real paths, symbols, tests and gates, and if the code disagrees with what was agreed, it surfaces the conflict instead of rewriting the deal.

### Is one blueprint one job?

No. A blueprint is a project. After `/f-plancheck` and your answers to its findings, `/f-schedule` cuts it into one-PR tickets.

### What if I decide to postpone it?

Move the file to `foreman/blueprints/deferred/` and its index entry to **Deferred**, with the trigger that brings it back. The skill never deletes a blueprint.
