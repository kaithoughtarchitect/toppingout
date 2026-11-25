# Builder Playbook

How to run any builder on a job, so it builds well and doesn't trip. One default for every builder, whatever the model: the foreman plans, and every work order is written the same way.
Drawn from real jobs run with Topping Out. In records, commits and PRs the builder is only ever "the builder".

---

## The one idea

**A builder builds well. It doesn't design well.**

- At gate 1 of one job, a builder's own plan found 2 of 3 hard points. It missed the security one: it trusted a user ID taken from the request and used an ordinary key where a delegation credential was needed.
- Built from the foreman's corrected plan, the same builder produced a clean commit, full captures and an honest report.

So the foreman does all the thinking, and the builder does precise execution. The one exception is a **master builder** job, which the owner chooses at "go": the builder plans too, and the plan check from other model families is what catches the hard points its plan misses (`METHOD.md`, "MASTER BUILDER").

---

## Before the job

1. **Run a pre-flight first.** It checks the builder's environment is ready: shell, git on the target repo, reading and writing outside the project folder, tools, permissions. Nothing starts until it says READY.
2. **Tell the foreman up front how the builder is reached** (hand-carried pointers or a pane link, `METHOD.md` §7e), so work order 1 is written for that delivery. The work order style is the same for every builder.

---

## Every work order

| Rule | Why |
|---|---|
| **Decisions, never questions.** The work order says what to build and how, not "decide X" | judgment is a builder's weak spot |
| **One outcome per task.** A work order may carry one or several tasks, each one independently checkable outcome with its own commit and every check | each outcome is checked on its own, and a review can name the commit that broke it |
| **Exact commands, exact paths, a prefix line of variables on every command** | many builders' shells don't keep variables between calls, and none should guess |
| **Scripts from a named template.** The builder writes the gate runners and scripts by copying the template the work order names (`snippets/run-gates-*.sh`), then runs the checks on them | a copied template plus mechanical checks leaves nothing to guess |
| **Test-first.** The foreman names the tests that must FAIL at the current head; the builder makes them pass | turns "think of edge cases" into "make these red tests green" |
| **The hostile-input checklist** (below) in every work order that writes or changes code | on one job, every bug found in the first task came from this area |
| **"Done when: …" right under the opening line** names the finish line: the tests that pass at head, one commit per task, the report written | the builder can check itself against it before it stops |
| **Opens with a state check, ends with one report file and STOP** | survives a stopped or compacted session |
| **The report opens with "Needs from the foreman"**: none, or BLOCKED on X | a stop that needs a decision isn't buried under a success summary |
| **"Report only what you observed. Do not explain differences away."** | a builder once called two new skipped tests "environment-dependent" when its own new test module caused them |
| **Evidence on every claim.** Every claim in the report cites its evidence: the command run and its output, the commit hash, the test name. A claim without evidence is treated as not done | agents often say they've finished when they haven't; it's the most common failure |
| **A "Not confirmed" section.** Anything the builder couldn't confirm goes there, with where it looked | "where I looked" makes an excuse checkable |

### Make test breadth mechanical

A builder's weakest areas are test breadth and judgment: on one job, four of fourteen work orders only repaired gaps found in review. These four steps turn "think of every edge case" into lists that must be empty:

| Step | In the work order | Why |
|---|---|---|
| **Coverage gate** | run the new module with branch coverage; every uncovered line or branch gets a test, or a reason the foreman already gave | coverage flags untested error paths, guards and legs without anyone having to think of them |
| **Probes per task** | each guard gets its mutation probe in the same work order, run immediately; GREEN = report and STOP | one hidden gap surfaced four work orders late; caught at once, it costs a line |
| **Standard gap checklist G1–G6** | cancellation passes through · deadline on every call leg · every field reaches its destination · every error path mapped and tested · multi-item cases · caller's bad input gets the local typed error | these are exactly the gaps reviews keep finding |
| **"Untested paths" report section** | the builder lists what it did NOT test | builders report honestly when asked; nobody had asked |

Target: roughly 8–9 work orders for a mid-sized ticket, not 14.

**What won't help:** asking the builder to plan more, or to review itself more deeply. Keep the thinking with the foreman and make every check mechanical.

### The hostile-input checklist

Put this in the work order, word for word if needed:

- A required key **missing** → a typed "unreadable" error, never a default and never a different error.
- The **wrong type** in any field → the same.
- **Control characters** in labels or names → refused at the edge, with the same rule the store uses.
- Data that **skipped validation** on the way in (in Python, objects built with `model_construct`) → revalidate at the boundary, nested parts included.
- An error raised while handling another can **carry the first one's payload** with it (in Python, `__context__`, prompt text included) → record a flag, raise after the handler, and check nothing is chained.
- Hash or sign only **validated** data.
- **Time:** no test compares a fixed date or time with today's: it passes on the day it's written and turns every gate red on its own later. Inject or freeze the clock.

---

## Handing work orders over

- **Don't copy prompts out of the chat window.** It wraps long lines and breaks paths.
- **Give the builder a one-line pointer instead:**
  `Read the file <path>, lines A to B only, and carry it out exactly as written.`
- Ask the foreman for pointers, not full text in chat. Over a pane link, the foreman sends the pointer itself.

---

## After every work order

1. Tell the foreman "work order N done" (over a pane link, its watcher sees the stop).
2. It checks the disk first (commits, captures, report file), then reads the report, starting with its "Needs from the foreman" line.
3. It probes the new code itself and writes the findings into the next work order, test-first.

---

## When to switch builders

Switch builders **only** if a task review finds:

- a **security-class bug**: credentials, leaked data, trusting unverified input; or
- a **repeat** of something the work order explicitly warned about.

Ordinary edge-case findings are normal. They go test-first into the next work order.

**How to switch:** the foreman writes a new pre-flight for the new builder (`templates/BUILDER-PREFLIGHT.txt`, `METHOD.md` §3) and makes sure the next work order is self-contained: a state check, all decisions written in, no reliance on memory of earlier work orders. The owner runs the pre-flight in the new builder, then the work order. Because every work order is written this way, a switch costs nothing.

**Don't miss the switch signal.** When the foreman writes a new pre-flight (for example `...BUILDER-B-PREFLIGHT.txt`), that is it asking you to change builder. On one job that was missed, and the old builder ran it.

If you want to compare builders yourself, keep the notes in a private file outside every repo (per job: builder, harness, work orders, repair work orders, owner minutes, defects by review round), never in the method's records (`RULES.md`).

---

## What the builder is given

- **Good:** tasks with a settled design, clear tests and narrow files: repairs, adapters, readers, test suites, mechanical wiring.
- **Keep an eye on:** anything touching identity, credentials, auth, or data that leaves the service.
- **Not the builder's job:** scoping, planning, choosing between designs, deciding what a ticket owns.
