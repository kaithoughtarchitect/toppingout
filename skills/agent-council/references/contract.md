# Agent Council v3 contract

This contract is normative. `scripts/agent-council-core.mjs` owns deterministic schemas,
normalization, evidence validation, and milestone transitions. `scripts/agent-council.mjs` owns
orchestration and may observe the filesystem, Git, qualified native CLIs, pi, and processes only
through its injected I/O boundary; observations pass closed validators before becoming authority.

## Authority, identity, and membership

An Agent Council has one registered host/chair plus the exact number of external seats required by
its resolved assurance profile, routed through qualified native subscription CLIs or pi-headless
seats. It has one separate auditor. A missing or invalid member means no Agent Council formed;
there is no degraded mode.

`prepare` requires `--host-id <qualified-host-profile-id>`. The chair selects the profile that
matches its actual runtime identity. This is registered/self-reported identity, not cryptographic
attestation. Legacy `--host-family` input is a v1 migration error and cannot start a v2 run.

The roster pool is schema/version 2 and contains `hosts`, `participants`, and `auditors`:

- A host has `allowedRoles: ["decision"]`, a human-readable `runtimeDescriptor`, normalized
  lineage, and a live 90-day `manual-static` qualification with
  `capabilities.structuredChairRecord: true`.
- An external decision profile has `allowedRoles: ["decision"]`, an exact available model slug,
  variant, normalized lineage, an exact qualified adapter/version, the four repository capabilities
  (`repositoryRead`, `repositorySearch`, `snapshotEdit`, `structuredResponseFile`), and
  `statelessRoundContext`. No transport continues a session in any form: every later-round input is
  rematerialized for every seat, in the prompt or in the bounded context files the prompt names.
  Adapter qualification is exact and each adapter declares its facts once, in the core's
  `QUALIFIED_EXTERNAL_ADAPTERS` table: `claude-cli` 2.1.312, `grok-cli` 1.0.13, and pi 1.4.0 as
  `pi-headless`, each row carrying `version`, `writesResponseFile`, `auditCapable`, and
  `subscriptionTransport`. Every decision that once compared the adapter name against a literal,
  the version check, the auditor gate, response-file materialization on the seat and audit paths,
  and `subscription-first` ranking, reads that row. Lookup is `adapterContract`, which fails closed
  on an unknown, non-string, or prototype-shaped name; any other adapter name or version fails
  `ADAPTER_QUALIFICATION_MISMATCH`. The receipts behind the current pins, and the procedure for the
  next bump, are in `references/qualification-receipts.md`.
- An auditor has `allowedRoles: ["audit"]`, the same qualification discipline, and never appears
  in `decisionSeats`. An auditor must ride an `auditCapable` adapter, which `pi-headless` alone
  declares today: the audit path reads the auditor's response
  file directly and native seat argv carries no write tool, so a native auditor row is rejected at
  roster resolution with `AUDITOR_TRANSPORT_UNSUPPORTED`, before any repository material is copied.

The resolved roster is immutable: one `host` with role `chair`, exactly 2, 3, or 5
`externalDecisionSeats` with role `external-decision` according to `focused`, `balanced`, or
`full`, one `auditor`, and respectively 3, 4, or 6 `decisionSeats`. Across every resolved
selection, duplicate seat id, exact model, `vendorId`,
`familyId`, `baseModelId`, or intersecting `correlationGroupIds` is rejected. Provider transport
may repeat; provider aliases, variants, endpoints, deployments, or fine-tunes do not create
independence. Qualification expiry, missing capability, unavailable exact model, or a collision
fails before any panel seat receives repository material. Temporary one-off substitutions are not
durable roster defaults.
The ordered pool prefers qualified native subscription profiles and retains separately identified
`pi-headless` OpenRouter profiles; Gemini 4 Argon with the `high` variant is served by such a
profile. Claude-family models are never routed through OpenRouter, so the Claude seat is
`claude-cli` or nothing. Grok is not symmetric with that: the pool carries both a `grok-cli` row
and a distinct `grok-openrouter` `pi-headless` row, so a Grok CLI that fails preflight does not
remove Grok, the resolver seats the OpenRouter row instead, which is **pay-per-token**. Read the
resolved per-seat transport from the `prepare` output's `seatTransports`; the model name alone
never says which door a seat took. Every participant and auditor profile in the shipped pool carries
`variant: "high"`.
Because host lineage participates in the same collision test, a Codex host
cannot select GPT/Astra externally, a Grok host cannot select Grok, a Claude host cannot select
Claude, and a Gemini host cannot select Gemini; the first qualified collision-free family replaces
the omitted seat.

### Panel specification and selection

Every newly prepared resolved roster contains `panelSpec` version 1:

