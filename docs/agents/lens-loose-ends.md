# lens-loose-ends

Find what a change should also have touched: an untouched copy, a sibling line, a companion piece, an existing function.

Stage: Inspect · Agents used as review lenses
Source: `agents/lens-loose-ends.md`

## On site

Used as a reviewer inside f-inspect; the only lens that reads the rest of the repo rather than the diff. Its candidate list comes from a local script in f-inspect's folder.

## When to use it

When the changes add functions or edit existing code, which is nearly every job.

## Not for

Bugs in the changed lines (lens-code), not for coverage of new behaviour (lens-tests), not for style-only duplication (lens-simplify). Not for git (the caller owns it).

## It's working if

- It ran the script over the job's range and reported what it listed, including the "first N listed" line when there were more.
- Each finding cites both places: the line the change touched and the place it left alone, or the new function and the existing one.
- Most candidates end up "fine", and each copy that a recorded decision made on purpose is marked "fine (decided)", with the decision cited.
- Step 4 is reported even when it found nothing: which mirrors, companion tests and doc lists it checked.
- It edited nothing and ran no tests: where a finding needs a run, it names the command.

## The summary it closes with

Each finding comes first, in the lenses' shared shape; these four lines close the report, exactly as the agent's instructions give them.

```
lens-loose-ends: <n> findings (<base>..<final head>)
listed: copies <n> · new functions <n> (of <n>) · weaker tests <n> · not scanned <n>
verdicts: needs the same change <n> · reuse <n> · check <n> · fine <n> (decided <n>)
step 4: <n> findings, or what was checked and found nothing
```

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

## Connections

- Used by: f-inspect
