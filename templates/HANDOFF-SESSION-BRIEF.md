# Session brief for the J<N> shift handover

Give this to the `handoff-builder` agent; it refuses to build a shift handover without one. Its defaults already match Topping Out: the shift handover `AGENT-HANDOFF-<date>-job-<N>-<slug>.md` and the answer key `SITE-WALK-ANSWER-KEY-J<N>.md`, both in **`foreman/handovers/`**, and no commits or pushes.

`mode` and the next eight headings are the agent's own required fields; the rest are what this method adds.

mode: full

## Workstream + ticket
J<N>: ticket <KEY>, <goal>. Why this ticket: `<next-ticket decision file>` (project board v<n>, **measured** with `render_board.py <project>/BOARD.json check` when this brief was written, never copied from an earlier handover).

## Where the day ended
The last thing done (e.g. job <N-1> merged as PR #<n>, `<merge sha>`, closed and archived), and any ask in flight.

## Verbal decisions
Choices the owner ratified in conversation, including accepted deviations and rejected options with why (e.g. the builder chosen, whether it's on audition, rulings on inspections).

## Pending approvals
Everything proposed but NOT yet approved, so the new session never treats it as approved: records push, tracker transitions, branch and worktree deletions (outside the post-merge cleanup the foreman does itself), yes/no items.

## Likely next asks
In order: usually "run the site walk", then "go".

## Outward / DB state
What was pushed or sent and to whom; any migration applied, and where; what's live; what's owed.

## Trap candidates
Mistakes this job almost made or made (questionnaire fuel), each as WHEN → DO / DON'T, and why.

## Key file pointers
The dev report, the next-ticket decision, **the next job's ground investigation** (`JOB-<N>-GROUND-INVESTIGATION.md`), the project board link, the archived job file, the runners and probe harness to copy.

---

## Verified state (measured today, with the commands)
- Target repo: `<remote>/<main>` = `<sha>` (`git rev-parse <remote>/<main>` after `fetch --prune`).
- Records repo: head `<sha>`, <n> ahead of origin, <n> dirty files.
- Worktrees: <list>; which one is the **base worktree** for the next job's base-vs-head (the last merged branch, whose tree equals `<remote>/<main>` at the new branch point). Deletable remote heads: <n> (never `<protected branch>`).
- Containers and databases: names, ports, restart policy; which one is disposable.

## The ticket (read live; transcribe verbatim, never summarise; no ticket yet: the foreman writes it first, `METHOD.md` §10 step 8)
<the ticket's own sections, verbatim, in the original language>

## The design forks (F1..Fn)
For each: the question, the evidence for each side (file:line), and what must NOT be decided by default.

## Red lines
The acts listed in `RULES.md`, plus this ticket's own: files outside scope, defaults that must not change.

## The site walk
12 site-walk questions, each testing a fact that would cause a wrong plan if missed; at least 3 test judgment in a new situation.

## How we work
Mode 1; the builder (strong / light / on audition); the pre-flight; work order 1's scope; both base-vs-head runs; never naming the builder. **The new session writes its readiness answers and all its own files in its own day folder** (the date it starts), and reads the shift handover and answer key from `foreman/handovers/`.
