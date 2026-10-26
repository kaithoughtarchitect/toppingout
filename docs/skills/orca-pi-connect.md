# orca-pi-connect

Link the foreman to a Pi builder in the Orca pane beside it, and know when it finishes.

Command: `/orca-pi-connect` (old name `/pi`)

Stage: Run a job · Starting and running a job
Source: `skills/orca-pi-connect/SKILL.md`

## On site

Handing work to the builder in Orca: the foreman sends each work order itself and is woken up when the builder finishes. Comes with Pi's finish signal, starts Pi inside the job's folder without the trust question, and binds a pane it opened itself without asking.

## Say it

- "connect to pi"
- "set up the builder pane"

## When to use it

When the builder runs in an Orca pane next to the foreman.

## It's working if

- The builder pane is split to the right of the foreman, in the same tab, and started in the job's worktree with an assigned session ID.
- It puts the pane handle and session ID to you and waits for an explicit yes before sending anything.
- Round 1 gets back the job worktree's absolute path and READY, with the Stop log growing by at least one line for that session.
- Round 2 runs three separate `echo` commands, prints the matching `ORCA_TERMINAL_HANDLE`, replies `DONE`, and the Stop log grows by exactly one line.
- The session file for that ID exists on disk, written during the handshake.
- The report says whether the link is proven, with the handle, the session ID, both rounds, the log counts and the model in the footer.
- During a job it sends only a one-line pointer to each work order, and checks the disk before reading the builder's report.

## The five proofs

The five things the link must prove before any work is sent, exactly as the skill lists them.

```
1 binding   the foreman opened the pane itself (exactly one new pane, on its right, fresh SID, or the old SID in a §1b resume), or the owner confirmed the handle + SID
2 pane      Orca can target that binding and submit prompts
3 hook      Pi's global agent_settled extension logs ONCE per genuine turn end
4 replies   Pi answers, runs tools, and the reply is readable
5 session   the on-disk session file records the turn under the bound id
```

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
