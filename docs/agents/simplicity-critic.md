# simplicity-critic

Find the overbuilt parts of a plan and suggest the simplest version.

Stage: Kit · Agents still in use
Source: `agents/simplicity-critic.md`

## On site

Used, optionally, on the foreman's plan, and on a big project being split in f-schedule.

## When to use it

When a plan or a project split looks bigger than it needs to be.

## It's working if

- Its answer opens with a filled lens blueprint: the one-sentence requirement taken from the ticket, and the simplest design that meets it, sketched before any critique.
- Every finding is ranked Blocker, High, Medium or Nit, traces back to a blueprint field, and offers a concrete simpler alternative.
- Claims about the codebase carry a `file:line`; a simpler option it has not confirmed is put as a question, not a finding.
- The verdict comes last: `JUSTIFIED`, `TRIM` or `RETHINK`, with the smallest shippable subset of the plan named.
- `JUSTIFIED` appears when the plan is proportionate. It does not invent findings to fill the report.
- It edited nothing and ran no git command that writes.

## Common questions

### How is it different from the plan check?

The plan check asks whether the plan can work against the code that exists. This agent asks whether the plan is more than you need. When the two disagree, the disagreement is useful signal.

### When does the foreman run it?

It is optional. The foreman may run it on its own plan alongside `/f-plancheck`, and `/f-schedule` runs it on a project cut of more than about ten jobs, to catch a job doing two jobs or two jobs that are really one.

### Does it change the plan?

No. It has read and search tools and a shell it is told to use only for read-only git. It reports; you and the foreman decide what to cut.

### What does `RETHINK` mean?

That a structurally simpler design exists, and building the proposed one would carry a permanent cost. It presents its own sketch as a fresh answer to the requirement, not as a patch to the current plan.

## Connections

- Used by: f-schedule
