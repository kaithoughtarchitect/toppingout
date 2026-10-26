## It's working if

- It opens with an Independence statement: automated dispatch or hand-carried, and if hand-carried, whether it already knows the author or has seen the work.
- It states the goal it reviewed against and says whether that goal was stated or inferred.
- Every finding is a numbered row in the claim table (C1, C2 and so on), with a bucket, a severity, evidence and the smallest suggested change.
- Anything it could not check is marked UNKNOWN, not promoted to a defect.
- A clean review is a single `C0 | No findings` row naming what it actually read.
- It ends after the six sections, with no essay, no rewrite and no file edits.
- It refuses, and says why, when asked to review work this same session wrote or supervised.

## Common questions

### Who should run it?

A fresh session of a different model family from the one that did the work. You can paste a `/pack-review` brief into it by hand, or `scripts/cross-review-dispatch.mjs` can run it headless.

### Will it guess who wrote the work?

No. It is told never to guess the author, vendor or model, and not to mention model names even if the artifact leaks one.

### What does it judge against?

Only the stated goal and constraints in the brief. Items on the non-goals or do-not-relitigate lists are settled: it files no claims against them, and if one looks unsafe it says so once under Unknowns.

### What if the brief has no goal?

It asks one short question first. If you tell it to go ahead, it infers the goal in one sentence and labels it as inferred.

### Does it comment on style?

Only when style causes a real defect. It doesn't praise by default or invent nits to look useful.

### What happens to its output?

It goes back to the session that did the work, where `/adjudicate` judges each claim.
