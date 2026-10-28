---
name: f-plancheck
description: >
  Validate one plan against the codebase with COLD seats (the owner's standing choice, or the
  one-shot picker the first time and on request: 1-5 models from families different than the Player
  that authored the plan (codex/Astra, Claude, Grok CLIs at $0 subscription;
  OpenRouter doors from a curated roster), so the read is genuinely
  independent. Every seat runs at high reasoning, dispatched in parallel, and
  findings are merged across seats with seat attribution, never voted.
  Read-only but for two residues: the saved seat choice in the repo profile (the first pick, or a change) and the `gate: plancheck` line, written on
  request and always for a plan under or headed for the repo's ready-to-build
  plans folder.
  Use when the user runs /f-plancheck or /cv,
  wants a plan checked before building, or asks for cross-validation. This is
  the cold-seat protocol, not the validator itself, it dispatches
  plan-validator; reach for that directly only when cross-family
  independence does not matter.
  Also answers to its old name, /plan-read.
---

# Plan Check

Validate one plan against the codebase. **Report findings. Never edit the plan**, the
sole exception is the `gate: plancheck` line (see § Gate line).

The deliverable is confidence that the plan was reviewed, not a plan the reviewer
rewrote. Applying findings is the author's separate act.

```
/f-plancheck <plan-path> [--player <id>] [--host <claude|codex|grok|roster-resolvable model id>]
```

`/cv` is an alias. One pass. No score. No `--max-rounds`, no `--auto`.
Scratch: a fresh `plancheck-<timestamp>/` folder under the repo's scratch area (the repo's
constitution or profile names it; `scratch/` at the repo root if nothing does). Below, `{scratch}`
means that folder. Script paths assume the skill is installed at `.claude/skills/f-plancheck/`;
adjust them if the repo installs skills elsewhere.

The **operator** is the human who owns this run; the **Player** is the model that authored the
plan. **The ready-to-build plans folder** (Topping Out: `foreman/blueprints/ready/`) is wherever the repo keeps plans approved for building
(a fixed convention in Topping Out; another repo may name its own).

---

## Operator authorization (LOCKED)

Invoking this **is** authorization for **read-only** external seat access to the named plan
and this repository, including the seat's sandbox, file reads, and any network it needs.
Do **not** re-prompt mid-run for egress, network or repo-read approval. Re-prompt only if
scope expands beyond the read (implementation, workspace-write, git, commit/push, secrets).

---

## 1. Resolve the Player and the host

**Never the Player's own family.** The Player is the model that authored the plan and will
implement it, normally the session host. `--player <id>` overrides. **If it cannot be
resolved with confidence, ask**, a wrong Player turns the read into self-review.

The host is the session running this skill: `--host claude` for Claude Code, `codex` for
Codex, `grok` for Grok Build; a pi-hosted session passes the model pi is running, any
roster id, `cliModel`, slug, or family keyword the roster can resolve (e.g. `--host
gemini-4-argon`). Both families are greyed in the picker and refused by its server,
because a seat from either would be self-review.

Print the resolution before picking: `player: claude-opus-5 → Anthropic · host: claude →
Anthropic · excluded: Anthropic`.

## 2. Pick the seats (Law A: every attended run has the owner's pick: the standing choice, or the picker)

