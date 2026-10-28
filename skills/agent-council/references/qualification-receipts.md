# Adapter qualification receipts

Qualification is exact string equality between a roster row's `qualification.adapter.version` and
`QUALIFIED_EXTERNAL_ADAPTERS`. A drifted install is refused at preflight, which is the point: the
runner sends a fixed argv per adapter, so an unverified version is an untested argv that would fail
at spend time rather than before it.

Exactness is only affordable if re-qualifying is cheap. This file is that receipt. **Bumping a pin
without adding a row here is not a re-qualification, it is a guess.**

## Procedure

1. Read the version: `<cli> --version`.
2. Confirm every flag the runner sends still exists: check `buildNativeSeatArgs` (or
   `buildPiSeatArgs`) and the adapter's preflight against `<cli> --help`. A flag missing from
   `--help` is not automatically a failure, record whether the CLI still accepts it.
3. Exercise the contract, not just the version. For a native CLI that means the runner's own
   entitlement or single-shot path returning the structured output the runner parses. For pi it
   means a dispatched seat producing a response file.
4. Add a row below with the date, the version, the evidence, and anything that changed.
5. Update `QUALIFIED_EXTERNAL_ADAPTERS` and every matching roster row's `adapter.version`,
   `checkedAt`, `expiresAt`, and `evidenceRef`.

## Receipts

### pi-headless 1.4.0: 2026-10-28

- `pi --version` → `1.4.0`; the runner's own `parsePiModelCatalog` over `pi --list-models openrouter`
  → 375 models, every roster slug present (`grok-4.7`, `deepseek-v4-pro-0813`, `gemini-4-argon`,
  `glm-5.3`, `gpt-6-astra`, `kimi-k3.1-pro`, `qwen3.8-max-0902`, `minimax-m3`).
- **Changed: pi 1.x has a built-in MCP client, and `--tools` keeps MCP tools unless an entry names
  `mcp__`.** On 0.84.4 the allowlist alone kept a seat to its six tools; on 1.4.0 it would not.
  `--no-mcp` is now in `PI_ISOLATION_ARGS`. Every other flag the runner sends is still in `--help`.
- Seat contract exercised: the runner's own `buildPiSeatArgs` + `piInvocation` + `piChildEnvironment`
  on `openrouter/deepseek/deepseek-v4.1-flash-1017`, `--no-mcp` in the argv → exit 0 in 5.5 s,
  `stopReason: "stop"`, 6 tool calls (`grep`, `ls`, `read`, `write`), 0 MCP tools, and a valid
  response file. The three event types the runner retains (`session`, `tool_execution_start`,
  `message_end`) are all still emitted; 1.4.0 also emits `agent_settled`, which the runner ignores.
- Roster bump on the same date: Grok 4.6 → 4.7, Gemini 3.8 Flash → Gemini 4 Argon, Kimi K3 → K3.1 Pro,
  DeepSeek V4 Pro → the GA slug `deepseek-v4-pro-0813`, and Qwen 3.8 Max → `qwen3.8-max-0902` (the
  undated `qwen/qwen3.8-max` slug is no longer on OpenRouter).

### claude-cli 2.1.312: 2026-10-28

- `claude --version` → `2.1.312 (Claude Code)`; `claude auth status --json` → `loggedIn: true`,
  `authMethod: "claude.ai"`.
- All nine flags from the 2.1.259 receipt are still in `--help`.
- Contract exercised: `buildClaudeModelPreflightArgs("claude-opus-5-5")`, spawned against the resolved
  `claude.exe` → exit 0 in 3.5 s, `{"status":"available"}` through `parseNativeStructuredResponse`.
  The Claude seat and host move from Opus 5 to Opus 5.5.

### grok-cli: not re-qualified 2026-10-28

- Installed `grok 1.0.41`, but `grok models` answered "You are not authenticated", so the contract
  could not be exercised. The pin stays at 1.0.13, which means a 1.0.41 install is reported as an
  unavailable transport and the resolver seats `grok-openrouter` (pay-per-token) instead. The CLI
  still lists only `grok-4.6`, so the `grok` row keeps that model. `--no-memory` is still absent
  from `--help`, as in the 1.0.13 receipt.

