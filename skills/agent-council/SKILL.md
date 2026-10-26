---
name: agent-council
description: >-
  Settle a load-bearing, repository-grounded design decision with a
  cost-aware Focused, Balanced, or Full panel: the current host plus two,
  three, or five independent external agents routed through qualified native
  subscription CLIs or pi-headless seats, followed by adversarial
  reconciliation and a separate repo-aware evidence-and-synthesis audit. Host
  lineage is automatically removed from the external panel. Use when models
  must inspect, trace, test, or probe the codebase to judge a genuinely forky
  architecture, security, data-model, or interface choice. Not for a decision a
  written brief can carry without repo access, that is the cheaper model-council.
  Do not use for questions already decidable by repository facts or an evaluation.
---

# Agent Council v3

Settle a genuinely forky repository-dependent decision with a resolved assurance profile: the
current host/chair plus two, three, or five external investigators, followed by a distinct
independent auditor.
Native Claude and Grok subscription transports are preferred when qualified and authenticated;
every other seat runs as a `pi-headless` OpenRouter agent. Read
[references/contract.md](references/contract.md) completely before use; it is the normative
protocol.

## Non-negotiable boundary

- Every resolved profile requires its exact decision-seat count and one non-participating auditor.
  Never degrade, silently substitute, or call a partial resolved panel Agent Council.
- Select the qualified host profile matching the actual runtime. The resolver rejects the host's
  vendor/family/model/correlation lineage from external seats, then admits the first qualified
  collision-free replacement. Thus Codex hosts omit GPT/Astra, Grok hosts omit Grok, Claude hosts omit
  Claude, and Gemini hosts omit Gemini. Host identity is registered, not cryptographically attested.
- Seats receive separate writable copies of one sanitized frozen corpus. They can read, search, and
  edit experimentally below an inert `workspace/` wrapper, but have no shell, web, LSP, MCP,
  plugins, custom tools/agents/commands, skills, nested agents, package installation, automatic
  update/share/download, live-worktree, or external-directory capability.
- Models never execute edited code. Existing offline gates run only through the runner's pristine,
  exact-argv broker and are represented by receipts.
- Source disclosure is authorized by the exact manifest SHA-256, never a boolean.
- Resolve arguments from validated repository citations and runner receipts, not vote counts.
  Preserve consequential dissent.

## Choose the assurance profile

Choose the smallest profile that matches the consequence of being wrong, and state the choice to
the user before preparation:

- `focused`, host + 2 external seats. Use for bounded, reversible choices with a narrow evidence
  surface.
- `balanced`, host + 3 external seats. This is the normal skill-driven choice for architecture,
  data-model, and interface forks where independent scrutiny matters but Full would add
  disproportionate cost.
- `full`, host + 5 external seats. Use for security/privacy boundaries, irreversible migrations,
  public contracts, high blast radius, or unusually ambiguous evidence.

Do not omit `--profile` in a new skill-driven run. The runner's omitted-profile behavior remains
`full` solely for safe V2 continuity. The roster is frozen into the disclosure manifest; never
expand or shrink it mid-run. A profile or seat change requires a fresh preparation and approval.

Normally let the resolver choose the exact models, preferring qualified native subscriptions.
When the user or the decision needs a particular mix, use repeated `--prefer-seat <profile-id>` or
`--exclude-seat <profile-id>`. Use repeated `--seat <profile-id>` only for an exact roster; its
count must match the profile. `--auditor <profile-id>` pins the separate auditor.
`--transport-policy subscription-first` is the only accepted value and the default: qualified
native CLI seats rank ahead of `pi-headless` seats, with pool order as the deterministic tiebreaker.
Every explicit choice remains subject to host-lineage, pairwise-independence, availability,
qualification, and auditor-separation checks.

### Let the user seat it (optional)

Two paths lead here and they are not interchangeable. When the user names specific model ids in
chat, translate those into `--seat` / `--prefer-seat` / `--exclude-seat` directly, do not make them
click. Open the picker when the user wants to browse and choose interactively, or when you do not
know which models they want and would otherwise be guessing:

```
node .claude/skills/agent-council/scripts/agent-council-pick.mjs --host <host-profile-id> [--profile balanced]
```

