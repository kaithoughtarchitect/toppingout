---
name: orca-pi-connect
description: >
  Connect the foreman's session to a Pi builder in an Orca pane and PROVE the link (a pane the
  foreman opened itself (or one the owner confirmed) + assigned Pi session id, two-round
  handshake, Stop-log and session-file evidence), then send work-order pointers and wait on Pi's
  real turn-end signal. Use for /orca-pi-connect, "connect to pi", "set up the builder pane", or
  before a Topping Out job whose repo profile says builder delivery = pane link. Orca only
  (another pane host: hand-carry the pointers). Proves and uses the channel; never decides or
  approves anything for the owner. Also answers to its old name, /pi.
---

# orca-pi-connect: the foreman ↔ a Pi builder, over Orca

The pane link for a repo whose builder runs in **Orca** (repo profile: builder delivery = pane link). It is the one bundled pane link: the Pi pieces it needs (the stop extension and `stop-watch.mjs`) live in this folder. Proven with pi 0.87 to 1.0 and orca 1.4.

Evidence, not vibes. Every claim is proven by an observable (a Stop-log line, a file on disk, a reply), never by a quiet pane.

```
1 binding   the foreman opened the pane itself (exactly one new pane, on its right, fresh SID, or the old SID in a §1b resume), or the owner confirmed the handle + SID
2 pane      Orca can target that binding and submit prompts
3 hook      Pi's global agent_settled extension logs ONCE per genuine turn end
4 replies   Pi answers, runs tools, and the reply is readable
5 session   the on-disk session file records the turn under the bound id
```

## The wake signal

- Extension: `~/.pi/agent/extensions/foreman-stop.ts`, Topping Out's own. It's global, binds `agent_settled`, fails open, and guards against child agents (`FOREMAN_PI_STOP_OWNED`). The source is bundled at `.claude/skills/orca-pi-connect/pi-extension/foreman-stop.ts`. On a new machine, copy it to `~/.pi/agent/extensions/` and restart Pi.
- Log: `~/.pi/agent/foreman-stops.log`. Lines look like `STOP tag=<cwd folder> session=<id>`; filter by `session=<id>`.
- Watcher: `.claude/skills/orca-pi-connect/stop-watch.mjs`. Exit 0 = turn end, 2 = timeout, 3 = bad args.
- Proved: one headless Pi turn (`pi -p --session-id <uuid>`) wrote exactly one line, and the watcher returned exit 0. Other global stop extensions log to their own files and don't interfere.

```bash
LOG="$HOME/.pi/agent/foreman-stops.log"
WATCH=".claude/skills/orca-pi-connect/stop-watch.mjs"
```

## Halt

- A pane read with a missing or wrong handle can hit **this** session. That's a targeting halt, not builder evidence.
- Dim composer ghosts or predicted "next message" text aren't the builder speaking.
- The TUI can swallow a paste. If the prompt is sitting in the composer, send Enter only; don't resend.
- **Never infer a finished turn from a quiet pane or `orca terminal wait --for tui-idle`.** A long tool call looks identical. The Stop log is the only completion signal.
- **`Timed out waiting for split pane handle` does not mean no pane was created.** Orca timed out waiting for the *handle*; the pane is often already open on the right. A split error is UNKNOWN until §1's wait-and-count says otherwise.
- Pi shows a trust or tool-approval prompt: surface it to the owner. Never blind-approve with keystrokes. (Starting Pi with `--approve` in §1 is the deliberate, up-front trust for the job's own worktree; it is not a keystroke approval.)

## 0. Preconditions

```bash
orca worktree current --json      # must be inside an Orca worktree
echo "$ORCA_WORKTREE_ID"          # set in every Orca pane
pi --version
grep -c "agent_settled" ~/.pi/agent/extensions/foreman-stop.ts   # >= 1; missing file -> install it (see "The wake signal")
grep -n "pi.on(" ~/.pi/agent/extensions/foreman-stop.ts             # must be agent_settled, never agent_end
test -f .claude/skills/orca-pi-connect/stop-watch.mjs                # missing -> re-run SETUP §1's install (an older install kept it elsewhere)
```

`orca agent hooks status` reports Orca's own `orca-agent-status.ts`, which is a different extension and says nothing about the Stop signal.

## 1. Bind pane + session

**Assign the session id; don't discover it.** The builder goes in a pane **on the right of the foreman, in the same tab**, running **in the job's worktree**. Split the foreman's own pane: a split inherits the foreman's worktree (the main checkout) and takes no worktree flag, so the startup command changes folder first:

```bash
WT="<job worktree, absolute>"                                    # cut by the foreman before work order 1 (METHOD §4)
orca terminal show --terminal "$ORCA_TERMINAL_HANDLE" --json     # note the foreman's tabId
orca terminal list --include-visual-layouts --json               # BEFORE: count the panes in that tab
SID=$(node -e "console.log(crypto.randomUUID())")                # a FRESH id for every split attempt (one exception: §1b)
orca terminal split --terminal "$ORCA_TERMINAL_HANDLE" --direction vertical --command "cd '$WT'; pi --approve --session-id $SID" --json
orca terminal list --include-visual-layouts --json               # AFTER: exactly one new pane, on the right, in the foreman's tab
```

**The split is confirmed by the count, not by the command's reply:**
- **A split error is UNKNOWN, never a failure** (the timeout above, or any other error). List the panes again a few times over about 10 seconds (`orca terminal list --include-visual-layouts --json`), counting the panes in the foreman's tab. A new pane there means the split worked: take its handle from the list. Only an unchanged count after those checks means it failed. One immediate look proves nothing: a pane can register a few seconds late (the same rule as rule 12 of the Foreman rules in `RULES.md`, an empty read is not "nothing yet").
- **Never split a second time on your own.** If the wait shows no new pane, **stop and ask the owner to look** at the foreman's tab: the pane list can lag, and the owner can see the screen. Split again (with a new `SID`) only after the owner says there is no new pane. (Learned in job 08: two splits, both "unconfirmed" by the list, both opened a pane.)
- **No fallback outside the foreman's tab.** Never `orca terminal create` (it opens a separate tab), and never start the builder in a terminal that already exists in another tab (the new worktree's own startup terminal included). If the split can't be confirmed in the foreman's tab, stop and tell the owner; never call another layout "a minor deviation".
- **Duplicates** (two or more builder panes): keep **one** pane on the right in the foreman's tab, close the rest, and redo the kept pane's handshake (§3–§5) if any other pane shared its `SID`. The layout rule wins over handshake evidence: a handshake costs a minute to redo. After closing the duplicates, the kept pane still needs the owner's yes (§1: the count was off).
- Orca files the new pane under the foreman's worktree (its `worktreePath` is the main checkout). That's expected. **Pi's own working directory is the proof**, checked in handshake round 1 (§3).

