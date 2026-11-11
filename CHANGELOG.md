# Changelog

What changed for a project that upgrades, newest first. `/f-setup` shows the entries your install hasn't seen yet. To upgrade: between jobs, run `/f-setup` in your project (see the README, "Updating").

## 2026-11-11

- **A new lens, `lens-loose-ends`, for what a change should also have touched.** The other lenses read the diff; this one reads the rest of the repo: a copy or sibling line left unchanged (two of three log lines updated), a copied piece without its companion (a fixture without the test that proves it, a new log line missing from the docs' list), a new function that already exists, a test that checks less. A local script lists candidates (no network, no model call; JS/TS needs the `typescript` package, Python works without it) and the lens judges them, findings only. `/f-inspect` runs it on nearly every job. In its first live job it raised 3 findings, all accepted, none found by another lens, for about 8 minutes of the foreman's time.
- **QUICK / STANDARD / FULL is now a job's size, not its lane.** QUICK, STANDARD and FULL were called the job's "lane"; they're now its **size** (`**Size:**` in the job header). Older job files that say `Lane:` are still read the same way.
- **Proof matched to risk, and three checks no requirement covers.** Each verification point gets a risk level when the plan is written (P0 safety, money, privacy or data; P1 the main thing delivered; P2; P3 cosmetic): P0 needs executed proof plus a biting mutation probe, P1 executed proof, P3 may pass on a code read. The acceptance ledger gains non-functional checks (speed, security, privacy, cost: evidence or `not touched` and why) and, for jobs that change how an AI feature behaves, a behaviour row: the repo's eval harness on base and head.
- **The site walk gets an outside grade.** After the new session scores its own cold answers, a model from the other family (Codex for a Claude foreman) grades them against the key and the handover, about a minute, read-only (`snippets/site_walk_grade.mjs`). The session re-answers every point it lists; a blocking question it marks wrong is re-read and re-answered before going on, never a wait for you; a wrong key goes into the dev report. Measured on 13 past jobs: no misread handovers, but sessions passed themselves on about half the missed details, and 7 keys were wrong.
- **The Logbook archive finishes by itself.** Past 250 live cards, `/f-archive` used to stop at a preview until you said `--execute`, so in autonomous runs and night shifts it never trimmed. Started automatically, it now runs through, under its guards: every copy checked before anything is removed, the 50 index cards and every ruled-out card kept, archived cards still searchable and restorable. Typed by hand it still previews first.
- **The Logbook looks after itself.** Every close catches up finished jobs that never got cards (three at a time). Every 10th close (the repo profile's "Logbook upkeep every") merges duplicate cards and marks superseded ones with guards (nothing lost: a retired card is kept in the proposal's retired area; every change reversible; never a CRITICAL card) and writes a distill preview. Turning cards into rules still waits for your word: `/f-distill`.
- **Pi, Orca, Greptile and an OpenRouter key are now requirements**, not extras. `/f-setup` checks each and warns loudly about any that's missing, but still finishes. **Greptile reviews every PR**: up to three rounds run right after the PR opens, covered by your word to open it; a fourth round is your word, "greploop". A repo profile can still say `none` for the review bot, with your recorded reason.
- **An autonomous run may split its own job** at scoping when its plan is over the repo profile's new "Max work orders per job" (default 9), with guards: every acceptance line carried verbatim, flagged for your review. `split --rewire` points each dependent job at the child it actually uses.
- **Easier updates.** `/f-setup` pulls the newest package itself, shows what's new from this file, applies on your yes, lists every file to commit (new ones included), and offers new switches such as the parallel test proof. `install.mjs --check` says, read-only, whether a newer package is out; the foreman's site walk runs it at each job's start.
- **Run it on a Linux server.** `SETUP.md` §8b and the site's Cloud setup page: harden the server, Orca as a service, pairing, the night shift on a server. New rule 18: never use sudo; stop and ask. The repo profile gains a "Runs on" row.

## 2026-11-10

- **Faster tests, same proof.** Each work order runs the tests its change affects, before and after (`BEFORE` and `AFFECTED`); a set over half the suite runs once as the whole suite. The whole suite runs at t0 and at the final head. The builder's final head-wide run reuses its own t-final capture.
- **Parallel test workers**, per machine, switched on only after `snippets/parallel_proof.sh` prints PROVED (one process against three runs with workers, identical failing tests, at least 2x faster). Measured on a real project: about 3.6x on a PC, 3.8x on a server.
- **Where the time goes:** every pytest run lists its 30 slowest tests; `snippets/run_times.py` adds up a job's test time for the dev report's new "Test time" line.
- **The one-page board:** the full head, "Needs you" (every decision and debt waiting on the owner), "Now", the fishbone, and every job card, with nothing cut short.

## 2026-11-09

- **Deep Agents add-on:** deepagents 0.7.29 to 0.7.34 (refusals, async subagent notifications, the summarization cutoff, permission inheritance); hidden paths fixed.

## 2026-11-07

- **Saved base:** each base-versus-head base run is saved once per job and reused while its key (base tree, test list, adapter, environment) matches.

## 2026-10-26 to 2026-10-28

- **Board summaries** say in plain words what each job builds; `/f-schedule` writes them from the blueprint task's Outcome.
- **Councils** re-qualified on current models and tools.