It serves the console on `127.0.0.1` only, opens one tab, accepts exactly one pick (a second POST
gets 409), refuses a cross-origin or non-JSON POST (403 / 415), and exits. Stdout carries
`AGENT_COUNCIL_PICK_URL=`, `AGENT_COUNCIL_PICK_FILE=`, `AGENT_COUNCIL_PICK_TOKEN=` and, on success,
`AGENT_COUNCIL_PICK_ARGS=`, the exact `prepare` flags to pass on. Read the pick file only if its
`token` matches the printed token, echo profile / each seat / the auditor in chat, then **delete
it**. Timeout (exit 2), bind error (exit 1), missing file, or token mismatch: stop and ask; never
invent a roster from a failed picker.

The picker writes its receipt **outside** the skill directory (default: the OS temp dir) because
the skill's file inventory is kept exact (a repo's readiness check may assert it);
`--out <file>` must also stay outside it, and the picker refuses to start otherwise or
to delete a file it did not write. The tab refuses what the resolver refuses, it imports the
resolver's own `profileCollisions`, so a pick it accepts passes `prepare`'s collision,
auditor-separation and qualification checks. **Availability is the exception:** `prepare` resolves
against a live pi model catalog plus whichever native CLIs preflight, so an uninstalled `grok-cli`
leaves `grok` seatable in the tab and refused at `prepare` with `SELECTED_MODEL_UNAVAILABLE`. Treat
that as the one refusal the tab cannot predict, not as a bad pick.

`AGENT_COUNCIL_PICK_ARGS=` is a complete flag set including `--host-id`, so the chair every
collision was judged against is pinned; pass it through rather than substituting your own host.

**The picker never approves disclosure.** It chooses who sits. The disclosure manifest does not
exist until `prepare` has run over these seats, and approving it by exact SHA stays a separate act
on the command line. Two consents, two surfaces, in that order.

## 1. Frame neutrally

Write a decision brief with two to four credible options, constraints, requested repository evidence,
and a strongest-self-counter requirement. Do not include the chair's lean.

Tell the user which resolved seats use native subscription CLIs and which are pi-headless
OpenRouter seats, reading `seatTransports` from the `prepare` output rather than inferring it from
model names. Grok 4.6 and Claude Opus 5 are native when their qualified transports pass
preflight; every other seat, Gemini 3.8 Flash with the `high` variant included, is served by a
`pi-headless` OpenRouter profile. Claude-family models are never routed through OpenRouter, so the
Claude seat is native or absent. Grok is not the same case: the pool also carries a separate
`grok-openrouter` row, so a `grok-cli` preflight failure reseats Grok as a **pay-per-token**
`pi-headless` OpenRouter seat instead of removing it. Say so explicitly when it happens.
Approved repository material is sent to the resolved external decision models and the auditor.
Preparing locally is not disclosure. No model call occurs until the user approves the returned
manifest digest.

## 2. Prepare and inspect the disclosure manifest

Map the actual chair runtime to its registered host profile:

- Codex/GPT-6 Astra → `host-openai-gpt-5-6`
- Claude Opus 5 → `host-anthropic-claude-opus-5`
- Gemini 3.8 → `host-google-gemini-3-6`
- Grok 4.6 → `host-xai-grok-4-5`

Pass the actual host profile and an explicit assurance profile. Prefer automatic selection unless
there is a concrete reason to constrain the mix; the lineage-aware resolver always performs the
host swap and independence checks.

From this skill directory:

```text
node scripts/agent-council.mjs prepare --repo <repo> --brief <brief.md> --host-id <qualified-host-id> --profile <focused|balanced|full> [--prefer-seat <profile-id>] [--exclude-seat <profile-id>] [--seat <profile-id>] [--transport-policy <subscription-first>] [--auditor <profile-id>] [--probe <logical-gate-id>]
```

Optional disclosure inputs are exact paths: `--exclude`, `--approve-binary`, and the separately
approved `--approve-history-diff`. Free-form commands are not accepted. Preparation:

- preflights pi against its pinned version and its OpenRouter model catalog, plus the authenticated
  native Claude and Grok transports, then validates the host-aware resolved roster and separate
  auditor before any model invocation; an absent or off-pin pi is a hard stop, while an unavailable
  native CLI is reported in the `prepare` output's `unavailableTransports` and only removes its own
  models, that field is `prepare` output only, absent from `inspect` and from durable evidence, so
  capture it if it matters;
- freezes tracked plus untracked/non-ignored current-tree bytes; ignored files are omitted by repository enumeration;
- secret-scans bounded history subjects, paths, and separately approved diff bodies, then materializes
  that bounded history packet inside the canonical corpus before its digest and every seat copy;