### claude-cli 2.1.259: 2026-09-03

- `claude --version` → `2.1.259 (Claude Code)`.
- `claude auth status --json` → `loggedIn: true`, `authMethod: "claude.ai"`, which is what
  `preflightNativeAdapter` requires.
- All nine flags the runner sends are present in `--help`: `--safe-mode`,
  `--disable-slash-commands`, `--strict-mcp-config`, `--no-session-persistence`, `--json-schema`,
  `--output-format`, `--permission-mode`, `--effort`, `--tools`.
- Contract exercised: the runner's own `buildClaudeModelPreflightArgs("claude-opus-5")` argv, spawned
  against the resolved `claude.exe`, returned exit 0 in 6.9 s with structured output
  `{"status":"available"}`, parsed by the runner's own `parseNativeStructuredResponse`.
- Note: this CLI auto-updates. It moved 2.1.258 → 2.1.259 within a single working session, so an
  exact pin goes stale on its own schedule rather than on ours. Expect to re-run this procedure
  often; that is the cost the exactness buys.

### grok-cli 1.0.13: 2026-09-03

- `grok --version` → `grok 1.0.13 (5e9a58528b76) [stable]`.
- `grok models` → logged in with grok.com; `grok-4.6` (default) and `grok-4.5` available. The roster
  pins `grok-4.6`. Grok 4.7 is announced (Musk, 2026-09-02, “10 days”) but has no API id yet.
- Eleven of the twelve flags the runner sends are in `--help`. **`--no-memory` is not**: memory is
  now a `grok memory` subcommand. The flag is still *accepted*, a live `--single` call carrying it
  returned exit 0, valid JSON, and `stopReason: "end_turn"`, so the runner's argv works unchanged.
  It is now undocumented, which means it can be withdrawn without notice. If a future grok seat
  fails on argv, this is the first thing to check.
- Contract exercised 2026-09-03: `grok --single … --model grok-4.5 --no-memory --no-subagents
  --disable-web-search --output-format json` → exit 0, `stopReason: "end_turn"`, `modelUsage`
  reporting `grok-4.5-build`. The argv is model-id-agnostic; the 2026-09-07 roster bump
  seats `grok-4.6` (still listed, still default) without changing grok-cli 1.0.13.

### pi-headless 0.84.4: 2026-09-02, truncation trigger added 2026-09-03

- `pi --version` → `0.84.4`; `pi --list-models openrouter` → 354 models after alias filtering.
- Seat contract exercised 2026-09-02: a dispatched seat read and grepped its corpus copy across 5
  tool calls and wrote a valid response file.
- **Truncation trigger exercised 2026-09-03.** The whole truncation feature keys on
  `stopReason: "length"`, a value the earlier recording never contained, which left the offline fake
  receipt-grounded for stream *shape* but an ideal model for the *trigger*. A seat dispatched
  through the runner's own `buildPiSeatArgs` + `piInvocation` + `piChildEnvironment` on
  `openrouter/cohere/command-r-plus-08-2024` (4K output ceiling), asked for far more output than it
  could emit, produced `stopReason: "length"` with no response file, exactly the `truncated`
  classification path. 436 s, 681 KB stream, 2479 events. The captured events were committed as
  `scripts/fixtures/agent-council-pi-stream-length.jsonl` in the workspace this skill was built in
  (with its offline test suite; not bundled here), so the fake adapter's `length` arm is grounded
  in a real receipt.
- Two other real stop reasons were observed while forcing this and are worth knowing, because
  neither is `length` and both correctly fall through to `MISSING_STRUCTURED_RESPONSE` with the stop
  reason named on the record: `"error"` (`amazon/nova-micro-v1` and `amazon/nova-pro-v1` both failed
  pi's tool loop with "Model produced invalid sequence as part of ToolUse") and `"stop"`
  (`deepseek/deepseek-r1` declined to emit the full requested output and ended normally).
