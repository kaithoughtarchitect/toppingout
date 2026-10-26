---
sample: Report | 1
sample_title: One coverage gap
sample_note: Each gap it reports takes this shape, exactly as the agent's instructions give it.
---

## It's working if

- It states the git command that set its scope.
- Each gap names the uncovered behaviour at a `file:line` and a change to the code that no test would catch.
- It reports a gap only at 80 or above for confidence, and only gaps this diff introduced; older holes get one line at most.
- Every recommendation uses the repo's own test harness and names the nearby test to copy.
- When coverage is adequate, it says so in one paragraph and stops.
- It changed no code and no tests.

## Common questions

### Do I call it directly, or does `/f-inspect` run it?

`/f-inspect` runs it when the job changed tests, or changed behaviour without a test. It runs as a fresh subagent with no context from the job.

### Does it write the missing tests?

No. It specifies the missing assertion, with a full snippet only when it is tiny. It has read and search tools and a shell it is told to use only for read-only git.

### How does it find a gap?

For each changed function it imagines small mutations, such as flipping a comparison or dropping a guard. If no test would fail, that mutation is the gap. Error and rollback paths rank first.

### Why does it reject some test suggestions?

A suggestion written for a test framework the repo does not use is a false positive. It reads the nearest existing test first and recommends only that idiom.
