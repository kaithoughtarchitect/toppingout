# f-survey

Turn a rough request into clear decisions, one round of questions at a time.

Command: `/f-survey` (old name `/f-groom`)

Stage: Plan · Before a job · step 1 of 11 in the order of works (Shape the idea)
Source: `skills/f-survey/SKILL.md`

## On site

Before a job, step 1: turning an idea into decisions. It settles each choice by checking the actual code, so the plan written next has no open questions.

## Say it

- "survey this"
- "groom this"
- "this is still vague"
- "tighten this before we build"
- "what am I missing"
- "survey this out loud"

## When to use it

When a request is still vague or has open choices, before anyone writes the plan.

## Not for

The site walk (the machine check at the start of a job, METHOD §2). Not for writing the plan (f-blueprint) or cutting it into tickets (f-schedule).

## It's working if

- Each round opens with the survey layout: your call, settled by the foreman, on site, next round.
- "Your call" holds at most three questions, each with the recommended option first and starred.
- Anything the code or the evidence can answer sits under "Settled by the foreman", with the evidence named, not as a question to you.
- No question in a round depends on another question still open in the same round.
- It stops asking once another answer would only tune implementation detail.
- It ends with one self-contained commission block: in scope, out of scope, acceptance criteria, decisions with their reasons, the likely lane and the exact next action (`/f-blueprint <topic>`, or park it).
- It created no job, plan, code or commit along the way.

## What a round looks like

Every round uses this layout, exactly as the skill prints it. The markers are the skill's own.

```
👷 SURVEY · <topic> · round <n> of <expected>

🚧 YOUR CALL (<count>)
 1. <the question, one line>
    ★ A  <option, one line>   ← recommended
      B  <option, one line>
      C  <option, one line>
    Why A: <one line>

✅ SETTLED BY THE FOREMAN (no answer needed)
 · <a choice made on evidence, one line, with the evidence named>

📐 ON SITE (facts that shape the ticket)
 · <a measured fact, one line>

🔜 NEXT ROUND: <what comes after the owner answers, one line>
```

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

## Connections

- Comes after: f-sketch
- Leads to: f-blueprint
- Uses: model-council, agent-council, speak