- `profile` and `assuranceLevel` are `focused`, `balanced`, or `full`;
- `externalSeatCount` is contract-bound to 2, 3, or 5 respectively;
- `transportPolicy` is `subscription-first`, the only defined policy;
- `selectionMode` is `automatic` or `explicit`;
- `requestedExternalIds`, `preferredExternalIds`, `excludedExternalIds`, and
  `requestedAuditorId` preserve the operator's exact selection intent.

The resolved-roster digest includes `panelSpec`, so the disclosure manifest binds both the selected
members and the constraints that produced them. Automatic selection prefers `--prefer-seat`
profiles in the order given, then qualified native subscription profiles under `subscription-first`,
ranking every `pi-headless` profile after them, with pool order as the deterministic tiebreaker. Any
other `transportPolicy` value is rejected. Explicit selection must name exactly the profile's
required external count. Requested, preferred, and excluded ids cannot contradict one another. Exact
seats and a requested auditor still must be available, qualified, host-distinct, and pairwise
independent.

The runner CLI exposes `--profile`, repeated `--seat`, repeated `--prefer-seat`, repeated
`--exclude-seat`, `--transport-policy`, and `--auditor`. A new skill-driven run always supplies a
profile. Omission defaults to `full` for compatibility. The roster never changes after preparation;
changing any selection input requires a new manifest and approval.

## Pure-core invariants

The core is import-clean except deterministic Node cryptography. It never reads files, environment,
clocks, randomness, UUIDs, processes, operating-system state, Git, seat transports, network,
database, or product data. All runtime facts are explicit inputs.

`AgentCouncilValidationError` exposes a stable uppercase `code`, optional structural `path`, and
sanitized structural `details`. Its message contains only the code/path and never source bytes,
credentials, prompts, model output, arbitrary adapter text, or secret values.

Canonical JSON rejects cycles, unsupported values, non-finite numbers, and Unicode-normalized key
collisions. Objects use normalized sorted keys. Canonical SHA-256 is `sha256:<lowercase-hex>`.
Comparable ids use Unicode NFC, trim, and lowercase. Repository paths normalize to relative POSIX
form and reject absolute paths, empty/dot segments, `..`, NUL, alternate data streams, and
case-fold collisions where a collection is formed.

The exported limits are authorization-sensitive input and are embedded byte-for-byte in every
disclosure manifest:

- two attempts per opened seat/round, two audit attempts per cycle, one synthesis revision cycle;
- 30-minute seat/audit timeout and 10-minute probe timeout;
- at most 8 probes; 256 KiB response, 4 MiB raw output, and 1 MiB probe output;
- 25,000 files, 2 MiB normal file, 5 MiB explicitly approved binary, 256 MiB corpus;
- 50 history commits and 5,000 history path entries;
- 10 separately approved historical diff paths, 512 KiB each and 2 MiB total.

## Disclosure manifest and corpus

Preparation freezes tracked plus untracked/non-ignored current-tree bytes; ignored files are omitted
by repository enumeration rather than treated as a rejected disclosure. It never copies original
`.git` history. Commit subjects and changed-path metadata are bounded and secret-scanned. Historical
diff bodies are empty by default; each requested path is separately approved, bounded, and
secret-scanned. A history manifest and encoded approved-diff files are materialized below
`.agent-council-evidence/history/` inside the canonical corpus before corpus hashing, seat copies,
and the fresh auditor copy.

Every included disclosure entry records:

- `logicalPath`, the citation path from the repository;
- `physicalPath`, the actual path in a sanitized corpus;
- disposition `copied`, the only disposition, with `physicalPath` equal to `logicalPath`;
- bytes, SHA-256, and explicit `binaryApproved` boolean.

Every exclusion records a logical path and non-secret reason code. The manifest also binds the
decision brief bytes/digest, included/excluded entries, bounded history, resolved-roster digest,
the mixed-transport adapter name/version (`mixed-seat-transports` / `pi-headless-v1`), logical probe
declarations, fixed limits, and corpus digest. The resolved-roster digest binds every selected
profile's exact native or `pi-headless` adapter. Its `manifestSha256` is the canonical digest of
every field except itself.

Authorization is equality between the supplied `--approve-manifest-sha <sha256>` and the newly
validated manifest digest. Any brief, corpus, exclusion, history, roster, adapter, probe, or limit
change invalidates authorization. A boolean approval is not accepted.

Secrets, symlinks, external dereferences, private keys, archives, databases,
dangerous binary formats, oversize files, reserved-tree collisions, alternate data streams, and
case-fold collisions fail before disclosure. A binary exception is explicit by logical path and
still secret-scanned and bounded.

`.agent-council-evidence/**` is a reserved tree: a repository path inside it is never disclosed and
is recorded as an exclusion with reason `reserved-evidence-tree`, so runner-generated evidence
cannot be shadowed by repository bytes. No file is ever relocated or given an alternate
disposition, it is either disclosed at its own path or excluded with a reason. Generated evidence
that would collide with an included path fails preparation with
`GENERATED_EVIDENCE_PATH_COLLISION`. Seats, probes, and the fresh auditor copy all use this same
sanitized canonical corpus.

