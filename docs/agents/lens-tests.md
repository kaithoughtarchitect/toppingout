# lens-tests

Find changes that aren't properly tested.

Stage: Inspect · Agents used as review lenses
Source: `agents/lens-tests.md`

## On site

Used as a reviewer inside f-inspect; it adds to the test-coverage check every work order already runs.

## When to use it

When tests changed, or changed behaviour has no test.

## Not for

Finding product bugs (lens-code). Not for git (the caller owns it).

## It's working if

- It states the git command that set its scope.
- Each gap names the uncovered behaviour at a `file:line` and a change to the code that no test would catch.
- It reports a gap only at 80 or above for confidence, and only gaps this diff introduced; older holes get one line at most.
- Every recommendation uses the repo's own test harness and names the nearby test to copy.
- When coverage is adequate, it says so in one paragraph and stops.
- It changed no code and no tests.

## One coverage gap

Each gap it reports takes this shape, exactly as the agent's instructions give it.

```
{
  "behavior_uncovered": "<contract, file:line>",
  "mutation_that_survives": "<change no test would catch | n/a>",
  "existing_coverage_checked": "searched <tiers>; nearest test <name> covers <what> not this",
  "confidence_gap_is_real": "<0-100>",
  "criticality_rationale": "<why this rating>",
  "rating": "<1-10>"
}
```

## Common questions

### Do I call it directly, or does `/f-inspect` run it?

`/f-inspect` runs it when the job changed tests, or changed behaviour without a test. It runs as a fresh subagent with no context from the job.

### Does it write the missing tests?

No. It specifies the missing assertion, with a full snippet only when it is tiny. It has read and search tools and a shell it is told to use only for read-only git.

### How does it find a gap?

For each changed function it imagines small mutations, such as flipping a comparison or dropping a guard. If no test would fail, that mutation is the gap. Error and rollback paths rank first.

### Why does it reject some test suggestions?

A suggestion written for a test framework the repo does not use is a false positive. It reads the nearest existing test first and recommends only that idiom.

## Connections

- Used by: f-inspect
