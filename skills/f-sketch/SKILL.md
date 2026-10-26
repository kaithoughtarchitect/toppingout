---
name: f-sketch
description: >
  Capture a discussed-but-not-yet-settled concept from the current conversation
  into one concept spec under foreman/ideas/, a thinking artifact that
  explains the idea as a whole and preserves open questions as first-class
  content, so a later session can resume the discussion without re-deriving it.
  Use for /f-sketch, "capture this idea", "spec this concept out", or when a
  brainstorm reaches a shape worth keeping but decisions are still open. Not for
  decision-complete work (f-blueprint), settling decisions (f-survey), a job's
  own plan (the foreman's PLAN.md), or single Logbook cards (f-card).
  Also answers to its old name, /f-idea.
---

# Topping Out: Capture an idea

Write **one concept spec** that a later conversation can pick up and continue. Do not plan, implement, open a job, stage, commit, or push.

## Where this sits

```
brainstorm → /f-sketch → more discussion → /f-survey → /f-blueprint → /f-plancheck
  → foreman/blueprints/ready/ (plan carries its `gate: plancheck` line) → /f-schedule → jobs
```

`/f-sketch` is the step **before** the survey. Its output is a thinking artifact, not a building artifact: it exists to be understood and discussed, not executed. The contract it fulfills: uncertain directions are deposited in `foreman/ideas/`, never in `foreman/blueprints/ready/`. If the repo's `foreman/blueprints/README.md` sets its own lifecycle rules, follow them.

## North star

**Fidelity over closure.** Capture the concept and the discussion as they actually stand. Do not resolve open questions, invent decisions that were not made, or polish tensions away to make the document look finished.

- Open questions are **first-class content, not flaws**. A concept spec with honest open questions is complete; one with invented answers is corrupt.
- **Fog vs ticket.** A `Q*` is only for a question you can *phrase* now, even if unanswered. If you cannot phrase it, it is unnamed fog, one loose line under open questions or "not yet discussed", not a fake `Q*` with invented options. Out of scope is not fog: record it as rejected or omit it.
- **The file is an index.** Each agreement (`A*`) and question (`Q*`) lives in one place. Concept and later sections gist and point; they do not restate. Do not invent the human's answer to a `Q*`.
- Prefer close paraphrase of settled wording over rewrite.
- If the discussion contradicted itself, record the contradiction, do not pick a side silently.
- Tight and high-signal. Do not pad sections to fill the template; mark thin sections `not yet discussed`.

## Preconditions

1. Identify the concept to capture. If arguments were passed (`/f-sketch <topic>`), scope to that; otherwise use the concept the conversation converged on. If several distinct concepts were discussed, ask which one, one spec per invocation.
2. If the conversation is actually **decision-complete** (no load-bearing open questions), say so and point at `/f-blueprint` instead, do not produce a weaker artifact than the moment deserves.
3. This skill needs no codebase exploration beyond confirming the names/paths it references exist. It is capturing a conversation, not grounding a build.

## Idea file

Write exactly one file:

`foreman/ideas/IDEA-YYYY-MM-DD_<short-slug>.md`

If the concept clearly belongs to an existing idea directory (e.g. it extends a programme already in `ideas/<dir>/`), place it inside that directory instead and say so in the report.

### Header

- **Title · Date · Status:** `idea, discussion open`
- **Banner line:** `Not a plan of record. Not executable. Open questions below are the point, not a defect.` (ideas are not plans of record and must not be executed directly)
- **Origin**, one line: what conversation/context produced this.

### Body (in order)

1. **Problem / motivation**, why this came up; what gap or friction it answers.
2. **Concept**, the idea explained as a whole, in product terms, for a reader with zero context from the originating conversation. This is the heart of the file.
3. **Agreed so far**, points the discussion settled, labeled `A0…`. These are **working agreements, not locked decisions**, the survey may still reopen them. Use the settled wording.
4. **Open questions**, labeled `Q0…`, each with the live options or tension **as discussed**, not as you would resolve them. If a question was raised but never explored, list it bare. Unphraseable fog stays unlabeled, not a hollow `Q*`.
5. **Rejected along the way**, alternatives discarded during the discussion and the stated reason, so future sessions do not re-litigate them.
6. **Relationship to existing systems**, light pointers only: which components, skills, docs, or constraints this touches or must respect. Names and paths, not inventories or interfaces.
7. **What would move this forward**, usually: which `Q*` must close, then `/f-survey` → `/f-blueprint`. Name the blocking questions explicitly.

### What does NOT belong in an idea file

| Excluded | Belongs to |
|---|---|
| Locked decision tables, in/out-of-scope fences | f-survey / f-blueprint |
| Ordered tasks, Done-When, verification gates | f-blueprint / the job's PLAN.md |
| Code grounding inventories, interfaces, migrations | f-blueprint |
| Invented resolutions of open questions | nobody |

## Index

Add one bullet for the new file to the **Ideas** section of `foreman/blueprints/README.md` (create the file with an `## Ideas` heading if the repo has none), matching the existing entry style: path, one-sentence description, ending with what blocks promotion (normally the open questions in the file, then the survey).

## Report

Return:

- idea file path
- one-line concept summary
- counts: agreements captured / open questions preserved / rejected alternatives recorded
- the blocking questions that gate promotion
- any contradictions in the discussion that were recorded rather than resolved

Do not implement, stage, commit, push, survey, plan, or open a job from this skill. When the open questions later close, the idea graduates via `/f-survey` → `/f-blueprint` → `/f-plancheck` → `/f-schedule` (f-plancheck leaves the `gate: plancheck` line that marks the plan cold-read); the idea file's lifecycle then follows the repo's `foreman/blueprints/README.md` if it has one (by default: archive when folded, superseded, or rejected).