**The owner's standing choice comes first.** If the repo profile's **Plan check seats** row, or the job's opener, names the seats (e.g. "codex, the $0 seat"), that is the owner's pick. **Before dispatch, apply §1's exclusions and the distinct-vendor rule to it:** drop any seat from the host's or the Player's vendor family, keep one seat per vendor, and echo what was dropped (a saved seat can become self-review when the host or the plan's author changes). Write `{scratch}/seats.json` as `{"seats":[{"id":"<roster id>","door":"<roster door>"}]}` from the row's **roster ids**, echo each seat as the picker path does, and dispatch without the picker. If no seat remains, an attended run opens the picker for this run (the row stays as it is) and an unattended run uses the resolver. Otherwise (no standing choice yet), the attended run opens the one-shot HTML picker.
- **The first pick becomes the standing choice.** After the owner's first pick in this repo (no Plan check seats row yet), write it into the repo profile's **Plan check seats** row (the roster ids, the date, "the owner's pick in the picker"; add the row if the profile predates it) and **leave it uncommitted**: the foreman commits it with the job's records (`METHOD.md` §10 step 9); outside a job (a blueprint read), whoever ran the read commits it by explicit path with the blueprint's records, subject only. Tell the owner in one line: "Plan check seats saved as <seats>; say 'change the plan check seats' to pick again."
- **To change it later:** the owner says "change the plan check seats" (or runs `/f-plancheck` and asks for the picker to change them): open the picker, and the new pick **replaces** the row, with its date.
- **For one run only:** the owner says "use the picker this time" (a big blueprint that deserves more seats, say): open the picker; this pick is used for this run and the row stays as it was.
- An unattended run (an autonomous run, a night shift) never opens the picker: it uses the standing choice, or the resolver below when there is none. **A paid seat in the standing choice** (an OpenRouter model, say) counts against the run's spend cap; with no cap named, the run uses only the standing choice's $0 seats and says so in the report (§9) and, when a gate line is written, after its seats (`$0 seats only: no spend cap`).

Seats picked are for that run only, except that the first pick (and a "change") is also saved as above. Do not reuse a
leftover pick file. Do not dispatch without a pick. Do not guess if the picker fails.

```
node .claude/skills/f-plancheck/plancheck-pick.mjs --host <host> --player <player-id> --timeout 1800000
```

**Post the picker's URL in chat** the moment it prints (`PLANCHECK_PICK_URL=…`), so the owner can open it even if the browser tab didn't appear or got buried. The picker waits 30 minutes.

Roster: `.claude/skills/f-plancheck/plancheck-roster.json`, operator-curated, single home
for seats (edit the file to change the pool; do not copy slugs into this skill); rows carry
`id, name, vendor, door, cliModel|slug, effort: "high", pickableAs`; doors are `codex CLI`,
`claude CLI`, `grok CLI` ($0 subscriptions) and `OpenRouter` (pay-per-token,
`OPENROUTER_API_KEY`); Claude-family models are never OpenRouter rows (a roster rule: the
Claude door is the claude CLI). The operator picks 1–5 seats from distinct vendors; every seat runs at high;
the tab says "Seats recorded" and they close it.

Stdout carries `PLANCHECK_PICK_TOKEN=`. Read `.claude/skills/f-plancheck/plancheck-pick.json`
only if `pick.token` matches that token, copy it to `{scratch}/seats.json`, **delete** the
skill-dir pick file, echo host / Player / each seat (`id · door · model · vendor · high`) in
chat. Timeout (exit 2), bind error (exit 1), missing file, or token mismatch: stop. One
picked seat is a single-seat cold read and the report says so. The server binds 127.0.0.1
only, accepts exactly one pick (a second POST gets 409), and refuses a cross-origin or
non-JSON POST (403 / 415, with a `PLANCHECK_PICK_WARN` on stderr), the consent surface is the
operator's tab, nothing else.

### Unattended (no operator present)

When no operator is present, an unattended run, e.g. one triggered by an issue or a CI job,
the picker above is never launched, and it is not opened and filled synthetically
either; a synthetic click recorded as an operator pick is self-authorization wearing a
costume. **With a standing choice, use it** (above, including its family, vendor and spend-cap rules). **Without one, or when none of its seats can run** (all excluded, or all paid with no cap), seats come from a deterministic resolver:
`.claude/skills/f-plancheck/plancheck-seat-resolve.mjs --host <host> --player <player-id>
--out {scratch}/seats.json`. It imports `resolvePlayerVendor` from this skill's own
`plancheck-pick.mjs` rather than re-deriving the family rule, and applies the operator's
fixed claude↔codex rule over this same roster: host claude → seat codex; host codex → seat
claude; any other resolvable host family → claude, falling back to codex; and it refuses
(exit 2, no file written) rather than seat the host's or Player's own vendor family. It
never probes door availability, the existing `plancheck-dispatch.mjs` preflight remains the
single source of availability truth.

