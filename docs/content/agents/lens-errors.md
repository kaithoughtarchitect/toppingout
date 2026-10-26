## It's working if

- Each finding gives the `file:line`, what the code does, and why it is not designed degradation. A finding that cannot say why is dropped.
- Each finding carries a severity (CRITICAL, HIGH or MEDIUM), a confidence, the error classes it could hide, and a fix in the repo's own style.
- It treats documented fail-open paths as the design, but still flags a fallback that fires with no log line.
- An intent it cannot confirm is reported as inconclusive with a question to verify, not as CRITICAL.
- A clean change set gets a list of the catch sites and fallbacks it reviewed and zero defects.
- It changed no code.

## Common questions

### Do I call it directly, or does `/f-inspect` run it?

`/f-inspect` runs it when the job changed error handling, fallbacks, catches or partial-failure paths. It runs as a fresh subagent with no context from the job.

### Does it change code?

It is told not to: it reports only. Its tools are read and search, plus a shell it is told to use only for read-only git, so this rests on its instructions, not on a lock. The fixes come later, as repair work orders.

### Will it flag every catch that logs and carries on?

No. It first works out which dependency is hard (the result is wrong without it) and which is soft (the result is degraded but valid). A logged fallback on a soft dependency is often correct.

### What does it hunt hardest?

Catch blocks that are too broad, which can hide a typo, a null reference or a failed assertion along with the expected error. It ranks that above an empty catch.