- rejects secrets, links, dangerous formats, path collisions, unsafe binaries, and oversize input;
- excludes the reserved `.agent-council-evidence` tree from disclosure and wraps every seat corpus
  below `workspace/`, keeping all configuration and instruction files citable but inactive;
- resolves selected logical gates to fixed platform executables/argv and hashes them;
- creates one immutable corpus and one separate synthetic-Git copy per resolved external seat.

Record `runFile`, `manifestSha256`, and `chairRound1Nonce`. Inspect the manifest with `inspect`. Obtain
explicit user approval for that exact digest; any input drift requires a new preparation/approval.

Legacy `--host-family`, `--approve-source-sharing`, and `--allow-command` are v1 migration errors.

## 3. Blind Round 1

Before reading external positions, write `chair-r1.json` as the schema-v2 chair record using the
returned nonce. Round 1 requires `role: "chair"` and `movement: null`.

Run every command that may launch or terminate an external model process (`round1`, `round`,
`retry`, `audit`, and recovery `abort` when `inspect` shows owned processes) with the host's
external-network and child-process-management authority. In Codex, invoke the shell tool with
`sandbox_permissions: "require_escalated"` and a narrowly scoped user-facing justification.
Managed default shells can allow cached CLI/model-catalog preflights while blocking live egress
and Windows `taskkill`. `prepare` and `inspect` do not need this authority merely for Agent Council.

```text
node scripts/agent-council.mjs round1 --run <run.json> --chair <chair-r1.json> --approve-manifest-sha <sha256>
```

Authorization is checked against the current manifest and corpus. Selected pristine probes run once
through the broker. After exact manifest approval, a credential-free bounded reachability check runs
before any model attempt is opened. `EXTERNAL_NETWORK_PREFLIGHT_FAILED` means no model process was
started; rerun the same command with the required host authority after checking external connectivity.
The resolved external transports then run concurrently and return nonce-bound structured
JSON. pi seats write that response file themselves; native structured output is normalized into the
same response-file contract.
Each seat root also receives `AGENT_COUNCIL_DISCLOSURE.json`, beside the prompt and outside
`workspace/`: the prompt names the approved inventory instead of embedding it, because embedding it
made a 691 KiB Round-1 prompt on a 2,055-entry repository against a 1.4 KiB pointer, and every byte
had to be echoed back through the seat's `--mode json` event stream against the 4 MiB raw-output
cap. Rounds 2 and 3 add `AGENT_COUNCIL_ROUND_CONTEXT.json`; the auditor root gets
`AGENT_COUNCIL_AUDIT_BUNDLE.json`. The brief, the required record, the nonce identity, and every
citation rule stay inline, and the pointer carries the entry count and corpus digest so a seat can
tell it read this run's inventory. These files are outbound disclosure: they pass the prompt's
secret scan (`SECRET_IN_OUTBOUND_CONTEXT`, naming the file and detector) and are deleted and
rewritten before every attempt, so a retry never reads the previous attempt's context.
When the resolved panel contains the native Claude seat, Round 1 makes one minimal structured,
tool-disabled subscription call to prove the exact model is entitled before the other seats spend;
panels with no `claude-cli` seat skip it, and it is not repeated in later rounds.
Prose, refusal, malformed schema, invalid citations, or fabricated receipt ids are explicit failed
attempts, not positions. Failure codes are written here in the runner's raised form; the persisted
attempt record lowercases them (`TRUNCATED` is stored as `truncated`). A pi seat that exhausts its
output budget before writing the record, a stream stop reason of `length` with a missing or
unparseable response file, is the named `truncated` attempt with failure code `TRUNCATED`, and the
runner retries it once automatically inside the same round with a compact-record prompt, spending
the second of that seat's two attempts. A second truncation leaves the seat named and unresolved,
the round `failed`, and a further `retry` reports `SEAT_ATTEMPT_LIMIT`; there is no degraded panel.
`PI_NO_ASSISTANT_TURN`, a stream with no assistant turn at all, is named for you instead of
retried automatically; recover it with the `retry` command below.
Otherwise retry the same seat at most once:

Every selected seat attempt is persisted as `running` before invocation. The same closed record is
settled afterward; an unresolved running attempt or process-ownership record blocks relaunch.
Launch and persistence are not OS-atomic: the attempt is durable before spawn, and PID/stable
identity ownership must persist through the callback before a result is accepted. Missing identity
forces immediate owned-handle termination and rejects the work.
If that ownership persistence callback fails, the live owned handle is terminated immediately;
unverified termination remains explicit recovery evidence rather than being accepted as work.
Process ownership is first written to a strict manifest-bound recovery ledger under the runner's
temporary root. Primary run-state mutation rolls back on write failure; every later command and
abort merges the exact recovery record before deciding whether work may continue.

