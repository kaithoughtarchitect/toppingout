---
name: f-survey
description: >
  Topping Out's first step: turn a fuzzy ask into a decision-complete,
  codebase-grounded commission block by settling every open question first.
  Use when the owner runs /f-survey, says "survey this", "groom this" (the old name), "this is still vague",
  "tighten this before we build", "what am I missing", or hands over work whose
  scope or approach is not yet decided. Add --voice (or say "survey this out
  loud", "talk me through it") to run it aloud as a colleague conversation, one
  short turn at a time. Also answers to its old name, /f-groom. Next step: /f-blueprint. Not the site walk (the machine check at the start of a job,
  METHOD §2). Not for writing the plan
  (f-blueprint) or cutting it into tickets (f-schedule).
---

# Topping Out: Survey a commission

_In Topping Out: lessons live in the Logbook, the next step is `/f-blueprint`, and a survey never runs inside an active job._

Use this before starting or future-planning work when scope, intent, or acceptance is unclear.

## Usage

```
/f-survey [topic]                 # text, batched rounds
/f-survey --voice [topic]         # aloud, as a colleague conversation
/f-survey voice                   # same thing, dashes optional
```

A bare `voice` / `--voice` / `-v` argument is the MODE, never a topic. If the operator seems to
mean a topic actually named "voice", ask which they meant rather than guessing, one short
question costs less than surveying the wrong thing.

## Process

**A new head after a topping out** (`METHOD.md` §11b): start from its `NEXT-HEADS.md` row and the topping out report (what was built, what's carried over); don't re-ask what they already settle.

**Start from the ground investigation** when the end game wrote one (`JOB-<N>-GROUND-INVESTIGATION.md`, `METHOD.md` §10 step 7b): what its section 4 settles is not asked again, and its section 5 questions seed the first round.

**In an autonomous run** (the owner's `/goal autonomous run: <opener>`, `RULES.md` "The one exception"): there is no one to ask. Run every round the same way, but answer each question yourself with its starred recommendation, mark each answer `decided under the autonomous run` in the ticket, and go on. Stop instead only when a question has no clear recommendation, or when an answer would take the job beyond its board entry **and no in-scope option exists**: if the starred pick goes beyond the entry but an option is exactly the board's entry or a settled decision, take that option and flag it for the owner (`RULES.md`). An autonomous run is **not** step 5's "autonomous resolution": never run `/model-council` or `/agent-council` under it unless the goal names a spend cap, and count their calls against it.

0. **First, the end-game lock:** run `node <skills>/f-signoff/endgame.mjs check --root <records root>`. Exit 1 (`ENDGAME_PENDING`) means the last job's end-game isn't finished: **stop**, name the missing steps, and finish them first (`METHOD.md` §10). Exit 2 or 3 is an error, never a pass.
1. **Hidden forks first.** Before the inspect dump, name the 1–3 choices already in the idea: one-off vs repeated; few lines vs a module; what it would break. Inspection may run in parallel. Then inspect the constitution the repo profile names (`AGENTS.md` or `CLAUDE.md`), repository structure, relevant code, current git state, and related Logbook cards, ideas (`foreman/ideas/`) and blueprints (`foreman/blueprints/`). Ask `code-explorer` only bounded questions the root cannot answer efficiently. For an unfamiliar domain or change-class, add one bounded pass on its known failure modes, Logbook first (`/f-search`, including `#ruled-out` cards on the idea's key nouns: a hit is question one, quoting its Why and Revisit if), outside research only if warranted, and carry hits into assumptions, exclusions, or risks.
2. Separate facts, assumptions, decisions, exclusions, and empirical unknowns.
3. Resolve empirical questions with read-only inspection or a bounded probe. For each material product choice, present two or three mutually exclusive options with the recommended option first and a concrete tradeoff.
4. Ask only the smallest batch whose answers change architecture, scope, or acceptance, and order that batch by **dependency** as well as value: a question whose answer depends on another question still open in this round belongs to a LATER round, not this one. Never ask something whose premise you would have to guess. Continue useful exploration while awaiting non-blocking preferences; only the questions downstream of a running probe wait for it, so ask the rest now.

   **Fog vs ticket.** Ask only when you can *phrase* the question now, even if you cannot answer it. If you cannot phrase it, it is not a Q, it is unnamed fog. Do not invent a `[NEEDS CLARIFICATION]` for fog. Park it as not-yet-specified (in-scope, not sharp) or out of scope (beyond this commission). The output block is an **index**: each decision lives in one place; later questions gist and point, they do not restate.

   Render each question exactly like this:

   ```
   ❓ **Q1** - **<title>**: <body, including the two or three options>

   ➡️ <recommended answer>
   ```

   Each round of answers reshapes what is answerable next: settled decisions unblock the questions that depended on them. Recompute the batch and ask the next round. Step 6 governs when to stop.
5. If the user authorized autonomous resolution, classify each remaining load-bearing fork before choosing an instrument:
   - empirical -> use a probe or evaluation;
   - abstract and self-contained -> use `/model-council` (bundled; needs an OpenRouter key);
   - repository-dependent with explicit disclosure permission -> use `/agent-council` (bundled, optional: always needs the pinned Pi CLI and an OpenRouter key; native subscription CLIs are extra transports);
   - repository-dependent without disclosure permission -> reframe it as a self-contained question without repository source or halt. Never disclose automatically.
   Record the decision and surviving dissent.
6. Stop questioning when another answer would only tune implementation detail.

## Voice mode (`--voice`)

Two colleagues working a decision out loud, not an interview. Step 4's dependency ordering still decides what is askable; voice mode changes the register and serves one turn at a time.

**Every turn is one of four things.** Making every turn a question is what produces the interrogation feel.

- **Position**, the default. State what you would do and why, then name the one condition that would change your mind. *"I'd keep this local; the worker can't see the account id, so we'd thread it through three layers to save one call. Unless you're expecting this to get heavy?"* That invites disagreement on a specific axis instead of offering a menu.
- **Question**, when you genuinely have no view. Two options, three at most, named by what they are. Never lettered: "A, B, or C" is untrackable by ear.
- **State update**, no question at all. *"Right, that settles the worker thing, and it kills the queue idea too."*
- **Check**, *"Hang on, let me look at something."* Then go look.

**Conduct**

- **Push back once, then defer.** If an answer looks wrong, say so with the reason: *"Are you sure? That makes the admin table writable from the public endpoint."* Then take their call and move on. Never relitigate.
- **Never manufacture disagreement.** Arguing to sound like a peer is worse than asking questions, because it trains the operator to ignore the pushback that is real. Only argue when you actually think they are wrong.
- **Never answer for the human.** Voice is HITL: they speak for themselves. A turn that asks a question and then fills in their side has broken this.
- **Say when it does not matter.** *"Either works here, pick one."* An interviewer asks anyway because it is on the list; this is the difference between fifteen turns and thirty.
- **Confidence is asymmetric.** *"I'm sure about the auth boundary. The performance side I'm guessing."* Hedging everything equally reads as having thought about nothing.
- **Frame before detail.** Open by agreeing the shape: *"So broadly this is a caching problem?"* Starting at question one of twelve skips finding out you are solving different problems.
- **Carry decisions in the language, not a ledger.** *"So given we're keeping it local…"*, not "Decision A0 recorded."
- **Short turns.** Fifteen to thirty seconds. Peer technical talk is fast back-and-forth, not paragraphs.

**Mechanics**

> **Needs the voice add-on:** the bundled `/speak` skill and `scripts/speak.ts` (+ `bootstrap-env.ts`), with `OPENROUTER_API_KEY` in the repo's `.env` and `npx tsx` available (`SETUP.md` §1). Without them, survey in text.


- **Author for the ear; do not translate.** Write the spoken turn directly. Do NOT compose written prose and pass it through `/speak`, that skill rewrites finished text into an explainer, and an explainer of a question is worse than the question.
- **Speak it and print it.** Write the spoken text to `scratch/survey-voice.txt` (hard cap 4800 chars), run `npx tsx scripts/speak.ts scratch/survey-voice.txt`, and ALSO print the same turn as text. Audio carries the load; text is what the operator looks back at while thinking.
- **Probes stay silent.** Background fact-finding is never narrated. Take the next askable turn while it runs.
- **The output block is text only.** Never speak the commission block, it is a document to keep, not a turn in a conversation.

Length hurts more here: on the page an operator skims past an easy question, in audio they sit through it. Step 6 binds harder in voice mode, not softer.

## Each round: the survey layout

Every round the owner sees uses this layout, in this order, and nothing else. Five fixed markers, one per heading, never in the text:

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

- **🚧 YOUR CALL holds only real questions for the owner**: at most three per round, recommended option first and starred. Anything the foreman can settle from the code or the evidence goes under ✅, never here.
- **One line per option.** The cost or catch of an option goes on its own line, not in a paragraph.
- **No internal codes without words.** Write "the Director of Football's judging stats", not "F4" or "K2"; a code may follow in brackets the first time.
- Queued side work (an idea to capture with `/f-sketch`) is one line under 🔜.

## Output

When every question is settled, return a self-contained block:

- commission and user outcome;
- current problem/evidence;
- in-scope behavior;
- explicit out-of-scope behavior;
- users/actors and trust/security boundaries (auth, data ownership, multi-account isolation where it applies);
- functional acceptance criteria;
- non-functional constraints;
- existing patterns/interfaces to preserve;
- decisions made with rationale;
- open empirical checks;
- likely lane (QUICK / STANDARD / FULL) and why;
- suggested validation strategy;
- options ruled out along the way that could plausibly come back: propose a ruled-out card for each (`/f-card`, tag `ruled-out`), written on the owner's yes;
- known future work this commission leads to (id, title, what it needs), so it goes on the project board with real `needs` (`render_board.py … add`, `METHOD.md` §11);
- exact next action: `/f-blueprint <topic>`, or park it.

**Mid-job?** If a job is active, decline: clarifications belong to that job's scoping, not a parallel survey.

Do not create a job, implementation plan, code, commit, or external side effect unless separately requested.
