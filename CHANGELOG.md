# Changelog

What changed for a project that upgrades, newest first. `/f-setup` shows the entries your install hasn't seen yet. To upgrade: between jobs, run `/f-setup` in your project (see the README, "Updating").

## 2026-11-11

- **The Logbook looks after itself.** Every close catches up finished jobs that never got cards (three at a time). Every 10th close (the repo profile's "Logbook upkeep every") merges duplicate cards and marks superseded ones with guards (nothing deleted, every change reversible, never a CRITICAL card) and writes a distill preview. Turning cards into rules still waits for your word: `/f-distill`.
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