```text
node scripts/agent-council.mjs retry --run <run.json> --round 1 --seat <id>
```

## 4. Peer-blind falsification and conditional cross-examination

Round 2 is mandatory. Each external seat sees only the neutral brief and its own Round-1 record; it
does not see peers or the chair recommendation. Write a structured `chair-r2.json` with a changed or
unchanged movement record.

```text
node scripts/agent-council.mjs round --run <run.json> --number 2 --chair <chair-r2.json>
```

After all resolved Round-2 records validate, the core derives the Round-3 trigger. Run Round 3 only when
`inspect` reports `round3.required: true`:

```text
node scripts/agent-council.mjs round --run <run.json> --number 3 --chair <chair-r3.json>
```

Round 3 exposes neutrally labelled consequential conflicts. It cannot be manually forced or
suppressed. An incomplete opened round blocks audit, and there is no fourth round.

## 5. Independent full-trajectory audit

Write the final structured chair record for the latest completed round and the proposed synthesis:

```text
node scripts/agent-council.mjs audit --run <run.json> --chair <chair-final.json> --synthesis <synthesis.md>
```

The separate auditor receives a freshly recreated/hash-verified corpus plus every attempt,
failure, retry, round record, manifest, receipt, bounded diff, movement, conflict, convergence,
dissent, and synthesis. Its structured verdict is `FAITHFUL` or `NEEDS-REVISION`.
Every finding claim id and evidence reference must resolve against the complete persisted audit
bundle. Claims use the bundle's bounded, collision-safe `r{round}:sha256:{digest}` reference index,
which preserves the raw round, seat, and claim ids alongside each qualified id; raw claim ids and
unknown references are rejected rather than accepted as auditor prose.
If a crash leaves a completed audit attempt without history, resume validates and adopts its
existing response before any new snapshot rewrite or model call, but only when the persisted
`auditInputSha256` still matches the exact bundle, revision, nonce, and cycle. Changed chair or
synthesis input uses the remaining bounded attempt. Only an absent/invalid response may do so;
unexpected adoption I/O or validator errors propagate without another model call.

For `NEEDS-REVISION`, answer every finding `ACCEPT` or `DEFEND` using existing evidence only and
provide replacement synthesis in `audit-revision.json`:

```text
node scripts/agent-council.mjs audit --run <run.json> --chair <chair-final.json> --revision <audit-revision.json>
```

One synthesis-only revision cycle is allowed. New evidence, manifest/roster/probe change, or a second
adverse verdict becomes `RESTART_REQUIRED`. An adverse or malformed audit never enables finalization.

## 6. Persist before cleanup

After `FAITHFUL`, write the final record and finalize:

```text
node scripts/agent-council.mjs finalize --run <run.json> --record <final-record.md> --destination <durable-output-directory>
```

The runner stages, hashes, verifies, and atomically renames durable evidence before cleanup begins.
The durable destination/staging tree may not overlap the disposable run in either direction. The
runner then re-proves current process ownership, removes only owned source-heavy artifacts,
and re-verifies the durable payload after cleanup and immediately before success.
Partial copy or cleanup remains an inspectable recovery state and never reports success.

Use `inspect` at any point. Use `abort --confirm-generated-run` only for a generated pre-durability
run. Existing schema-V2 runs without `panelSpec` are inferred as Full and retain their original
digest-bound roster shape. V1 runs are inspectable/abortable but never resumable under V3.
A schema-V2 run prepared by an earlier build that no longer parses is refused by `inspect` as
`STALE_RUN_STATE_RESTART_REQUIRED` with the offending field in its details; abort it the same way
and read `ownedProcessRecords` in the `aborted-stale` result, the runner cannot re-prove ownership
from state that never validated, so confirm those PIDs are gone yourself.

## Failure semantics

- Roster, manifest, pi preflight, launcher, or authorization failure stops before model calls; an
  unavailable native CLI is reported in the `prepare` output's `unavailableTransports` and removes
  only its own models. An absent pi is `PI_LAUNCHER_NOT_FOUND`; an off-pin `pi --version` is
  `PI_VERSION_MISMATCH`; a catalog with no rows is `PI_MODEL_CATALOG_EMPTY`, supply or repair
  `OPENROUTER_API_KEY` and confirm `pi --list-models openrouter` lists models before preparing again.