The resolver's candidates are drawn **only** from this roster's `cost: "subscription"` rows (the $0 CLI
doors), never a `cost: "openrouter"` metered row, because an unattended run cannot ask
before spending. The resolver writes exactly
`{"seats":[{"id":...,"door":...}]}`; model, vendor, and `effort: "high"` still come from the
roster, never from the seats file it writes. A single resolved seat is the same legitimate
single-seat cold read Law A already allows (`picker.minSeats:1`). Exit 2 means refuse rather
than self-review, turning that refusal into a typed halt is the unattended caller's job, not
this skill's.

## 3. Run the deterministic gates

Mechanical, no model, before spending a seat. **Report what they catch as findings, do not
fix them.**

- Every path the plan names exists, or is explicitly marked as a file to create.
- Every `file:line` citation resolves and says roughly what the plan claims.
- Every CLI flag the plan asserts appears in that tool's `--help`, **including flags it
  claims are absent**. An unverified negative is still unverified.
- Every cited measurement has a surviving artifact, or is labelled unreproduced.
- Every latency, speed or size budget that a VP passes or fails on has a **measured baseline** behind it (a live run, with its anchor named: from which event to which), or is marked `estimate`. An estimate is never a pass/fail VP: the VP records the measured figure until the owner sets a number. Report each unbacked budget as a finding.
- The Done-when block exists, is non-empty, and every line is checkable.

## 4. Freeze one assignment, dispatch every seat in parallel

Freeze **one** self-contained assignment at `{scratch}/assignment.md`: plan path(s), the
ticket's own words (the transcript path, or the text) with the instruction to check every
decision against them as well as against the code, repo
root, the full plan-validator check contract, READ-ONLY, no implementation, no nested
agents, do not open gitignored local credential or machine-config files (`.env`,
`.env.local`, `.mcp.json`, `.claude/settings.local.json`, anything under `~/.pi`,
`~/.codex`, `~/.claude`, `~/.grok`), permitted shell commands read-only only (`git
log|show|diff|status|ls-files|grep|rev-parse|blame`, `--help`/`--version` of installed
CLIs, `pi --list-models`, `grok models`, plus read-only file reads, `cat`, `sed -n`,
`head`, `tail`, `type`, `Get-Content`, and `git show <ref>:<path>`; no build/test/install),
findings-only output shape, the severity token is exactly one of `[CRITICAL]`,
`[MODERATE]`, `[MINOR]`, written at line start and followed by a location (a bare
token or a quoted format list is not a finding), and a check with nothing to report
writes its own line whose remainder is `no findings` (a mention of that phrase
inside prose does not count); a `[SEVERITY]`-free body that says `unverified`,
`could not read`, or `blocked by policy` is a failed attempt even if a
`no findings` line is present; the dispatcher (`hasFindingsShape`) omits any
seat that lacks a line-start severity marker plus location and also lacks a
`no findings` line, or that carries the unread-refusal veto.
**Never** include root's prior conclusions or anything resembling "please agree". Every
seat receives identical bytes and is told nothing about the others. Reading source is
permitted and expected: use a file-reading tool where the door provides one, otherwise
the read-only shell reads listed above (`cat`/`sed -n`/`head`/`tail`/`type`/`Get-Content`)
or `git show <ref>:<path>`. The actual boundary is **changing anything, any write, edit,
or git mutation, and running build/test/install tooling. Reading source itself is not
the thing forbidden.**

