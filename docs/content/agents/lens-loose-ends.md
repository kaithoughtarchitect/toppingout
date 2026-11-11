---
sample: Output | 1
sample_title: The summary it closes with
sample_note: Each finding comes first, in the lenses' shared shape; these four lines close the report, exactly as the agent's instructions give them.
---

## It's working if

- It ran the script over the job's range and reported what it listed, including the "first N listed" line when there were more.
- Each finding cites both places: the line the change touched and the place it left alone, or the new function and the existing one.
- Most candidates end up "fine", and each copy that a recorded decision made on purpose is marked "fine (decided)", with the decision cited.
- Step 4 is reported even when it found nothing: which mirrors, companion tests and doc lists it checked.
- It edited nothing and ran no tests: where a finding needs a run, it names the command.

## Common questions

### How is it different from the other lenses?

The other lenses read the diff. This one reads the rest of the repo for what the diff should also have touched: the third of three matching log lines, the mirror of a changed rule, the test that came with a copied fixture, the docs list a new log line should join, a function that already existed.

### Does it send code anywhere?

No. The candidate list comes from a local script (`skills/f-inspect/loose-ends/loose-ends.mjs`) with no network and no model call. The lens itself reads the code in the session like every other lens.

### What does it need installed?

Node, which Topping Out already needs. JS and TS files also need the `typescript` package (`npm install -g typescript`). Without it, the script scans Python only and says so, and the lens checks the JS/TS files by hand.

### Won't it flag every copy the plan made on purpose?

It lists them, then marks each one "fine (decided)" when the plan, a `D-` decision or a comment says the copy is deliberate. It raises one only when the copies now disagree on a rule.

### What did it find when it was tried?

In its first live job it raised 3 findings, all accepted, none found by another lens: a function that repeated an existing one, a log line missing from the README's list, and a copied test fixture without the test that proves it works. About 8 minutes of the foreman's time.
