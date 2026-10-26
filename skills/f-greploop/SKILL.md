---
name: f-greploop
description: >
  Take an open PR through Greptile the Topping Out way: ask Greptile to review it,
  adjudicate its findings, have the builder fix what's accepted by work order,
  re-run the tests and the acceptance ledger, push on the owner's grant, and
  ask again. At most three rounds, then stop for the owner. Use after the PR is
  open and before "merge", when the owner says "greploop" or /f-greploop.
  Not the lens inspection (f-inspect) or the
  independent inspection (xreview); never merges.
argument-hint: "<PR number>"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Task"]
---

# Topping Out: Greptile rounds

The third review of a job, and the only one on the **open PR**. It runs after the owner's "open the PR" and before "merge" (`METHOD.md` §10 step 2a). Greptile reads the PR and gives a confidence score out of 5; the goal is **5/5**.

**Greptile reads; it doesn't run anything.** So a fix made to satisfy it can score 5/5 and still break a test or undo a requirement. Every round that changes code therefore re-runs the mechanical checks (tests, base-vs-head, the acceptance ledger) before the push. The inspections don't need re-running.

## The owner's grant

This skill starts only on the owner's word **"greploop"** (or `/f-greploop <PR>` typed by the owner), or inside an **autonomous run** the owner started, directly or through a night shift (`RULES.md`, "The one exception"; the goal's words are in the job file). That one word authorises, **for this PR only, for at most three rounds**:

- posting `@greptileai review` on the PR, once per round;
- pushing reviewed repair commits to the PR's branch (normal push, **never force**).

It authorises nothing else: no merge, no tracker transition, no other branch, no comment other than the review request and **one reply on the thread of each routed finding** (step 5). A fourth round needs a new word.

## Never

- More than **three rounds** without the owner. After round 3, stop and hand over, whatever the score.
- Fix code itself. The **builder** fixes, from test-first repair work orders; the foreman reviews them like any work order.
- Push a head whose tests, base-vs-head or ledger aren't green.
- Resolve a Greptile thread: the grant doesn't cover it. Threads stay as they are; the round record says which are fixed and by which commit. Never dismiss a finding as noise without saying so in the round record.
- Change a locked decision, the constitution or a requirement to satisfy Greptile. That's a **halt**: tell the owner.
- Use `@greptile review` (wrong mention) or the Greptile CLI; the trigger is the comment `@greptileai review`, exactly.
- Merge. Merge is always the owner's separate word.

## Each round (1 to 3)

**First, the job file:** `ls foreman/jobs/JOB_*_<slug>.md` must list exactly one file. None means this isn't a job yet (`RULES.md` rule 15): **stop** and say so; the job starts with work order 1, which writes it. A late job file needs the owner's word and states its gaps.

0. **Pin the head.** `gh pr view <PR> --json headRefOid` must equal the job's final head (the head the acceptance ledger passed). If Greptile has already reviewed **this head**, don't ask again (don't spend a credit): take that review straight to step 3, and its findings through step 5 like any other.
1. **Ask for the review:** `gh pr comment <PR> --body "@greptileai review"` (unless a Greptile review of this head is already pending). Ask in round 1 too: on some repos Greptile doesn't review a newly opened PR on its own.
2. **Wait for it with the bundled waiter, never a hand-rolled loop:** `node <skills>/f-greploop/greptile-wait.mjs --pr <PR> --head <pinned head> [--timeout 600]`. It counts either a Greptile review of this head or its summary comment (Greptile edits that comment on a re-review) naming this head, and reads the score from it. Exit 0: the score, as JSON. Exit 2: no review after 10 minutes: **halt** and tell the owner. Exit 3: a read failed: that's an error, never "no review yet". Never invent a score. `--self-test` checks the waiter offline.
3. **Read the score** (`N/5`) and every finding. Record them in the round table (below). **A comment created before this round's request is carried, not new**, even when GitHub re-anchors it onto the new head: compare its `created_at` with this round's request.
4. **The score never skips step 5.** A 5/5 review can still carry findings; each one is adjudicated like any other.
5. **Adjudicate every finding** (`templates/ADJUDICATION.md`, round "Greptile N"): reproduce it against the code at the pinned head, then accept, reject (with the evidence), partly accept, or route (below).
   - A finding that would need a locked decision, the constitution or a requirement changed: **halt**, show the conflict.
   - A **security or concurrency** finding that holds: accepted, and after the fix it goes back to the independent reviewer for a final-diff acknowledgment before merge (`RULES.md` "never sign off your own repair").
   - **Routed:** a finding whose fix needs a file outside the ticket (act 8), and that isn't a security or concurrency defect in this diff, is disposed of in the round it appears as `routed to <board id>` (an existing job's notes, or a new board entry via `add`), with **one** reply on its thread saying where it went. A routed finding needs no repair.
   - **Exit on 5/5 only when every finding of this round has a recorded disposition and no accepted finding still needs a repair.** Then go to the description check. **Under 5/5 only because of routed findings** (every finding still open is routed): exit to the description check too; the PR body's review record gives the score and the routing. In an autonomous run that is not the "under 5/5" stop.
   - Only noise or rejected findings, and not 5/5: record why, and go to the round limit below. Don't loop on noise.
6. **Repairs:** accepted findings go to the builder as test-first repair work orders (`templates/WORK-ORDER.txt`); the foreman reviews each one.
7. **Re-run at the new head:** all captures, the probe harness, both base-vs-head runs (through the repo's test adapter), then update the acceptance ledger. Anything red: **halt**; don't push red.
8. **Push** the repair commits to the PR branch (under the grant). Confirm the remote head moved (`git ls-remote <remote> refs/heads/<branch>` = the new head). The new head is now the final head: write it into the job file's header (**Final head**) and into Phase 7, then re-run the blank check (`METHOD.md` §10 step 1: the header and Phases 1-7, outside code spans; the merge line waits for the merge).
9. **Round limit:** after round 3, **stop and hand over to the owner** with the score of each round, the findings still open, the commits each round added, and the PR link. The owner decides: merge as is, a new "greploop" for more rounds, or rework.

## Before merge: the PR description check (every PR)

Whether Greptile reached 5/5 in one round or three (and in every job, Greptile or not; `METHOD.md` §10 step 2b):

1. Read the PR body, the **final** diff (`gh pr diff <PR>`) and the final gate outputs.
2. Every claim in the body must be true of that diff: what changed (the Greptile repair commits included), the proof run at the final head (the real outputs, not earlier ones), the review record (each Greptile round's score and dispositions), and no builder names.
3. Rewrite whatever is stale (`gh pr edit <PR> --body-file <file>`: this edit is covered by the owner's "open the PR" word for this PR's body). Never leave a body that describes an earlier diff.
4. Only then tell the owner the PR is ready for their "merge".

## Round record (in the job record, Phase 6)

| Round | Head | Score | Findings | Accepted | Repair work orders | Re-run + ledger | Pushed |
|---|---|---|---|---|---|---|---|
| 1 | | /5 | | | | | |

## Output

The PR link, the rounds used (never more than three), each round's score, the findings accepted and rejected with reasons, the commits each round added, whether the ledger passed at the final head, the result of the description check (unchanged and verified, or rewritten), and either **5/5, ready for your "merge"**, **N/5 with only routed findings open (listed), ready for your "merge"**, or **stopped after round N: your call**. Never merge.
