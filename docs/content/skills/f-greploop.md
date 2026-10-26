## It's working if

- It checks the PR's head matches the job's final head before asking for a review.
- It asks with the comment `@greptileai review` exactly, once per round, and waits with the bundled `greptile-wait.mjs`, not a hand-rolled loop.
- Every Greptile finding gets a recorded disposition, even on a 5/5 score.
- Accepted findings go to the builder as test-first repair work orders; the foreman fixes nothing itself.
- Tests, base-vs-head and the acceptance ledger are green at the new head before any push, and pushes are never forced.
- It stops after round 3 at the latest and hands over with each round's score, the open findings and the commits added.
- The PR body is checked against the final diff before it tells you the PR is ready, and it never merges.

## Common questions

### What does "greploop" let it do?

For this PR only and at most three rounds: post the review request and push reviewed repair commits to the PR's branch. Nothing else: no merge, no other branch, no other comment. A fourth round needs your word again. Inside an autonomous run you started for this job, the goal's own words grant this instead.

### Does it resolve Greptile's threads?

No. Threads stay as they are; each round's record says which findings are fixed and by which commit. A finding is never dismissed as noise without saying so.

### Why re-run the tests if Greptile gives 5/5?

Greptile reads the code but runs nothing. A fix made to please it can still break a test or undo a requirement, so every round that changes code re-runs the mechanical checks before the push.

### What if Greptile never answers?

The waiter gives up after 10 minutes and the skill halts and tells you. A failed read is reported as an error, and a score is never invented.

### What if a finding needs a locked decision changed?

That is a halt. It shows you the conflict instead of changing a locked decision, the constitution or a requirement to satisfy Greptile.

### Does it merge when it reaches 5/5?

No. It ends with "5/5, ready for your merge" or "stopped after round N: your call". The merge stays a separate step: your word, or covered by an autonomous run you started for this job.
