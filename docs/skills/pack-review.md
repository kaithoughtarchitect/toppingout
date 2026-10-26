# pack-review

Bundle the goal, the rules and the changes into one brief for an outside reviewer.

Command: `/pack-review`

Stage: Inspect · The end game · step 7 of 11 in the order of works (Inspect)
Source: `skills/pack-review/SKILL.md`

## On site

Near the end, the second review: the foreman writes one brief for an outside reviewer once the first review's fixes are in, and checks it before it goes out (templates/PACK-REVIEW.md). It removes anything that names a model or an AI company, so the reviewer judges the work, not who wrote it.

## When to use it

Once the first review's fixes are in, to prepare the brief for the outside reviewer.

## Not for

Not a planning or build pack, and not a review (f-inspect, xreview).

## It's working if

- The output is one fenced block you can copy as it stands, with no commentary before or after it.
- The brief has its sections in order: goal, hard constraints, non-goals, what to review, the diff or artifact, tests or repro, and what not to relitigate.
- Nothing in the brief names a model or vendor: commit trailers and vendor-identifying paths are replaced, not summarised around.
- Paths are absolute wherever the reviewer may run in a different checkout.
- On a huge diff, it packs the file list and the riskiest hunks, and says what it left out.
- It did not review the work, rewrite it, or edit any file.

## Common questions

### Does it review the work?

No. It only builds the brief. The review happens in another session with `/xreview`, and the result comes back here for `/adjudicate`.

### How does the brief reach the reviewer?

Either you copy the block and paste it into the other session by hand, or an unattended run passes it to `scripts/cross-review-dispatch.mjs`, which seats a reviewer from another model family and runs it headless.

### Why strip model and vendor names?

The reviewer must not learn which model did the work, so it judges the claims, not the author.

### Can the same session review its own brief?

No. Running `/xreview` on work this same session produced is never valid. Independence comes from a different session, or a different process on another vendor's CLI.

### Where does it fit in a job?

In the end game: the foreman runs it for the independent inspection, after the lens inspection's fixes, and checks the brief before it goes out.

## Connections

- Comes after: f-inspect
- Leads to: xreview
