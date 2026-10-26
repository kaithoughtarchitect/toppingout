---
sample: Where this sits | 1
sample_title: Where it sits
sample_note: The path an idea takes from a brainstorm to jobs, exactly as the skill draws it.
---

## It's working if

- It wrote exactly one file, `foreman/ideas/IDEA-YYYY-MM-DD_<short-slug>.md`, or placed it inside an existing idea directory and said so.
- The file opens with a title, a date, a status saying the discussion is open, a banner saying it is not a plan of record and not executable, and one line on where it came from.
- Settled points appear as `A0…` agreements and open questions as `Q0…`, with the options as they were discussed, not resolved.
- Nothing in it was invented: no locked decision tables, no ordered tasks, no answers to questions you never answered.
- `foreman/blueprints/README.md` has one new bullet for it in the **Ideas** section, naming what blocks promotion.
- The report gives the path, a one-line summary, the counts of agreements, open questions and rejected options, and the blocking questions.
- It opened no job, wrote no plan or code, and staged, committed and pushed nothing.

## Common questions

### Why does it keep my open questions instead of answering them?

Its rule is fidelity over closure. An idea file with honest open questions is complete; one with invented answers is treated as corrupt.

### What if we have actually settled everything?

It says so and points you to `/f-blueprint` instead, so a finished decision doesn't end up as a weaker thinking file.

### How does an idea become a job?

Once its open questions close, it goes through `/f-survey`, then `/f-blueprint`, `/f-plancheck` and `/f-schedule`. The idea file itself is never executed.

### We talked about two ideas. Can it capture both?

One spec per run. If several distinct concepts came up, it asks which one to capture.

### It used to be called something else?

Yes: `/f-idea` still works.