**2026-09-23, the read-path wording blocked reads outright.** Even with the codex door's
network access restored (the `--ignore-user-config` fix below), a live cold read
still refused: *"I cannot read the local repository under the stated constraints: no
local file-reading tool or repository resource is available, and reading file contents
through executed commands is prohibited."* It never attempted a read. Controlled A/B
isolation, identical resolver, identical seats file, identical door, only the
assignment wording differed, proved the defect was the wording, not the seat or the
sandbox: "read files with file tools" presumes a file-reading tool the codex `exec` door
does not have, and the permitted-shell allowlist named no read command at all, so a seat
with no native file tool read the pair as "no reading is permitted, by any means." The
clause above now names the door's actual read routes instead of presuming one exists. A
future edit tightening this back to "file tools only" would silently re-break every
codex seat, which is why the reason lives on this page and not only in a work record.

```
node .claude/skills/f-plancheck/plancheck-dispatch.mjs --assignment {scratch}/assignment.md --seats {scratch}/seats.json --out {scratch} --cwd <repo-root>
```

| Door | Dispatch | Log |
|---|---|---|
| codex CLI | `codex exec -m <cliModel> -c model_reasoning_effort="high" --sandbox read-only --skip-git-repo-check -o {scratch}/read-codex-<model>.attempt<n>.last.md -` (assignment on stdin; codex streams its transcript to stderr and writes the final message to the per-attempt `-o` file, the winner is copied to `read-codex-<model>.last.md` and becomes the `.log`) | `read-codex-<model>.log` (+ `.last.md`) |
| claude CLI | `claude -p --model <cliModel> --effort high --permission-mode plan --tools Read,Grep,Glob,Bash --disallowedTools Edit,Write,NotebookEdit --no-session-persistence --output-format text` (stdin; plan mode blocks writes, probed 2026-09-02) | `read-claude-<model>.log` |
| grok CLI | `grok --prompt-file <assignment> --output-format json --cwd <repo> --permission-mode plan --disallowed-tools Edit,Write,MultiEdit,NotebookEdit --allow "Bash(<exact read-only command>)" … --reasoning-effort high --no-subagents -m <cliModel>`, plan mode supplies the built-in read-only shell set and blocks writes; the `--allow` rules (`GROK_READ_ONLY_ALLOW_RULES` in the dispatcher: node/npm version, codex/claude/grok/pi help+version, `grok models`, `pi --list-models:*`) admit the extra read-only commands a cold read needs; headless grok cancels the whole turn on any command outside that set, so an attempt counts only when `stopReason` is `end_turn` | `read-grok-<model>.log` (+ raw `read-grok-<model>.json`) |
| OpenRouter | `pi -p --no-session --no-context-files --no-extensions --no-skills --no-prompt-templates --no-mcp --no-approve --tools read,grep,find,ls --model openrouter/<slug> --thinking high @<assignment> "<one-line instruction>"`, pi's read-only tool allowlist (`--no-mcp` because pi 1.x keeps MCP tools through `--tools`); `OPENROUTER_API_KEY` inherited from the environment, never printed; `pi -p` prints only when the model finishes, so a long silence is not a hang | `read-openrouter-<sanitized slug>.log` |

**2026-09-23, codex door lost `--ignore-user-config`.** A live cold read failed: the
seat could reach the network but read nothing, refusing `blocked by policy`. Cause, proven
by A/B/D testing: the flag discarded `~/.codex/config.toml`'s global `sandbox = "elevated"`,
which is what permits `CreateProcess` on Windows, without it, codex could not read the repo
at all. Removing the flag fixed the read; the operator took the accepted cost knowingly: a
codex seat now inherits the operator's `~/.codex/config.toml`, including whatever model,
effort, MCP servers, hooks and plugins it configures. **The codex door is less hermetic than
the other three**, a reader trusting a codex seat's independence should weigh that.