- External-network reachability failure after authorization stops before an attempt or model process
  is opened and reports `EXTERNAL_NETWORK_PREFLIGHT_FAILED`.
- Secret errors report only logical path and detector name, never matched content.
- Every opened seat/audit attempt is retained, including transport and validation failures. Seat and
  audit attempts both record truncation and the observed stop reason where the transport reports one,
  and each gets the same single automatic retry with a compact-record prompt. One rule chooses every
  retry prompt on both paths: too much output (a `length` stop, `RESPONSE_SIZE_LIMIT` /
  `AUDIT_RESPONSE_SIZE_LIMIT`, `OUTPUT_LIMIT`) asks for a compact record; an attempt that wrote no
  record (`MISSING_STRUCTURED_RESPONSE`, `PI_NO_ASSISTANT_TURN`) asks for the record first; a whole
  record that failed schema validation gets the schema correction; a transport failure
  (`TIMED_OUT`, `SPAWN_*`, `EXIT_*`, `UNEXPECTED_*`) gets neither and retries the base prompt.
  Audit-side runner failures are named `INVOKE_<cause>`, `UNEXPECTED_AUDIT_IO_FAILURE`, and
  `UNEXPECTED_AUDIT_VALIDATION_FAILURE`, not the seat's `UNEXPECTED_<cause>`. A native envelope that
  is not parseable JSON is `NATIVE_STRUCTURED_RESPONSE_SCHEMA_INVALID`. The `length` trigger is
  anchored to a recorded real-transport capture (`agent-council-pi-stream-length.jsonl`, kept with
  the offline test suite of the workspace this skill was built in; not bundled here), not to a
  hand-built stream.
- A pi seat's stdout is filtered to the events the runner reads, `session`,
  `tool_execution_start`, `message_end`, plus anything that is not a typed JSON object, so a
  transport banner still reaches the log, *before* the 4 MiB raw-output budget is applied. Unread
  streaming deltas are discarded rather than counted: `message_update` repeats text that arrives
  again, whole, in the following `message_end`, and two live seats died at the cap with roughly
  seven eighths of their stream being those deltas plus `message_start`, `turn_end`, and
  `tool_execution_end`. Only retained bytes count against the cap, so those runs would now complete.
  A runaway is still bounded and still named: raw stdout is capped at eight times the retained
  limit and crossing it is the same `OUTPUT_LIMIT` kill. The retained stream, not the child's whole
  stdout, is what lands in `raw/`, with the dropped line and byte counts written beside it as
  `<seat>-r<n>-a<n>.stdout.filter.json`. Probes and native seats are unfiltered and unchanged.
- Every qualified transport declares its facts once in the core's `QUALIFIED_EXTERNAL_ADAPTERS`
  table, exact version, whether it writes its own response file, whether it may audit, and whether
  it is a subscription door, and every version check, auditor gate, response-file decision, and
  `subscription-first` ranking reads that row. Pins are `claude-cli` 2.1.259, `grok-cli` 1.0.13, and
  `pi-headless` 0.84.4, re-qualified against live probes; `references/qualification-receipts.md`
  holds the receipts and the procedure for the next bump. An unknown adapter name resolves to
  nothing and fails closed.
- A failed command prints its failure code plus the structural details naming which boundary failed
  (`reason`, `adapterName`, exit status, and a bounded secret-scanned slice of a failed preflight
  child's stderr, replaced by `stderrRedacted: <detector>` on a match), and for a validation failure
  the field path (`... at response.risks[0].impact`); an unexpected internal failure additionally
  prints its message and stack.
- Process ownership is persisted immediately after PID/identity observation and removed only after
  exact-record, clean settlement or positively verified owned-handle/identity/absence termination.
- Recovery-ledger removal follows a durable primary-state removal; write or deletion failure leaves
  the exact ledger record recoverable and blocks progress.
- A required later round, adverse audit, durability failure, process survivor, or incomplete
  filesystem cleanup cannot become `FINALIZED`.
- Native CLIs and pi are not OS-contained; this release removes shell/network/extension
  capabilities at the application-policy boundary but makes no stronger containment claim. pi seats
  run under the host's own `~/.pi/agent` profile, there is no HOME redirect, so the pi door is a
  same-trust-domain boundary, not a sandbox.
