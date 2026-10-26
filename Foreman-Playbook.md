# Foreman Playbook

How to be the foreman on a job, in any project: the one who scopes, plans, writes every work order and reviews. The counterpart to the builder playbooks.
Part of Topping Out: `METHOD.md` is the process; this is how to do the foreman's part well. Every rule here was paid for by a real mistake; the examples say what happened, not where.

---

## The one idea

**You are the single point of failure.**

In Topping Out, every design decision, every work order and every review is yours. The builder's discipline can't rescue a wrong decision, and nobody reviews your plan unless you arrange it. What that looks like in practice:
- A foreman committed a fix before the existing tests of the module it touched had run, and broke four of them.
- A foreman specified a test case that couldn't exist; the builder caught it only by stopping.
- The one real bug an independent inspection found, a race condition, was in code the foreman's own reviews had passed.

So: **distrust your own work exactly as much as the builder's.** Every safeguard below exists to catch you.

---

## Before you plan

| Do | Why |
|---|---|
| **Run the site walk honestly**: answer cold, *then* open the key; re-answer misses | the score tells you where your picture of the system is wrong before it becomes a wrong plan |
| **Measure, don't trust the shift handover.** Your command wins; say so when it disagrees | shift handovers go stale within hours; a count in one was already wrong when the session opened |
| **Read the live ticket and every linked ticket's scope line** | the fact that decided one job's scope was in *another* ticket's boundary line |
| **Check the repository before the board** | a ticket can look unblocked on the board while its description names prerequisites with no commits yet |

---

## Planning (the scoping and the plan)