The immutable canonical corpus remains until audit and durable-copy verification complete. Each
external seat receives a separate writable copy nested below a synthetic seat root as `workspace/`.
The seat root, not the nested evidence workspace, is the runtime discovery directory, so repository
`AGENTS.md`, `CLAUDE.md`, `.agents`, `.claude`, `.codex`, and similar instruction/configuration
surfaces remain citable evidence without becoming ambient runtime policy. The auditor copy is
freshly recreated the same way and hash-checked immediately before audit. Seat edits never flow to
peers, the auditor, probes, or the live worktree.

The prompt names the approved disclosure inventory rather than embedding it. Every seat root carries
`AGENT_COUNCIL_DISCLOSURE.json` beside `AGENT_COUNCIL_PROMPT.md` and outside `workspace/`, holding
the included entries, the exclusions, the probe declarations, and both digests. The auditor root
carries `AGENT_COUNCIL_AUDIT_BUNDLE.json` with the bundle, the allowed claim/evidence universe, and
any chair revision. Rounds 2 and 3 add `AGENT_COUNCIL_ROUND_CONTEXT.json` with the seat's own
Round-1 record, or the derived conflicts and the validated Round-2 record. Embedding the inventory
cost a 691 KiB Round-1 prompt on a 2,055-entry repository against a 1.4 KiB pointer, and every one
of those bytes had to be paged through the model's context and echoed back through the `--mode json`
event stream, which is part of how a live seat crossed the 4 MiB raw-output cap. The neutral brief,
the response-file contract, the nonce identity block, the schema instruction, and every
citation-shape rule stay inline; the pointer adds each file's name, its entry count, and the corpus
digest, so a seat can prove it read this run's context rather than a stale one. Those bytes are
outbound disclosure and pass the same secret scan as prompt bytes: a match is
`SECRET_IN_OUTBOUND_CONTEXT`, naming the file and the detector, and it fires before anything is
written. The prompt and every context file are deleted before each attempt materializes a new set,
so a retry can never read a previous attempt's context.

## Native and pi application-policy boundary

Native CLI and pi permissions are application policy, not operating-system isolation. Seats
may read, search, and edit only their isolated snapshot. They receive no shell/Bash, web, LSP,
nested agent, skill, command, MCP, plugin, package-install, automatic download/update/share, or
external-directory path. A pi seat is one non-interactive headless run per attempt with the child
cwd at the seat root: `-p --mode json`, the six isolation flags
`--no-session --no-context-files --no-extensions --no-skills --no-prompt-templates --no-approve`,
the strict tool allowlist `--tools read,grep,find,ls,edit,write` (pi's `bash` and `powershell`
built-ins are deliberately absent and pi has no `glob`), `--model <openrouter slug>`,
`--thinking <level>` from the profile variant, and an appended isolation system prompt. No
max-tokens or thinking-budget flag of any kind is passed: the seat gets the model catalog's full
output budget. On Windows the runner spawns the bundled `cli.js` through node with `shell: false`,
never the `.cmd` shim and never a shell. Claude uses safe mode, strict empty MCP discovery,
explicit repository tools, and no session persistence. Grok uses an isolated in-run home containing
only a copied subscription auth file and deny-oriented configuration, with compatibility imports,
workflows, memory, subagents, and web disabled; that auth copy is never disclosed or retained and is
deleted during cleanup. Every native seat receives only execution basics plus the minimum local
auth-location variables. Product,
database, cloud, Git, SSH, API-key, and MCP credentials remain absent.

