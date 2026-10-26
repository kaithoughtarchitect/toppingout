---
sample: orca-pi-connect: the foreman ↔ a Pi builder, over Orca | 1
sample_title: The five proofs
sample_note: The five things the link must prove before any work is sent, exactly as the skill lists them.
---

## It's working if

- The builder pane is split to the right of the foreman, in the same tab, and started in the job's worktree with an assigned session ID.
- It puts the pane handle and session ID to you and waits for an explicit yes before sending anything.
- Round 1 gets back the job worktree's absolute path and READY, with the Stop log growing by at least one line for that session.
- Round 2 runs three separate `echo` commands, prints the matching `ORCA_TERMINAL_HANDLE`, replies `DONE`, and the Stop log grows by exactly one line.
- The session file for that ID exists on disk, written during the handshake.
- The report says whether the link is proven, with the handle, the session ID, both rounds, the log counts and the model in the footer.
- During a job it sends only a one-line pointer to each work order, and checks the disk before reading the builder's report.

## Common questions

### Why not just watch for the pane to go quiet?

A long tool call looks the same as a finished turn. The Stop log is the only completion signal it trusts.

### Why does it assign the session ID instead of asking Pi?

Asking Pi for its own ID is not proof of identity. The ID is chosen when Pi starts, or worked out from the session files and a fresh Stop-log line.

### Will it approve Pi's prompts for me?

No. A trust or tool-approval prompt is surfaced to you, never approved with keystrokes. Starting Pi with `--approve` in the job's own worktree is the one deliberate, up-front trust.

### Where are the stop extension and watcher?

In this skill's own folder: `pi-extension/foreman-stop.ts` and `stop-watch.mjs`. Copy `foreman-stop.ts` to `~/.pi/agent/extensions/` on a new machine and restart Pi.

### What if the split reports an error?

An error or timeout from the split means unknown, not failed: the pane often opened anyway. It counts the panes in the foreman's tab again over about 10 seconds. If there is still no new pane, it stops and asks you to look at the tab, and splits again, with a fresh session ID, only after you say there is no new pane. It never opens the builder in another tab.

### Does the link make any decisions?

No. It only carries pointers. Merges, pushes and deletions stay with you.

### It used to be called something else?

Yes: `/pi` still works.