Log names: `read-<door>-<model>.log`, model lowercased with `/` and anything outside
`[a-z0-9.-]` → `-`. The dispatcher preflights every seat (executable, `--version`, key
presence for OpenRouter, `grok models`), runs all preflight-ok seats in parallel, retries a
failed seat once, except a quota or rate-limit error, a timeout, or an output overflow,
which are surfaced and omitted at once (reason `usage limit: …`; a quota error is never
silently retried), then omits it and names it, pointing at the per-attempt
`.attempt<n>.log` / `.stderr.log` evidence; `dispatch.json` records `assignment_sha256`,
per-seat argv (no secrets), preflight, attempts with `started_at`/`ended_at`, exit code,
bytes, `log_bytes`, `shape_ok`, status. An attempt counts only when its text carries the
findings shape (a line-start `[SEVERITY]` marker plus a location payload, or a
`no findings` line with no unread-refusal veto, a mention of either token in
prose, or a bare token, does not count), a CLI that exits 0 with an
error sentence is a failed attempt, not a seat. Stderr artefacts are secret-scrubbed; the
receipt is written even when a seat's artefact write or an interrupt (`Ctrl-C`) cuts the run
short. Stdout sentinels: `PLANCHECK_DISPATCH_ASSIGNMENT_SHA256=`, `PLANCHECK_SEAT
…`, `PLANCHECK_DISPATCH_OK n/m` (≥1 ok), `PLANCHECK_DISPATCH_NONE 0/m` (exit 3),
`PLANCHECK_DISPATCH_ERR` (exit 1, on stderr), `PLANCHECK_DISPATCH_INTERRUPTED` (exit 130);
the picker warns `PLANCHECK_PICK_WARN …` on stderr when it cannot open a browser (open the
printed URL by hand). Root owns the shell. A run that lost seats down to one is a
single-seat read and says so; a run with zero seats stops. There is no Claude fallback: a
claude CLI seat is only ever picked under a non-Anthropic host, where no Claude subagent can
be spawned, so an omitted claude seat is omitted and named like any other.

**Ask for findings, not a verdict.** Output shape is `[SEVERITY] location, defect /
EVIDENCE / FIX`. Do not request a score or a recommendation.

## 5. Merge, then verify every finding

Collect every seat's findings. **Merge identical defects at the same location into one
entry**, same section/location and the same defect however worded; different defects at
one location stay separate; a defect raised by one seat is kept exactly like one raised by
every seat; record on each merged entry which seats raised it; nothing is dropped, voted, or
averaged. Report raw findings per seat and merged unique findings as two separate counts.

Label each **AGREE** (verified against the codebase, evidence cited) / **PARTIAL**
(direction right, severity or fix wrong) / **DISAGREE** (unverified, false, or out of
scope). Never accept a finding because the model asserted it. Nothing is voted away or
averaged, a 1-of-2 finding reaches the operator exactly as a 2-of-2 does.

Also mark each AGREE finding **mechanism** or **concept**:

- **mechanism**, bugs, wrong API/flag assumptions, unverified claims, missing surfaces,
  broken invariants, unreachable validation, untested paths.
- **concept**, changes what is built, whether it is built, component composition, scope,
  or adds a gate that could cancel the work. Includes a policy written for a *different*
  system that a seat argues transitively binds this one.

Panel agreement raises confidence a finding is **correct**, never that it is **in scope**.

**Cascade check:** Before recording an AGREE factual finding, inspect the surrounding block for reasoning that depends on the wrong value: a step justified by it, a because clause, or a calculation that consumes it. If correcting the fact would orphan that reasoning, name the dependent reasoning as part of the defect and evidence. Report the cascade; do not correct the plan.

**A concept finding may be delegated back to the Player, what it may never be is
assumed.** The operator owns the call and can spend that authority by handing it over:
"you pick", or "you pick, I lean to option 1". Either is a real decision. The disposition
records who exercised it and why:

```
operator: chose option 1
operator: delegated to Player → chose option 1, because <reason>
```

The rule was never "a human must personally decide". It is that a concept decision leaves
a row. A choice made silently, in a plan that then reads as though it had always said so,
is the failure, it is discoverable only by noticing the output is wrong, which is far too
late and depends on someone looking.

## 6. Never edit the plan

The read produces a report. It does **not** revise, condense, restructure or correct the
plan, and it never adds review narration to it, no "what the read found" section, no
finding tags in the body.