A pi seat receives no generated configuration file at all; its isolation is argv-only. Its child
environment is the shared allowlist plus `OPENROUTER_API_KEY`, an absent key fails loudly with
`MISSING_ADAPTER_CREDENTIAL` rather than starting a seat that cannot produce a record, plus
`USERPROFILE`, `HOME`, `APPDATA`, `LOCALAPPDATA` so pi can read its own `~/.pi/agent` model catalog,
plus `NO_COLOR`. There is no HOME redirect: the host's pi profile, including its auth and settings,
is visible to a seat, so the pi door is an application-policy boundary inside one trust domain and
not a sandbox. `filterEnvironment` rejects any attempt to pass an environment override at all
(`UNSAFE_ENVIRONMENT_OVERRIDE`). Native adapters use fixed argv assembled by the runner.
Preparation checks the exact `pi --version` against the pin (an absent pi is
`PI_LAUNCHER_NOT_FOUND`; off-pin is `PI_VERSION_MISMATCH`; a failed spawn is
`PI_VERSION_PREFLIGHT_FAILED` or `PI_MODEL_PREFLIGHT_FAILED`; a catalog that parses to no models at
all is `PI_MODEL_CATALOG_EMPTY`, named at the transport rather than surfacing later as a roster
failure, pi answered with no rows, so supply or repair `OPENROUTER_API_KEY` and confirm
`pi --list-models openrouter` lists models before preparing again), normalizes the
`pi --list-models openrouter` catalog into `openrouter/<slug>` ids that form the available-model set
before roster resolution, and checks native CLI version and subscription auth (a Claude
`auth status --json` payload that is not parseable JSON is `CLAUDE_AUTH_SCHEMA_INVALID`). All of
these are non-generating. On Windows the runner resolves pi only under `%APPDATA%\npm`, the bundled
`cli.js`, else the `pi.cmd` shim's own target, and never consults `PATH`;
`PI_LAUNCHER_NOT_FOUND` carries a `reason` (`no_appdata`, `no_bundle_or_shim`, `shim_unreadable`,
`shim_target_missing`, or `no_path_executable` off Windows). A preflight failure raised by a failed
child (`*_PREFLIGHT_FAILED`) carries that child's exit status and a bounded, secret-scanned slice of
its stderr (`stderrRedacted: <detector>` replaces the slice when the scan matches); failures raised
from a successful child (version mismatch, empty catalog, schema-invalid auth) carry their own
structural detail instead. Preflight argv carries no repository material and no model credential,
but the pi preflight child does hold `OPENROUTER_API_KEY`, which is why that stderr is scanned
before any of it is surfaced. A named transport failure removes only its own rows; an internal defect
inside a preflight propagates instead of being recorded as an unavailable transport. The pi checks run in the pi child environment; the native CLI version and auth
checks run in the native auth environment, which carries no model credential. An unavailable native
CLI is a named degradation listed in the `prepare` output's `unavailableTransports` and removes only
its own models. That list is `prepare` output only, it is not run state, not part of `inspect`, and
not part of durable evidence, so capture the `prepare` output if the degradation matters. An
unusable pi is a hard stop, because every OpenRouter-hosted seat rides that door.
Preparation makes no network reachability request. After exact manifest authorization and before a
command opens any model attempt, the runner makes one credential-free, bounded `HEAD` request to
the OpenRouter model catalog through injected I/O. It sends no repository material or model
credential. An absent or malformed positive reachability observation fails with
`EXTERNAL_NETWORK_PREFLIGHT_FAILED` before a model process starts. This observation proves only
current egress; the host remains responsible for granting child-process lifecycle authority as well.
When the resolved panel contains the native Claude seat, Round 1 makes one minimal structured,
tool-disabled subscription call to prove the exact model is entitled before the other seats spend,
because the Claude CLI exposes no non-generating entitlement listing; panels with no `claude-cli`
seat skip it, and it is not repeated in later rounds.
Native safe modes and pi's isolation flags are supplementary and are never treated as
operating-system containment.

Model-edited code is never executed in this release. That capability remains unavailable until a
verified OS-isolation adapter exists.

## Pristine probe broker

Seats receive receipts, never command authority. A probe declaration contains an id and one logical
gate id from the fixed v1 catalog:

- Node `--check` for the installed Agent Council core and runner (`.claude/skills/agent-council/scripts/`);
- `npm run typecheck`;
- `npm test`.

