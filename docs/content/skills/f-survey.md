---
sample: Each round: the survey layout | 1
sample_title: What a round looks like
sample_note: Every round uses this layout, exactly as the skill prints it. The markers are the skill's own.
---

## It's working if

- Each round opens with the survey layout: your call, settled by the foreman, on site, next round.
- "Your call" holds at most three questions, each with the recommended option first and starred.
- Anything the code or the evidence can answer sits under "Settled by the foreman", with the evidence named, not as a question to you.
- No question in a round depends on another question still open in the same round.
- It stops asking once another answer would only tune implementation detail.
- It ends with one self-contained commission block: in scope, out of scope, acceptance criteria, decisions with their reasons, the likely lane and the exact next action (`/f-blueprint <topic>`, or park it).
- It created no job, plan, code or commit along the way.

## Common questions

### Will it decide things for me?

It settles what the code and the evidence can answer, and says what it found. It asks you only the questions whose answers change the architecture, the scope or the acceptance. It hands a fork to a council only when you authorise it to settle questions on its own.

### Can I run it out loud?

Yes: `/f-survey --voice` runs it as a spoken conversation, one short turn at a time. It needs the voice add-on (`/speak`, an OpenRouter key and `npx tsx`). Without them, survey in text.

### Why did it stop before asking anything?

Its first step checks the end-game lock. If the last job's close-out isn't finished, it stops and names the missing steps, so new work never starts on top of an unfinished one.

### Can I survey while a job is running?

No. If a job is active it declines: questions about that job belong to its own scoping.

### What happens in an autonomous run?

There is no one to ask, so it answers each question itself with its recommended option, marks each answer as decided under the autonomous run in the ticket, and goes on. It stops instead when a question has no clear recommendation, or when an answer would take the job beyond its board entry.

### How is it different from the site walk?

The site walk is the check at the start of a job. The survey comes before any job exists, and settles what the work should be.
