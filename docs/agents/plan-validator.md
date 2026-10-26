# plan-validator

Check a plan against the real code before it's built (used inside f-plancheck).

Stage: Inspect · Used only inside f-plancheck
Source: `agents/plan-validator.md`

## On site

Not used on its own: f-plancheck gives its checklist to every reader.

## When to use it

You don't call it yourself: f-plancheck uses it for every reader.

## It's working if

- The read covers the six checks: files, patterns, dependencies, APIs, scope and risk.
- Each finding names what the codebase actually has, found by reading or searching it, not by guessing.
- Known false alarms (path aliases, Windows letter case, a slug against its readable form, re-export files) come back as advisories with a step to verify, not as failures.
- The plan file is unchanged: the checks only read the plan and the code.
- No git state moved: the contract allows read-only git and forbids every command that writes.

## Common questions

### Do I call it directly?

Not in Topping Out. `/f-plancheck` copies its check contract into one frozen assignment and gives it to every cold seat, each a reviewer from another model family. Reach for the agent on its own only when independence across model families does not matter.

### Why doesn't `/f-plancheck` show a score?

Run on its own, the agent scores the plan out of 100 and recommends Proceed, Revise or Reject, with a veto on any unresolved critical. In Topping Out the seats are asked for findings only, so the score and the veto are not used.

### Does it change the plan or the code?

No. It is told not to implement anything, and its tools are read and search, plus a shell it may use only for read-only git. Applying findings is the plan author's separate act.

### What if it can't confirm a problem?

Then it is not a failed item. A problem it cannot verify by reading the code goes to advisories, with the step that would settle it, and deducts nothing.

## Connections

- Used by: f-plancheck