The catalog is fixed code. `typecheck` and `test` apply only where the repository defines those npm
scripts (check the repo profile's gates); in any other repository, select only the Node checks, or
no probe.

At most eight may be selected (the catalog has four). No free-form command, prefix/suffix expansion, extra argv, shell,
PowerShell, direct `npm`/`npm.cmd`, `npx`, inline interpreter, install, network smoke, retrieval
evaluation, or model-edited path is eligible. Catalog expansion is a versioned contract change.

Each logical gate resolves during preparation to a fixed `ResolvedProbeSpecV1`. Direct Node gates
use exact `process.execPath` plus catalog argv. Npm gates use exact `process.execPath`, an absolute
inspected `npm-cli.js`, then fixed npm argv. The spec records platform, Node path/version/digest,
launcher path/digest, and, where applicable, npm CLI path/digest/version. Resolution or hashing
failure stops before authorization. Execution uses `shell:false`, the sanitized environment, a
fresh hash-verified pristine corpus copy, finite timeout, bounded output, and no extra argv. Runtime
path/argv/digest drift rejects the probe. Broker probes receive the shared allowlist alone: neither
the model credential nor any seat adapter's profile-location or configuration variable.

`ProbeReceiptV1` is `{payload, receiptSha256}`; the digest covers canonical payload only. Payload
status is a closed union:

- `PASSED` requires exit code 0 and an output digest;
- `FAILED` requires a nonzero exit code and output digest;
- `TIMED_OUT` has no exit code and reaches the timeout;
- `OUTPUT_LIMIT` is truncated and has an output digest;
- `SPAWN_FAILED` has no exit or disclosed output;
- `REJECTED_SECRET` suppresses both disclosed output and its digest.

Receipts are validated against the current spec and corpus identities. Seats and auditor may cite
only runner-issued receipt ids. Post-seat diffs expose bounded logical path/digest metadata only.

## Structured decision records

V3 changes orchestration and roster selection, not the validated evidence record formats. Seat
responses, disclosure manifests, and persisted run state intentionally remain schema version 2 so
existing tools and in-flight V2 runs do not require a format migration.

Free prose is not a completed seat. Every response is JSON schema v2, nonce-bound, and has the exact
run/round/seat/role identity expected by the runner.

An external response requires `role: "external-decision"`. A chair response requires
`role: "chair"`. Both contain recommendation/choice/confidence, claims, exact disclosed-corpus
citations, runner receipt ids, risks, alternatives, self-counterargument, and unresolved questions.
Claims, risks, and alternatives use unique stable ids; all references resolve. A citation includes
logical path, line range, and the manifest file digest. Wrong nonce, role, round, path, digest,
receipt, reference, or missing/unknown field fails validation and consumes the bounded retry.

The chair is a structured decision seat in every round. Round 1 requires `movement: null`. Later chair
responses require one disjoint movement variant:

```json
{"kind":"changed","fromChoiceId":"a","toChoiceId":"b","reasonClaimIds":["claim-1"]}
```

or:

```json
{"kind":"unchanged","choiceId":"b","rationale":"Evidence still supports b.","reasonClaimIds":["claim-2"]}
```

An external record cannot stand in for a chair record, and a chair record cannot stand in for an
external seat. A completed round contains the validated chair plus exactly the resolved profile's
external responses. Empty prose, refusal, malformed JSON, wrong nonce, invalid citation, fabricated receipt,
or schema failure records an explicit failed attempt; it never completes a seat.

The record is always the same file. A pi seat writes `.agent-council-response.json` at its seat root
itself; a native seat returns a structured envelope the runner materializes into that same file. A
native envelope that is not parseable JSON, a CLI banner printed ahead of its output, or a non-JSON
inner payload, is the named `NATIVE_STRUCTURED_RESPONSE_SCHEMA_INVALID`, never a raw parser error:
on a seat attempt it settles as `invalid_response`, and inside the Claude entitlement preflight it
stops the command. The
attempt's raw stdout, for a pi seat, its `--mode json` event stream, and its stderr are
retained under the disposable run's `raw/` tree. The exported 256 KiB response and 4 MiB raw-output
limits bound both; an overflowing stream is the named `output_limit`/`OUTPUT_LIMIT` failure, never a
silent trim.

A pi seat's stdout is filtered to the events the runner reads *before* that output budget is
applied. The retained set is exactly `session`, `tool_execution_start`, and `message_end`, what
`parsePiJsonStream` consumes, plus every line that is not a JSON object carrying a string `type`,
so a non-JSON transport banner still reaches the log. Unread streaming deltas are discarded rather
than counted: `message_update` carries incremental text that arrives again, whole, in the following
`message_end`, and two live seats died at the cap with roughly seven eighths of their stream being
those deltas plus `message_start`, `turn_end`, and `tool_execution_end`. Only retained bytes count
against the raw-output limit. Discarding them does not uncap the child: raw stdout is separately
bounded at eight times the retained limit, the next whole multiple above the worse of the two
measured compositions, and crossing that ceiling is the identical `OUTPUT_LIMIT` kill, so a model
emitting nothing the runner reads is still terminated and named. stderr is never filtered and keeps
counting against the retained cap. The retained stream, not the child's whole stdout, is what lands
in `raw/`, and the dropped line and byte counts are written beside it so the attempt's raw evidence
is honest about having been filtered. A line split across chunk boundaries is buffered and decided
whole; a trailing partial line at EOF takes the same decision and is retained when it passes. No
other caller filters: probes and native seats count and keep whole chunks exactly as before. The
retained set is contract-bound to what `parsePiJsonStream` consumes, and the offline suite fails if
the two drift apart.

Because a pi seat gets the model's full output budget, running out of it is a distinct, named
failure. The runner reads the stream's final assistant `message_end.stopReason` and persists it on
the attempt record as `stopReason`. A `length` stop with a missing or unparseable response file is
attempt status `truncated` with failure code `TRUNCATED`; a record that exists and validates is
`completed` even after a `length` stop, a missing file under any other stop reason stays
`MISSING_STRUCTURED_RESPONSE`, and a well-formed record that fails schema validation stays that
validation code. A stream that produced no assistant
turn at all did not run out of budget, it never spoke, and is the separately named
`PI_NO_ASSISTANT_TURN`, reported to the operator rather than automatically retried; recover it with
`retry --run <run.json> --round <n> --seat <id>` for a seat, or by re-running the same `audit`
command for the auditor. A
record that arrives whole but exceeds the exported response limit is `RESPONSE_SIZE_LIMIT`, and is
not automatically retried either. The `length` trigger is anchored to a committed real-transport
capture, `agent-council-pi-stream-length.jsonl` (kept with the offline suite of the workspace this
skill was built in; not bundled here): a recorded pi `--mode json` stream
whose earlier assistant `message_end` stopped on `toolUse` and whose final one stopped on `length`.
The offline suite reduces that asset directly, so the trigger is recorded behaviour rather than an
ideal model. A `truncated` attempt is
automatically retried once inside the same round with a truncation prompt that requires the compact
record first, spending the second of that seat's two attempts. A second truncation leaves the seat
as a named `truncated` attempt with no record, so the round is `failed` and a further `retry`
reports `SEAT_ATTEMPT_LIMIT`. There is no degraded panel and no partial round. Failure codes are
written here in the runner's raised form; the persisted attempt record lowercases them (`TRUNCATED`
is stored as `truncated`).