- `--direction vertical` puts the pane on the **right**. Orca's own guide states this backwards.
- `--approve` (Pi 1.0+) trusts the project's own files for this run, so a new worktree doesn't block on "Trust project folder?" and an autonomous run never waits on the owner's Enter. Only for a worktree of the owner's own repo. If the prompt appears anyway (an older Pi), read the pane and surface it to the owner.
- The session file only appears after the first turn: `~/.pi/agent/sessions/<cwd-slug>/<timestamp>_<SID>.jsonl`.
- For a pane the owner started by hand, resolve the id from `ls -t ~/.pi/agent/sessions/<cwd-slug>/` and a fresh Stop-log line. **Never ask Pi for its own session id.**

**A pane you opened yourself binds without asking:** the split ran in this session with a fresh `SID` (or, for a §1b resume, the old `SID` whose session file exists), the count went up by exactly one, and the new pane is on your right in your tab. Say which handle and `SID` you bound, in one line, and go straight to the handshake (§3), which proves the pane is Pi in the job's worktree. **Ask the owner only** for a pane you didn't open (one the owner started by hand), when two panes share a worktree, or when the count or placement is off: then put the handle + `SID` to the owner and get an explicit yes.

## 1b. Resume after the host slept or restarted

The builder pane died with the host, but its Pi session file exists (`~/.pi/agent/sessions/<cwd-slug>/<timestamp>_<SID>.jsonl`): split a new pane exactly as in §1, **with the old `SID`** (`pi --approve --session-id <old SID>`), which resumes its context. Redo both handshake rounds (§3, §4) and confirm the session file grew; the Stop-log count carries on from the old `SEEN` (the log is global, but counted by `session=<SID>`, so the old count still holds). Record the resume in the job file. This is the only reuse of a `SID`: a failed or duplicate split always takes a fresh one.

## 2. Revalidate, then snapshot

Right before every send:

```bash
orca terminal show --terminal <handle> --json    # worktreePath, branch, tabId, incarnationId unchanged since binding
SEEN=$(grep -c "session=$SID" "$LOG" 2>/dev/null || echo 0)
```

If anything moved, go back to §1. Count only the bound session's lines, because the log is global.

## 3. Handshake round 1: identity (no tools)

```bash
orca terminal read --terminal <handle> --limit 1 --json          # keep result.terminal.nextCursor
orca terminal send --terminal <handle> --enter --json --text "Handshake check from the Foreman controller. Reply with exactly two lines: (1) your working directory, (2) the word READY. Do not run any tools or commands."
node "$WATCH" --session "$SID" --seen "$SEEN" --log "$LOG"        # run as a BACKGROUND command so its exit wakes you
orca terminal read --terminal <handle> --cursor <nextCursor> --limit 80 --json
```

