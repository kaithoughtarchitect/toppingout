# spec-validator-fixer

Correct statements in a plan that are provably wrong.

Stage: Kit · Agents still in use
Source: `agents/spec-validator-fixer.md`

## On site

Used at close: f-signoff hands it the job file to correct anything the record says that the code doesn't.

## When to use it

At close, when the job record says something the code doesn't.

## It's working if

- It corrected only false statements about the code as it is today (a path, a symbol, a signature, a count, a default, a script), each with the `file:line` that proves it.
- Statements about the intended future (tasks, files to create, done-when lines) are left alone, even where today's code differs.
- Borderline cases, and fixes that would leave a "because" or a calculation stale, come back as suggested diffs, not applied edits.
- Claims it cannot verify are flagged, never deleted.
- It touched only the spec or plan it was given: no implementation code, no git writes.
- The report ends `CLEAN` or `REMAINING CONCERNS`, with the number of passes used (three at most).

## Common questions

### Does it edit files?

Yes, but only the spec or plan it is handed, and only the safe fixes. It is told never to edit implementation code and never to run git commands that write; the caller stages the result.

### Where does Topping Out use it?

At close, `/f-signoff`'s drift corrections hand it the job file when there is more than a line or two to correct. `/f-blueprint` also calls it on a new plan.

### Won't it rewrite my plan to match the current code?

No. The gap between a plan and today's code is the plan. It fixes only descriptive claims, and where a section's intent is unclear it flags the claim rather than guess.

### What if its fixes keep flipping back and forth?

It restores the original text, stops and reports it. If the file is still not clean after three passes, the report says `REMAINING CONCERNS`.

## Connections

- Used by: f-signoff