One rule chooses the retry prompt, and it is the same rule on the seat and audit paths, for both the
automatic retry and the operator's next command. Too much output, a `length` stop, a record past
the response limit (`RESPONSE_SIZE_LIMIT`, `AUDIT_RESPONSE_SIZE_LIMIT`), or the raw-output ceiling
(`OUTPUT_LIMIT`), gets the compact-record prompt. An attempt that wrote no record at all
(`MISSING_STRUCTURED_RESPONSE`, `PI_NO_ASSISTANT_TURN`) gets the missing-record instruction, because
nothing was rejected and there is nothing to correct. A record that arrived whole and failed schema
validation gets the schema correction. A transport failure (`TIMED_OUT`, `SPAWN_*`, `EXIT_*`,
`UNEXPECTED_*`) gets neither: nothing the model writes can fix the transport, so the retry carries
the round's or the audit's own prompt unchanged.

Before any seat model invocation, the runner persists a closed `running` attempt record with no
completion or failure fields. Settlement mutates that same record exactly once. Invocation
rejection consumes the attempt and retains discovered process ownership. An internal runner failure
raised inside an attempt is `transport_failed` with the cause named on the record as
`UNEXPECTED_<cause>`, the same token the raised aggregate error carries, never a model-invalid
response. An unresolved
running attempt blocks relaunch rather than being replaced. Launch and state persistence cannot be
one OS-atomic operation: the attempt is durable before spawn, then the PID/identity callback must
persist ownership before any result is accepted. If stable identity cannot be obtained, the live
owned handle is terminated immediately and the invocation is rejected; unproven cleanup remains a
recovery blocker.
If the ownership persistence callback itself fails, the runner immediately terminates through the
still-live owned handle and surfaces a stable persistence failure. An unverified termination carries
explicit ownership/termination evidence and remains a recovery blocker.
The PID record is written atomically first to a strict per-run/per-PID recovery ledger at one
deterministic controlled child of the runner's temporary root. The directory is created
non-recursively, must be a real directory whose realpath is the exact resolved expected path, and
is never adopted through a symlink, junction, or other reparse indirection. Its regular-file owner
marker binds run-file path, run id, and manifest digest; each regular PID record additionally binds
run directory, PID/group, and stable identity. Before every record read, write, removal, or
directory cleanup, the runner rechecks directory/owner/record types, realpaths, owner marker, and
the closed inventory (`owner.json` plus at most 256 PID records). Only after the record write may
the primary `state.processes` mutation be attempted. A failed primary write rolls back its
in-memory mutation; `readRun` and abort validate and merge the exact ledger records so a crash
cannot erase the blocker. Proven normal settlement durably removes primary state before deleting
the exact record. Empty-ledger cleanup removes the validated record, then owner marker, then the
exact empty directory with non-recursive removal; it never recursively deletes this ledger.
If the first owner-marker write fails after this invocation created the directory, rollback
revalidates the same realpath and filesystem identity, requires the directory to remain empty,
removes it non-recursively, and verifies absence before rethrowing the original write failure. A
rollback failure surfaces a stable combined error. A pre-existing unowned directory is never
claimed or removed.

## Deliberation and disagreement

Round 1 is common and blind: neither peers nor the chair recommendation is exposed. After all
resolved Round-1 records validate, Round 2 is mandatory and peer/chair blind. Each external seat sees only its
own Round-1 position plus a common falsification instruction; the chair re-examines independently.

After exactly the resolved number of valid Round-2 records, the core derives consequential disagreements. No CLI
boolean or caller-authored trigger can force or suppress Round 3.

Round 3 is required when either:

1. at least two Round-2 seats choose different `choiceId` values with confidence at least 0.65; or
2. an unresolved annotation spans two decision lineages, uses one of
   `security_privacy`, `irreversible_or_migration`, `public_interface_or_data`,
   `correctness_or_gate`, or `architecture_boundary`, and every referenced claim has confidence at
   least 0.65 plus a valid citation or receipt.