The only permitted writes are the repo profile's Plan check seats row (§2) and the gate line: the gate line on request for any plan, and unconditionally
for a plan under or headed for the ready-to-build plans folder (see § Gate line). Applying
findings is a separate instruction, given after the operator has seen them.

## 7. Rewrite trigger

**3 or more AGREE criticals, or any finding against the plan's premise → say the plan needs
rewriting from its intent.** Do not enumerate patches and do not commission a second read.
A plan wrong in three places is not patchable; a second read on a patched plan grades a
document the patching just created.

## 8. Hand off to the Player

Write `{scratch}/findings.md`. **This is the deliverable**, the artifact the Player works
from to improve the plan. The Player may be root in a later, separate act; the separation
is temporal and deliberate, not a claim about who is typing.

One block per unique defect, stable id, **actionable findings first**:

```markdown
### F3 · critical · mechanism
**Where**      plan §4c, line 128
**Seats**      sol · dsflash
**Defect**     Claims the `claude` CLI has no `--effort` flag.
**Verified**   `claude --help` (2.1.222) lists `--effort <level>`;
               `agent-council.mjs:827` already passes it.
**Seat said**  "apply the normalized effort to Claude and include it in the fingerprint",
the seat's suggestion, NOT an instruction. The fix is the Player's.
**Disposition** <!-- Player fills: applied | refused + cite | operator -->
```

Rules for the file:

- **State the defect and the evidence. Do not prescribe the plan's new text.** A handoff
  that dictates wording makes the reviewer the author one step removed, which is the whole
  failure this instrument is shaped against. The seat's suggested fix is carried verbatim
  and labelled a suggestion, because it is sometimes useful and never binding.
- **Concept findings go in their own section, headed `DO NOT ACT, operator decision`,
  and carry no suggested fix at all.** They change what is being built; the Player's job
  is to surface them, not resolve them.
- **PARTIAL and DISAGREE findings are listed too**, under `Not actionable`, with the reason
  each was downgraded. Nothing the seat said is discarded, a finding lost to root's
  judgement is indistinguishable from a finding never made.
- Every finding carries a `Disposition` line, **left empty by this skill**. Filling them is
  the Player's act. A finding with no disposition is unfinished work, and that is the only
  completion signal there is.

The header lines of `findings.md` list the seats (id · door · model · high) and any omitted
seat with its recorded reason.

## 9. Report to the user

Short, on top of the file, the path to `findings.md`, then:

1. `player → seats` resolution (picked, with host/Player exclusions) and any omitted seat
   named with its reason.
2. Counts: gate failures, raw findings per seat, merged unique, AGREE (split mechanism /
   concept), PARTIAL, DISAGREE.
3. **Every concept finding in full**, these need a ruling before the Player proceeds.
4. Whether the rewrite trigger fired.

Readiness is **"every finding has a disposition"**, not a number. Do not rename the plan file
to mark it read.

Keep `read-*.log` and `findings.md` under scratch. Stage nothing. Never edit the plan,
implementation code, commit or push unless separately asked; the exceptions are the saved seat row (§2, left uncommitted for the foreman) and the
gate line below, which a plan in the ready-to-build plans folder always receives.

## Gate line

The plan's only permitted review residue. Written on request, and **always, without asking, for a plan
that lives under or is headed for the ready-to-build plans folder**. That line is the *only* durable
evidence a later run has that this plan was cold-read: a workflow that finds it can skip a second
f-plancheck pass, so a ready plan without it gets re-read from scratch by every later run that uses it.
Writing it is the one exception to "never edit the plan".

**Placement:** on its own line, unprefixed (it must start the line, so `grep -nE '^\*{0,2}gate: (plancheck|plan-read)'` finds it), directly under the plan's `## Plan check findings` heading if it has one, otherwise at the end of the plan's header.

```markdown
**gate: plancheck**, YYYY-MM-DD · seats gpt-6-astra high (codex) · grok-4.6 high (grok) ·
cross-vendor to claude Player · N unique findings (raw a + b): x agreed (y concept) ·
z partial · w disagreed · {scratch}/
```
