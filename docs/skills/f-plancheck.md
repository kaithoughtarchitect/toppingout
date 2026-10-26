# f-plancheck

Have AI models from other companies read the plan fresh and point out problems.

Command: `/f-plancheck` (old name `/plan-read`)

Stage: Plan · Before a job · step 3 of 11 in the order of works (Check the plan)
Source: `skills/f-plancheck/SKILL.md`

## On site

Before a job, step 3, between f-blueprint and f-schedule: the plan has to pass this check before it's split into jobs. One to five AI models from other companies read the plan side by side, all with the same checklist, and their findings are combined, never voted on.

## When to use it

After a plan is written and before it's split into jobs; also on a job's own plan before its second work order.

## It's working if

- Before picking seats, it prints who wrote the plan and which model family is excluded, so no seat comes from the author's own family.
- On an attended run, it opens a one-shot picker in your browser and posts the picker's link in chat; nothing is dispatched until you have picked 1 to 5 seats.
- Each seat gets the ticket's own words and checks every decision against them as well as against the code.
- It reports the findings of the mechanical checks (paths, `file:line` citations, CLI flags, measurements, the Done-when block) as findings, without fixing them.
- It writes `findings.md` in a fresh scratch folder: one block per defect, each with where, which seats raised it, the evidence, and an empty Disposition line.
- Findings that change what is built sit in their own section, marked DO NOT ACT and left for your decision, with no suggested fix, and the report shows each of them to you in full.
- The plan is untouched apart from one `gate: plancheck` line, which a plan in or headed for `foreman/blueprints/ready/` always gets.
- It staged, committed and pushed nothing.

## Common questions

### Why can't the model that wrote the plan check it?

That would be self-review. Seats come only from model families other than the plan's author and the session host; the picker greys those out and its server refuses them.

### Do the seats vote?

No. Identical defects at the same place are merged and credited to every seat that raised it. A finding from one seat reaches you exactly as one from every seat, and none is averaged away.

### Will it fix the plan for me?

No. It reports defects and evidence, and carries a seat's suggested fix only as a suggestion. Applying findings is a separate step, done by the plan's author after you have seen them.

### When does it say the plan needs rewriting?

When three or more verified critical findings land, or any finding goes against the plan's premise. It then says to rewrite from the intent, rather than listing patches.

### Does it cost money?

The codex, Claude and Grok CLI seats run on subscriptions. OpenRouter seats are pay-per-token and need `OPENROUTER_API_KEY`. An unattended run uses only the subscription seats.

### It used to be called something else?

Yes: `/plan-read` still works, and `/cv` is an alias. Older plans may carry `gate: plan-read`, the same gate under its old name.

## Connections

- Comes after: f-blueprint
- Leads to: f-schedule
- Uses: plan-validator
- Used by: f-shift