Annotations must reference existing Round-2 claims through the same bounded, collision-safe
qualified ids used by audit, plus selected lineages, confidence, and evidence. Each referenced
claim must belong to one of the declared involved seats, and every declared citation/receipt must
actually occur on a referenced claim. Raw claim ids and forged/unrelated evidence are rejected.
The core validates and derives the trigger; `evaluateRound3` accepts only that derived result, and
`inspect` reports it as `round3`, which is how the operator learns whether Round 3 is required.
Round 3 exposes
neutrally labelled conflicts for cross-examination. There is no fourth round. Incomplete or invalid
opened R2/R3 blocks audit; the runner never falls back to an earlier completed round.

## Audit, revision, and state

The auditor is distinct from every resolved decision family and never votes. It is dispatched
through the same seat door as its own qualified adapter, `pi-headless` for every auditor in the
shipped pool, under the same response-file contract. Its fresh verified snapshot receives
the disclosure/roster manifests, brief, every chair/external attempt from every opened round,
transport, truncation, and validation failures, retries, receipts, bounded diffs, synthesis, derived
disagreements, movement, convergence, and surviving dissent.

`AuditResponseV2` is nonce-bound and role `auditor`. Verdict is `FAITHFUL` or `NEEDS-REVISION`.
Findings use stable ids, evidence references, and remedy `SYNTHESIS_REVISION` or
`NEW_EVIDENCE_REQUIRED`. Malformed audit output is a retryable format failure, not an adverse
verdict. Truncation detection is symmetric with a seat: because the auditor rides the same
file-writing door, an audit attempt records the observed `stopReason`, a `length` stop with a
missing or unparseable record is `truncated`/`TRUNCATED`, and the runner spends one automatic retry
on it inside the same `audit` command and the same `auditAttemptsPerCycle` allowance, with the
compact-record prompt. A second truncation leaves both attempts named, produces no verdict, and a
further `audit` reports `AUDIT_ATTEMPT_LIMIT`. A record that arrives whole but exceeds the exported
response limit is `AUDIT_RESPONSE_SIZE_LIMIT`, the audit side of `RESPONSE_SIZE_LIMIT`. Retry
prompts follow the single rule stated for seat attempts above; there is no audit-specific variant.
`claimReferenceIndex` qualifies every claim as
`r{round}:sha256:{canonical digest of {seatId,claimId}}`, a bounded and collision-safe id, while
preserving the readable raw round, seat id, and claim id in the index. Finding `claimIds` must use
those qualified ids, while evidence references must resolve against the complete citation, receipt, diff, and
derived-disagreement universes in the persisted bundle. The audit
attempt is persisted as `running` before invocation and settled in place under the same lifecycle
rules as a seat attempt, but under its own failure-code names: a rejected invocation is
`INVOKE_<cause>`, a response-file read failure is `UNEXPECTED_AUDIT_IO_FAILURE`, and an unexpected
validator error is `UNEXPECTED_AUDIT_VALIDATION_FAILURE`, never the seat's `UNEXPECTED_<cause>`.
Every audit attempt also persists `auditInputSha256` before invocation,
binding the exact bundle, revision, nonce, and cycle. Only parsed `FAITHFUL` permits durability.

If a crash leaves one completed audit attempt without its history entry, resume first validates and
adopts the existing structured response in place only when its `auditInputSha256` matches the current
exact audit input, without recreating the auditor snapshot or making another model call. Changed
chair or synthesis input cannot adopt and may use only the one remaining bounded attempt. A missing
or schema-invalid response may likewise use that remaining attempt; unexpected adoption I/O or
validator errors propagate and never trigger a second model call.

For `NEEDS-REVISION`, the chair answers every finding `ACCEPT` or `DEFEND`, cites only existing
evidence, and provides replacement synthesis. The same auditor receives the original bundle/audit,
chair response, and revision against another fresh verified copy. One synthesis-only cycle is
allowed. `NEW_EVIDENCE_REQUIRED`, manifest/roster/probe change, or a second valid adverse verdict
becomes `RESTART_REQUIRED`; an adverse audit never passes as success.

Persisted `RunStateV2` is parsed immediately after every JSON read. Its `milestone` is a closed
discriminant:

`PREPARED -> AUTHORIZED -> R1_COMPLETE -> R2_FALSIFICATION_COMPLETE ->`
`[R3_CROSS_EXAM_COMPLETE] -> AUDIT_FAITHFUL -> DURABLE -> CLEANING -> FINALIZED`

`AUDIT_NEEDS_REVISION`, `RESTART_REQUIRED`, and `ABORTED` are explicit recovery/terminal states.
`nextMilestone` validates events; `parseRunStateV2` recursively validates persisted evidence. Each
milestone requires exactly the evidence already earned and prohibits later evidence. In particular,
`AUDIT_FAITHFUL` has no durability record, `DURABLE` has verified durability and no cleanup,
`CLEANING` has incomplete cleanup, and `FINALIZED` has complete cleanup. Attempt and cleanup records
preserve partial failures rather than flattening them into booleans.
An audit-ready milestone may contain exactly one newly completed next-cycle audit attempt while its
validated response is appended to history; any other attempt/history mismatch is invalid.
`AUDIT_FAITHFUL` and later terminal/recovery milestones reject running attempts; `AUDIT_FAITHFUL`,
`FINALIZED`, and `ABORTED` reject persisted process ownership. An unrequired Round-3 record is
invalid even when it is merely running rather than complete.

