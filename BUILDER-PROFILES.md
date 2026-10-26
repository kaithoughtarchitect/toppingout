# Builder Profiles

What happened with each builder used in this method so far: what failed, how it was caught, and which work-order change helped. **These are observations, not a ranking.** Each builder did one job, on a different ticket, while the work orders were still improving, so none of this compares builders under equal conditions. This file names models because the observations are about them: it is the method's reference, not a job record. Never copy these names into job files, commits or PRs (`RULES.md`, Builder hygiene).

| Builder | Seen on | What went well | What failed, and how it was caught | What helped |
|---|---|---|---|---|
| **GLM 5.3** | one job, a full build (4 work orders) | disciplined, honest reports; planned and built | once re-aimed a mutation probe on a false "implied" claim; some edge-case gaps. Caught in review | the rule that a GREEN probe means a missing test, never a probe to re-aim (`RULES.md`) |
| **GLM-5.3-Flash** (in ZCode, later over a pane link) | one job, 14 work orders, 13 commits | clean commits and full captures from a precise work order; stopped correctly twice, once catching the foreman's own mistake; admitted its own slips | its plan missed the security hard point at the audition (2 of 3 found); 6 edge-case bugs in the first task, before the per-work-order hostile-input checklist existed; explained away two skipped tests; re-aimed a probe; about 8 untested paths found in review. Caught by the audition and in review | settled decisions in every work order (`METHOD.md` §7b): after that, one work order fixed all 6 bugs test-first, independently verified. See `Builder-Playbook.md` |
| **Grok** | one job | new code well proved (18/18 probes, 10/10 database proofs), honest captures | 29 existing tests went red because it never ran the existing tests of the modules it changed. Caught at gate 2 (1 critical, 3 high) | the "run the existing tests before every commit" rule, written after this job; part of the miss was the method's |

**What the observations suggest, untested:** a builder working from fully settled work orders needs more of them (14 against 4 here, on different tickets), so more of the effort moves to the foreman. Whether a cheaper builder plus a busier foreman costs less overall is **a hypothesis, not a result**: testing it needs comparable tickets, a fixed method revision, the same acceptance, and the owner's time measured alongside every model bill.

**Keep a private run manifest** outside every repo if you want to compare builders yourself: per job, the builder and version, harness, method revision, work orders, repair work orders, tokens and cost if known, owner minutes, wall time, and defects by review round.

---

## The audition (for an untried builder)

**When:** for any builder with no completed job in this method. The three hard points are recorded in the foreman's scoping (`templates/SCOPING.md` §2), which the builder may not read.

1. Before reading the builder's plan, the foreman writes down **three hard points**: the places where a wrong plan would ship a real defect (one of them security-class if the ticket has one).
2. It **keeps them out of every file the builder may open**: move hint-bearing notes aside, and list the only files the work order allows the builder to read.
3. At gate 1 it records, per point: **FOUND / MISSED / half-seen**, with evidence.
4. **All three found:** the builder carries the build. **Any missed:** switch before the build work order, *or* keep the builder and have the foreman own every design decision (the work order gives decisions, never questions).

In its audition, Flash missed the identity-credential point, and the owner missed the switch signal. The corrected plan went into work order 3, so there was no damage, and Flash turned out to build well. Lesson: **the audition measures design; a light builder can still be a good hands-on builder.**

---

**Strong and light,** as used below: a light builder needs every decision settled in the work order; a strong one plans unaided. The audition shows which.

## The switch rule, once the build is under way

Switch to a stronger builder **only** if a task review finds:
- a **security-class bug**: credentials, leaked data, trusting unverified input; or
- a **repeat** of something the work order explicitly warned about.

Ordinary edge-case findings are normal. They go test-first into the next work order.

**How to switch:** the foreman writes a new pre-flight for the new builder and makes sure the next work order is self-contained (a state check, all decisions written in, no reliance on memory of earlier work orders). The owner runs the pre-flight in the new builder, then the work order.

---

## Matching work order style to the builder

| | Strong builder | Light builder |
|---|---|---|
| Work order size | one or several tasks per work order (one commit and every check per task) | one independently verifiable outcome per work order (with the `D-` decisions it needs); split tasks that have two |
| Design | foreman writes the plan (form A); an audition may have it write one (form B, plain steps) | foreman writes the plan (form A); work order gives decisions |
| Runners and scripts | builder writes them from a named template | foreman writes them; builder verifies and runs them |
| Edge cases | hostile-input checklist in every code work order | the same, **plus** the coverage gate, G1–G6 and an untested-paths section; tests named up front |
| Commands | exact commands; may batch several tasks per work order | exact commands with a prefix line of variables on every call; one verifiable outcome per work order |