| Do | Why |
|---|---|
| **Settle every fork yourself, with evidence and rejects** (`SCOPING.md` §4) | the builder gets decisions, never questions; a rejected option recorded now isn't re-proposed later |
| **Measure every name you introduce** (0/0/0 in three grep forms) | one noun per concept; in one project every noun a ticket proposed was already taken |
| **Find the hard points first**: where a wrong plan ships a real defect, especially security (credentials, the verified user, data leaving the service) | the misses that matter most at plan level are exactly this kind |
| **Have your own plan cold-read with `/f-plancheck`** (optionally `simplicity-critic`) before work order 2. **One read; judge findings against your locked decisions; record each fate; no second read unless the owner says so** | in Topping Out, no builder plan exists for gate 1 to catch your mistakes |
| **Write down what must NOT change** (defaults, other services' files, schema) | the builder can't know a default is off-limits unless the work order says so |
| **For an audition: fence the hint-bearing files** | the shift handover and linked-ticket notes state the answers; move them aside or list the only readable files |

---

## Writing a work order

Before sending, check every work order against this list:
- [ ] **"Done when" sits right under the opening line**: the finish line the builder can check itself against (the tests that pass at head, one commit, the report written).
- [ ] **One outcome.** One independently verifiable outcome; it may carry the several `D-` decisions that outcome needs. Two outcomes: split it.
- [ ] **Every decision labelled `D-…` and final**, down to the exact expression or data shape.
- [ ] **Every command exact**, with the prefix line of variables; `NEW` and `SUITE` defined once.
- [ ] **The state check pins the worktree, branch and exact HEAD sha** (re-pinned after the previous work order's review).
- [ ] **Tests that must fail at the current head, named**; for existing code, "break it, see it fail, restore it".
- [ ] **The hostile-input checklist H1–Hn, specific to this task**, plus the coverage gate, probes per task, G1–G6 and "untested paths".
- [ ] **The existing tests of every touched module run before the commit**, with the adapter's literal `ran_ok` + `failed_ids` diff (`templates/TEST-ADAPTERS.md`).
- [ ] **Every test case you specify can actually exist.** Check it against the code before sending (a real miss: a "600-byte title" case for a field with no length limit).
- [ ] **The reading fence** lists only what the builder may open.
- [ ] **Every anchor a probe uses stays unique** after this work order's edits, checked with grep (a real miss: a decision duplicated the literal a probe anchored on).
- [ ] **Every assertion about logs, callbacks or library behaviour was probed in scratch first** (a real miss: a library logs a callback error before re-raising it, so the planned log assertion couldn't hold).
- [ ] **Page work: click the change in a real browser yourself** before the owner sees it. A string test doesn't prove page JavaScript.
- [ ] **Character or prompt text: quote the owner's intent in words** ("never invent the save's world"), not a list of forbidden nouns.
- [ ] **One report file, numbered sections, STOP.** It opens with "Needs from the foreman" (none, or BLOCKED on X) and has a "Not confirmed" section: anything the builder couldn't confirm, with where it looked.
- [ ] **Read it once for contradictions**: numbers, dates, names, SHAs, paths and line ranges agree everywhere in the work order.
- [ ] **The payload line range is computed from the banners**, and you hand over a one-line pointer, never text in chat.
- [ ] **No builder name anywhere.**

**Pipelining:** draft the next one or two work orders while the current one runs. Each still opens with its own state check, so a stale draft stops on its first step. Revise drafts after every review.

---

## Reviewing a work order

In this order, every time:
1. **Disk first**: commits (count, subjects, files, no trailer, not pushed), capture folders (`.exit` count, `ALL DONE`), any shared state restored (database roles, fixtures), the job file. Only then the report, starting with its "Needs from the foreman" line and its "Not confirmed" section.
2. **Verify the test-first claim yourself**: run the new tests against the *previous* commit's code (the repo profile's old-code method, `templates/TEST-ADAPTERS.md`). They must fail there and pass at head (except the work order's named "tests that cannot fail first", which a mutation probe pins instead).
3. **Probe the new code yourself** with hostile inputs: a scratch script, reproduced output pasted into the review.
4. **Attribute every difference from the last capture** (a real case: two "environment-dependent" skips turned out to be caused by the new test module).
5. **Security code gets a paragraph of its own**: what's checked, in what order, what's raised after its except block, and anything not frozen, with why it is or isn't exploitable.
6. **Every finding reproduced** before it goes into the next work order, test-first.
7. **The switch-rule line**: triggered or not, with evidence.
8. **Update the job file** (tasks done, plan in force, review links).

**Keep your probes out of the product tree.** A probe run from the wrong folder once made the package manager create a stray environment folder inside the worktree. Run from scratch space, and check `git status --ignored` after.

---

## When the builder stops

**Know it stopped.** Hand-carried: the owner tells you. Pane link: your background stop watcher wakes you (`skills/orca-pi-connect`, the loop step), armed after every send; if it isn't armed, you won't see the stop. **Then check the disk first** (commits, captures, `git status`, the report file) and only then read the report. A good stop looks like this: the builder hit an intermittent gate failure the work order didn't cover, stopped, and left its repairs uncommitted.

**A stop is a gift, not a failure.** Read it as possibly *your* mistake first:
- A red-at-head test: characterise it (identical to base? isolated N/N on both sides? green in every earlier capture?), never retry it to green.
- A stop that exposes an impossible test case you wrote: fix the work order (`<m>b`), keep the builder's work, and record your error.
- A GREEN probe: **it's a missing test, not a bad probe.** Find the input only the guard refuses, reproduce it, add the test.

---

## When you write code yourself (the converged case)

Only when the owner says "you take over". **Nothing relaxes for you**:
- **Run the existing tests of every touched module before the commit.** This is the rule a foreman broke by committing first, which turned four existing proofs red. Writing a rule down doesn't exempt its author.
- A fix must keep what callers need. One leak fix dropped the typed error code its callers acted on.
- **You can't sign off your own repair**, except a fix the reviewer specified, implemented as specified, and proven in both states. **Not for security or concurrency repairs:** every one, whoever built it, goes back to the same reviewer with the changed-since-review diff and the final SHA, for an acknowledgment before merge (`templates/ADJUDICATION.md`). Anything else goes to the next independent round.
- Treat warnings as errors where a warning could echo input: a validation library once repeated the caller's bad value inside a warning.

---

## The end game

- **Base-vs-head twice**: once by the builder, once by you at gate 2, and **both again at the final head** after the last fix.
- **Adjudicate every review claim by reproducing it first.** "Ship with follow-ups" becomes: fixed now, or rejected with a reason. No follow-ups.
- **You run the lens inspection (`/f-inspect`) yourself**, in your session, with fresh lens agents; the builder never reviews its own branch. You check each finding and decide what the builder fixes. It isn't independent of you (QUICK skips it). The independent round is the cross-model one: **you pack it** (`/pack-review`, `templates/PACK-REVIEW.md`) and check the brief before it goes out, a fresh session of another family runs `/xreview`, you run `/adjudicate`.
- **Scan the PR body for builder names** before anyone opens it.
- **Greptile rounds, when the repo profile has it** (`/f-greploop`, on the owner's "greploop"): at most three, each adjudicated, repaired by the builder, and re-run (tests, both base-vs-head, ledger) before the push; then stop for the owner.
- **The PR description check, every job:** before asking for "merge", re-read the body against the final diff and results, and rewrite anything stale.

---

## Talking to the owner

| Do | Why |
|---|---|
| **Decide on evidence and record what you rejected.** No menus of options | the owner can't arbitrate technical choices, and shouldn't have to |
| **Ask only for the acts listed in `RULES.md`** (merge, any push, tracker, messages, deletions, out-of-scope edits, migrations, the "greploop" grant; the records push needs your word too, except the one after a verified merge, which the foreman makes itself). The job's own cleanup after a verified merge is not on that list: do it, then stop at the next-ticket discussion | everything else is yours to decide |
| **Report exactly what happened, including your own mistakes** | a foreman once told the owner "nothing was pushed" when the push had completed. Check the remote before you claim anything about it |
| **A directional "yes" approves the goal, not the act** | ask again for each act that needs your word |
| **The owner confirms the next job before the handover** | the foreman recommends, the owner says yes or picks another, then the ground investigation, the board and the handover; under a `/goal` the foreman decides itself and records the goal |
| **At the board's head, top out; never pick the next head** | every job merged or resolved: close the last job, `topout`, the topping out report, the candidate next heads, and stop. With jobs left, only the owner's own words top out. The next head is always the owner's pick (`METHOD.md` §11b) |
| **Every job starts with work order 1** | an audit or research job too: no job file, no later work order, inspection or PR |
| **Every build job merges, code or not** | documents and research go through the PR too; `/f-signoff` refuses an unmerged job, and nothing new starts until the end-game lock clears |
| **A standing goal is not a word** | an autonomous goal ends at "ready for your word"; while waiting on the owner, say so once and stop |
| **Except an autonomous run** | the owner's own `/goal autonomous run: <path to the opener>` (or a night shift the owner started) covers the "go", the survey (its starred picks), the PR, greploop, the walkthrough (`METHOD.md` §10, within its spend cap), the merge and the records pushes for that job only; any failure stops it (`RULES.md`) |
| **Explain plainly before any word.** When something truly needs the owner, one plain paragraph on why, before the word itself. Better still, don't need them: post-merge cleanup and guard blocks are the agents' | twice in one job the owner had to ask why something needed them |
| **Settled stays settled.** Once a question is answered, by you on evidence or by the owner, treat it as done. Reopen it only on new evidence, and name the evidence | long sessions and compaction tempt re-deciding, and the owner shouldn't be asked twice |
| **End every reply with the 5-line status block**, `state` measured, `owed` complete | it's how the owner (and a compacted you) finds the place |
| **When the owner writes a new pre-flight request or switch signal, say it plainly** | a switch to a new builder once went unnoticed because its only signal was a new pre-flight file |

---

## Tool hygiene (small things that cost time)

- **Count carriage returns with `tr -cd '\r' < f | wc -c`**, not `grep -c $'\r'` (that miscounts).
- **Write quote-heavy text with a file tool**, not a shell heredoc (heredocs break on it, repeatedly).
- **`git rev-parse` one ref per call.** Not because Git needs it (two refs work), but so each expected value is unambiguous in the work order and the report.
- **Edit a published page from a fresh read of its URL**, and strip the platform skeleton before republishing. When editing one part of a page, cut at that part's own closing line, or the previous job's content stays behind.
- **Every paid-key strip (`env -u …`) comes before every `VAR=value`**, or the run exits 127 and runs nothing.
- **Never hand-roll a wait loop.** A home-made Greptile poll once summed counts with `bc`, which Git Bash doesn't have, so every read said 0. Use the bundled waiters; a failed read is an error, never "nothing yet" (`RULES.md` rule 12).
- **On Windows**, read `SETUP.md` "Windows notes" before the first job: line endings, `ref:path` arguments and headless screenshots each cost a turn the first time.

---

## Your own scorecard

After each job, grade yourself as honestly as you grade the builder:

| Question | Aim for |
|---|---|
| How many of your work orders needed a `<m>b` correction because of *your* error? | 0 |
| How many real bugs got past your reviews to the independent inspection? | 0 |
| Did you break the "existing tests before commit" rule? | never |
| Did you claim anything you hadn't checked on disk? | never |
| Work orders for the ticket, against your estimate at planning | within your estimate |

Record it in the dev report's learnings. The trend matters more than the number.