Schema-V2 runs prepared before V3 may omit `panelSpec`. The parser infers `full` solely for
validation, preserves the original roster shape without adding the field, and verifies its original
roster/manifest digest. Thus an existing V2 run can resume without silent state or digest migration.
All new runs include manifest-bound `panelSpec`. V1 runs are inspectable and abortable but never
resumed under V3. A custom V1 roster receives a precise migration error.

A run file that claims schema version 2 and carries the `agent-council` marker but fails
`parseRunStateV2` is a third disposition: a *stale* run, prepared by an earlier build whose state
carries fields this parser has since retired. The schema version is deliberately not bumped for it,
version 2 is pinned by the roster pool, the disclosure manifest, and every seat, chair, audit, and
revision record, and a bump would invalidate all of them. `inspect` refuses a stale run by name with
`STALE_RUN_STATE_RESTART_REQUIRED`, carrying the underlying validation code, its structural path,
and the offending field names in `details`; every driving command still fails with that structural
code itself, so a tampered run is diagnosed exactly as before. `abort` takes the same
tombstone-and-delete path a v1 run takes and returns `aborted-stale`, so the disposable seat,
auditor, corpus, probe, and raw copies are still removed. Named degradation: process ownership
recorded by a stale run cannot be re-proved from state that never validated, so the abort result
reports `ownedProcessRecords`, the count of PIDs the unparsed state claimed, and the operator
confirms those are gone.

## Durability, ownership, and cleanup

After faithful audit, final artifacts are written outside the disposable run, hashed, read back,
and atomically renamed durable before source-heavy cleanup starts. Destination and staging paths
must not overlap the disposable run in either direction. The payload is reverified after source
cleanup and immediately before success. A copy/hash/rename or later drift failure never reports
`FINALIZED`.

Filesystem and process adapters return observations, never authority. The core converts them to
tagged results:

- `assessTerminationProof` returns `{kind:"terminated", proof}` only from a complete observation
  with no owned root/descendant survivor; otherwise `{kind:"survivors", survivors}`.

Malformed or truthy adapter output is never ownership. Process ownership is durably recorded as
soon as PID and stable identity observation complete, first in the external recovery ledger and
then in primary run state. It is removed only when the exact matching
record has a normal clean settlement or positive owned-handle, absence, or identity-bound
descendant termination proof. Missing stable identity forces immediate owned-handle termination
and rejects the work; abrupt invocation or unverified termination retains the record and blocks
relaunch. Ownership is re-proved immediately before deletion. Windows uses the runner-owned PID plus
descendant-tree termination/verification; POSIX uses an owned process group. A nonzero Windows
`taskkill` result is retained as `PROCESS_TERMINATION_COMMAND_FAILED`; a subsequent complete
all-absent snapshot may still prove a benign race, while any survivor remains explicit and blocks.
A Windows parent/child/grandchild fixture is required before claiming descendant cleanup.

Cleanup has exactly two checkpoints, `processes` then `filesystem`. It terminates owned processes,
then deletes only the disposable seat, auditor, corpus, probe, and bounded raw run copies and the
isolated native runtime directory (including the temporary Grok auth copy).
Recursive disposable-tree removal uses bounded Windows `EPERM`/`EBUSY` retries without force
broadening or an alternate deletion fallback.
Failure remains `CLEANING`, records completed/failed/pending checkpoints, preserves resumable state,
and never reports `FINALIZED`. Abort writes a strict target-bound tombstone outside the disposable
root before deletion; partial deletion remains resumable even when the in-root run file disappeared,
and the tombstone is removed only after root absence is verified. Abort follows the same ownership
rules. For v2, abort validates that the parsed state's `runFile` is the exact platform-normalized
file it was asked to abort before recovery-ledger merge, process inspection, writes, or
deletion. The live worktree, Git index,
Git history, external paths, product data, and databases are never mutated.

## Retained durable evidence

The durable result retains the neutral brief; exact disclosure, history, roster, probe, and limits
manifests; every attempt and structured response; runner receipts and bounded diff metadata;
movement, disagreement, convergence, concessions, and surviving dissent; synthesis and revision;
auditor findings; durability/cleanup records; and the final decision. It does not introduce raw
transcript retention: a pi seat's event stream and stderr live only under the disposable run's
`raw/` tree and are deleted by the `filesystem` cleanup checkpoint, leaving the attempt record's
status, failure code, and `stopReason` as the durable trace. What that tree holds for a pi seat is
the retained stream plus its drop counts, never the child's whole stdout; both are disposable and
neither is copied into the durable payload. It relies on no undocumented transport
event fields beyond the documented final assistant `message_end` and its `stopReason`.
