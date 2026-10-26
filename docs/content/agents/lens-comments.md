## It's working if

- It opens with a verification ledger: an entry for every comment it flags, with the code it read to check the comment's claim.
- The ledger ends with a coverage line: how many comments were in scope, how many it verified, and how many it could not, with the reason.
- Its findings fall under Critical Issues, Improvement Opportunities, Recommended Removals and Positive Findings, each with a `file:line`.
- A comment it could not verify is marked inconclusive, never raised to a Critical Issue.
- If every comment holds, it says so and stops.
- It suggests changes and makes none.

## Common questions

### Do I call it directly, or does `/f-inspect` run it?

`/f-inspect` runs it when the job changed durable comments or documentation prose, as a fresh subagent with no context from the job.

### Does it change code or comments?

It is told not to. Its instructions say it analyses and advises only, and its tools are read and search plus a shell it is told to use only for read-only git.

### Will it ask for more comments?

Rarely. A missing comment is a finding only when the code alone would mislead a competent reader into a bug, and a rename, an assertion or a type cannot fix it. It is more likely to recommend deleting comments that restate the code.

### What does it check first?

Comments that drifted from the code: a changed signature, new control flow under an old description, names that no longer exist, and descriptions of removed behaviour. A stale comment beside freshly changed code ranks highest.