Check all of these:
- The reply contains the job worktree's absolute path and READY. Strip ANSI and match the string.
- The bound session's count grew by at least 1, and the new line's `session=` equals `SID`.
- The pane footer shows the model the job expects. Ctrl+P silently cycles models; a changed footer means a changed builder.

## 4. Handshake round 2: tool loop

```bash
orca terminal send --terminal <handle> --enter --json --text "Run three SEPARATE bash commands, one at a time: echo one, then echo two, then echo three. Then print the value of ORCA_TERMINAL_HANDLE, and reply DONE."
node "$WATCH" --session "$SID" --seen <count after round 1> --log "$LOG"
```

Check all of these:
- There were three separate tool calls and `DONE`.
- The printed `ORCA_TERMINAL_HANDLE` equals the prompted handle.
- **The count grew by exactly 1**, not 3. One line per real turn end. If it's more, the wrong event is bound, and every `--seen` downstream is wrong.

## 5. Session file

```bash
ls -l ~/.pi/agent/sessions/<cwd-slug>/*"$SID"*.jsonl    # exists, mtime inside the handshake window
```

The reply, the Stop log and the session file are three witnesses to the same turn.

## 6. Using the link in a Topping Out job (METHOD §7e)

For each work order:
1. Revalidate (§2) and take `SEEN`.
2. Send **only the one-line pointer** to the work-order file, never the pasted text. Mark the file header *"Sent by the foreman as a one-line pointer."*
3. Arm `stop-watch.mjs` as a **background** command right after the send. A foreman that only checks the log during its own turns misses stops made while it's idle. **If the host kills the watcher** (memory pressure), don't restart it in the background unasked; say so in the reply and wait in the **foreground, repeated**: `node "$WATCH" --session "$SID" --seen "$SEEN" --log "$LOG" --timeout-seconds 540`, reading the log before each wait. **At the start of your next turn, read the Stop log yourself** (`grep -c "session=$SID" "$LOG"` against `SEEN`) and act on any new STOP: a reaped watcher must not hide one.
4. On exit 0: **disk check first** (commits, captures, files), then read the builder's report file. The pane text isn't the report. **A Stop counts as the work order's end only when its named report file exists:** a Stop with no report (a tool-call timeout mid work order, say) is not done; read the pane and wait again.
5. On exit 2 (timeout): check `orca terminal show` for `connected: true` and an unchanged `incarnationId`. Never restart the builder on a quiet read.
6. **Any other exit** (1, 3), or a Stop log you can't read: tell the owner the link is down and go hand-carried (METHOD §7e). Never go quiet.
7. **At the end game**, before removing the job's worktrees (METHOD §10 step 4), close the builder **pane**, not just Pi: `orca terminal close --terminal <builder handle> --json`. Pi runs inside the pane's shell, so stopping Pi (or Pi exiting) leaves an empty shell pane behind. Then **check it's gone**: `orca terminal list --include-visual-layouts --json` shows your tab with only your own pane. A pane still there (a bare shell prompt): close it by its handle again; never leave it.

The owner keeps every word `RULES.md` reserves (merge, push, deletions). The link only carries pointers.

## 7. Report

Say whether the link is proven. Include the bound handle and `SID` (assigned; and whether you opened the pane or the owner confirmed it), both rounds, the Stop-log counts before and after, the session file, the model in the footer, and any findings. Don't start builder work without the owner's go.

## Failure handling

- **The log didn't grow after a finished turn:** the wake signal is dead. Check the extension file, its `agent_settled` binding, and Pi's startup output for a load error. Don't proceed, and don't substitute `tui-idle`.
- **The log grew by more than 1 in one turn:** wrong event, or the PID guard (`FOREMAN_PI_STOP_OWNED`) was removed. Fix it before trusting any count.
- **The prompt produced no visible change:** read the pane before resending. It may be mid-turn, or blocked on a trust or approval prompt.
- **Pi's working directory in round 1 isn't the job worktree** (the `cd` failed or was skipped): close that pane and split again with the `cd`. Never use it anyway, and never fall back to `orca terminal create` (a separate tab).
- **The handle printed in round 2 differs, or `incarnationId` changed:** the pane was replaced. Rebind: a pane you open again yourself binds as in §1; any other pane needs the owner's confirmation.
- **Pi never starts:** the pane is a live shell, so read the actual error (PATH, bad `--session-id`, missing provider credentials).
- **The split returned an error or timed out:** it's unknown, not failed. Do §1's wait-and-count before anything else; if still unconfirmed, ask the owner to look; never retry on your own, fall back to another tab, or reuse the `SID`.
- **More than one builder pane exists:** keep one, on the right, in the foreman's tab; close the others; redo its handshake if they shared a `SID`. Record the false start in the job file.
