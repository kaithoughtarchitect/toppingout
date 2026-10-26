---
title: dcode configuration, providers and credentials
id: dcode-config
type: reference
status: sourced
product: dcode
keywords: dcode config, config.toml, managed_config.toml, API key, /auth, base_url, OPENAI_BASE_URL, gateway, DEEPAGENTS_CODE_, DEEPAGENTS_HOME, .env, provider, custom provider, class_path, recursion_limit, allowed models, retries
read_when: Read when dcode uses the wrong model or API key, a setting seems ignored, you need a custom or gateway provider, or an admin must pin policy.
updated: 2026-10-21
sources_hash: 252ab789eb0f
---

# dcode configuration, providers and credentials

Where every dcode setting lives and which source wins: `managed_config.toml`, env vars, `~/.deepagents/config.toml`, `.env` files, the `/auth` store, and CLI flags. Read this before changing models, keys, gateways or limits for [[dcode]].

## Quick reference

- General precedence: managed_config.toml > `DEEPAGENTS_CODE_<NAME>` env > canonical env var > `~/.deepagents/config.toml` > default; CLI flags override unless managed pins.
- Provider keys: `DEEPAGENTS_CODE_<PROVIDER>_API_KEY` > `/auth` stored key > plain env var. A stored key beats a plain env var like `OPENAI_API_KEY`.
- Key and `base_url` resolve as a pair; storing a key with a blank base URL clears a gateway `OPENAI_BASE_URL`.
- Dotenv: nearest project `.env`, then `~/.deepagents/.env`; shell exports always win. Skip the project one with `DEEPAGENTS_CODE_READ_PROJECT_DOTENV=0`.
- `DEEPAGENTS_HOME` relocates `~/.deepagents` and must be set in the inherited shell, never a `.env`.
- `/model` writes only `[models].recent`; pin a default with `/model --default p:m`, `Ctrl+S`, or `dcode --default-model`.
- Allowlist `[models].allowed` with `provider:*` admits only discoverable models; managed `allowed` replaces the user list.
- OpenAI, Anthropic and Google are bundled; others need `dcode --install <provider>`. Custom models use `[models.providers.<p>]` with `class_path`.
- Custom providers need `max_input_tokens` in `.profile`, or auto-summarization triggers at about 170k tokens. OpenAI-compatible gateways need `use_responses_api = false`.
- Managed config fails closed (exit 78 on unreadable policy); `[sandboxes].default` does not force sandboxing.

## Resolution order

- **General options** (first match wins): (1) admin `managed_config.toml`, (2) `DEEPAGENTS_CODE_<NAME>` env var, (3) the canonical env var where one applies, (4) `~/.deepagents/config.toml`, (5) built-in default. CLI flags override for one launch unless managed config pins the value.
- **Provider API keys:** (1) `DEEPAGENTS_CODE_<PROVIDER>_API_KEY`, (2) the `/auth`-stored key in `~/.deepagents/.state/auth.json`, (3) the plain env var such as `OPENAI_API_KEY`. A stored key beats a plain env var, so `OPENAI_API_KEY=... dcode` does **not** override a stored key. The prefixed variable does.
- **Endpoint (`base_url`):** (1) `base_url` in config, (2) the `DEEPAGENTS_CODE_`-prefixed endpoint var, (3) the plain endpoint var (for example `OPENAI_BASE_URL`), (4) the endpoint saved with `/auth`, (5) the SDK default. The key and endpoint resolve as a **pair**. If you store a key with a blank base URL, dcode also clears a gateway `OPENAI_BASE_URL`, so your key goes to the provider directly.
- **Dotenv:** dcode loads the nearest project `.env` (walking up from the launch directory; the first one found wins), then `~/.deepagents/.env`. Shell exports always win. `[startup].read_project_dotenv = false` or `DEEPAGENTS_CODE_READ_PROJECT_DOTENV=0` skips the project `.env`. A project `.env` cannot toggle this setting itself.
- **Prefix trick:** `DEEPAGENTS_CODE_X` is checked before `X` for any variable dcode reads. Setting `DEEPAGENTS_CODE_ANTHROPIC_API_KEY=` (empty) makes dcode ignore a shell-exported key.
- Inspect values without starting a session: `dcode config` / `config show`, `dcode config get <key|section>`, `dcode config list`, `dcode config path` (add `--verbose`, `--json`). Secrets show only as configured or not configured.

## Files and data locations

```text
~/.deepagents/                 # relocate with DEEPAGENTS_HOME (abs path or ~/...)
  config.toml  .env  .mcp.json  hooks.json  prices.json  extensions/
  .state/ sessions.db history.jsonl auth.json chatgpt-auth.json mcp-tokens/ hooks_trust.json
  conversation_history/        # /offload archives, swept after 30 days
  <agent>/AGENTS.md  skills/  memories/  agents/<sub>/AGENTS.md
~/.agents/skills/              # tool-agnostic shared skills (resolved from real $HOME)
<project>/AGENTS.md  .deepagents/{AGENTS.md,skills,agents,extensions,hooks.json,.mcp.json}  .agents/skills  .mcp.json
```

- `DEEPAGENTS_HOME` is a trust boundary. Set it in the inherited shell only; no `.env` may set it. Relative paths and `~user` forms are rejected.
- Dotenv files cannot set these variable families: `PATH`, `PYTHON*`, `LD_*`/`DYLD_*`, `NODE_OPTIONS`, `BASH_ENV`, `GIT_*` config and exec variables, `*_ASKPASS`, `COMSPEC`, and similar. A **project** `.env` additionally cannot set the MCP trust variables, `DEEPAGENTS_CODE_AUTO_CLASSIFIER_MODEL`/`_TIMEOUT`, `DEEPAGENTS_CODE_FORKED_SUBAGENTS`, `LANGGRAPH_DEFAULT_RECURSION_LIMIT` or `TERM_PROGRAM`.

## `config.toml` essentials

```toml
[models]
default = "anthropic:claude-opus-4-8"      # beats recent; /model only writes recent
summarization_default = "openai:gpt-5.6-sol"  # else the main model
auto_classifier = "openai:gpt-5.6-luna"    # Auto-mode reviewer
auto_classifier_timeout = 20               # seconds, clamped 1..300
allowed = ["anthropic:*", "openai:gpt-5.5"]  # unset = all; [] = none

[agents]
default = "backend-dev"                    # -a overrides; -r restores the thread's agent

[startup]
mode = "manual"                            # manual | auto | yolo
read_project_dotenv = true

[retries]
max_retries = 5                            # default 5; 0 disables
[retries.anthropic]
max_retries = 0                            # per-provider override

[runtime]
recursion_limit = 5000                     # 25..100000; no dcode default

[interpreter]                              # js_eval (QuickJS)
enable_interpreter = true
timeout_seconds = 5.0
memory_limit_mb = 64
max_ptc_calls = 256
max_result_chars = 4000
ptc = "safe"                               # "safe" | "all" | [names] | false
ptc_acknowledge_unsafe = false

[warnings]
session_cost_threshold_usd = 50            # <=0 disables
cache_prompt = "expiry"                    # expiry | send | off
cold_cache_min_delta_usd = 0.50
trusted_cache_endpoints = ["smith.langchain.com"]

[threads]
compact_on_resume_threshold = 400000       # 0 disables
max_resume_age = "7d"                      # s|m|h|d|w
auto_rename = true                         # name a thread after its first response
rename_model = ""                          # empty = the conversation model
[mcp]
tool_timeout = 120                         # seconds per MCP tool call; env DEEPAGENTS_CODE_MCP_TOOL_TIMEOUT (1..900)
[terminal]
tab_title = "{app_name} - {thread_name}"   # also {cwd}, {branch}
[memory]
auto_save = true
[history]
retention_days = 30
[tracing]
langsmith_redact = true
[update]
auto_update = true
check = true
prices_auto_update = true
[ui]
theme = "langchain"
show_reasoning = false                     # unset: on in the TUI, off headless (since 0.1.84)
show_diff_line_numbers = true
```

- Retry-budget precedence: `--max-retries` > `[retries.<p>]` > `[retries]` > 5. For an arbitrary provider, `[retries.<p>].param = "retries"` names the SDK's retry kwarg so dcode can disable the SDK-level retry.
- Recursion limit precedence: managed > `--recursion-limit` > `DEEPAGENTS_CODE_RECURSION_LIMIT` > `[runtime]` > `LANGGRAPH_DEFAULT_RECURSION_LIMIT` > LangGraph server default. The goal-rubric limits are separate.
- `[interpreter].ptc = "all"` exposes every tool to programmatic tool calls, and those calls **bypass approvals**. It needs `ptc_acknowledge_unsafe = true`. See [[interpreters]].

## Providers

- OpenAI, Anthropic and Google (Gemini) are bundled. Everything else is an extra: `dcode --install groq|fireworks|ollama|baseten|openrouter|litellm|vertex|...`. Built-in providers are identified by LangChain's `provider:model` ids (`openai`, `openai_codex`, `azure_openai`, `anthropic`, `google_genai`, `google_vertexai`, `google_anthropic_vertex`, `bedrock`, `bedrock_converse`, `groq`, `fireworks`, `ollama`, `together`, `mistralai`, `deepseek`, `xai`, `openrouter`, and more). See [[models]] for the SDK side.
- `openai_codex` uses ChatGPT browser sign-in through `/auth`, not an API key. The token is stored at `.state/chatgpt-auth.json`. `dcode auth set` cannot store it; `dcode auth remove openai_codex` signs you out.
- Claude on Vertex uses `google_anthropic_vertex:<model>` with ADC plus `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION`. Use `google_vertexai` only for Google models.
- The `/model` switcher lists models from installed packages' profiles, `[models.providers.<p>].models`, and locally discovered Ollama models (`DEEPAGENTS_CODE_OLLAMA_DISCOVERY=0` turns discovery off). Any model name can still be passed directly.
- Model kwargs, highest priority first: `--model-params` JSON, then `/model --model-params`, then `[models.providers.<p>.params]`, then `[...params."<model>"]` sub-tables (shallow merge; the model entry wins). Never put `api_key` in `params`.

```toml
[models.providers.my_custom]                 # arbitrary BaseChatModel
class_path = "my_package.models:MyChatModel" # imported at startup; runs arbitrary code
api_key_env = "MY_API_KEY"                   # NAME of the env var
base_url_env = "MY_BASE_URL"                 # literal base_url wins if both are set
models = ["my-model-v1"]                     # bypasses profile filtering in /model
display_name = "My Provider"
api_key_url = "https://my-provider.example/keys"
enabled = true
[models.providers.my_custom.profile]
tool_calling = true
max_input_tokens = 128000                    # without it, auto-summarization triggers at ~170k tokens
```

Install the package into dcode's environment with `dcode --install my_package --package`. dcode instantiates it as `MyChatModel(model="my-model-v1", base_url=..., api_key=..., **params)`. For OpenAI-compatible gateways, set `[models.providers.openai.params] use_responses_api = false`, because OpenAI defaults to the Responses API. See [[summarization]] for how `max_input_tokens` drives compaction.

## Credentials

- `/auth` is the TUI manager. It covers LLM keys plus optional base URL, the Tavily key (enables `web_search`), and the LangSmith key (enables tracing). Row labels are `[stored]`, `[env: VAR]` or `[missing]`.
- From the shell: `echo "$KEY" | dcode auth set anthropic`, `dcode auth set openai --from-env OPENAI_API_KEY`, `dcode auth list|status <p>|remove <p>|path`. `set` refuses to run in an interactive TTY.
- For CI, export env vars. Use `DEEPAGENTS_CODE_OPENAI_API_KEY` to scope a key to dcode without affecting other tools.

## Managed configuration (admins)

- Location: macOS `/Library/Application Support/dcode/managed_config.toml`, Linux `/etc/dcode/managed_config.toml`, Windows `<ProgramData>\dcode\managed_config.toml` (resolved from the registry, not env). Uses the same keys as `config.toml`. Users cannot override it.
- Remote policy: a local file containing only `[managed_config] source = "https://..."`. Requirements: HTTPS, no query string or credentials, 200 status, uncompressed, at most 1 MiB, 5 s timeout, no redirects or proxies.
- Fails closed: an unreadable policy makes commands exit with code `78`. Invalid values for security keys stop startup; these keys are `interpreter.enable_interpreter`, `interpreter.ptc`, `interpreter.ptc_acknowledge_unsafe`, `models.allowed`, `models.auto_classifier`, `runtime.recursion_limit`, `sandboxes.default`, `shell.allow_list`, `skills.extra_allowed_dirs`, `startup.mode`, `startup.yolo_switcher`, `tracing.langsmith_redact`. `dcode config`, `dcode doctor`, `dcode auth path` and help still run.
- Managed `[models].allowed` **replaces** the user's list. It applies to `--model`, `/model`, defaults, the Auto classifier, rubric graders and subagent models.
- Install pinning: `curl -LsSf https://langch.in/dcode | DEEPAGENTS_CODE_VERSION="0.1.16" bash`. Related variables: `DEEPAGENTS_CODE_EXTRAS`, `DEEPAGENTS_CODE_PRERELEASE` (mutually exclusive with `VERSION`), `DEEPAGENTS_CODE_PYTHON`. The script supports running as root for MDM.

## Gotchas

- `/model` writes only `[models].recent`. It never overwrites `default`. Pin a default with `Ctrl+S` in the picker, `/model --default p:m`, or `dcode --default-model`.
- An allowlist wildcard `provider:*` admits only *discoverable* models. Adding a model under `[models.providers.x].models` does not allow it.
- `[sandboxes].default` does not force sandboxing. A launch without `--sandbox` runs on the host.
- `config-file.md` says `startup.mode = "auto"` requires `DEEPAGENTS_CODE_EXPERIMENTAL=1`. But Auto is GA as of 0.1.46, and `approval-modes.md` mentions no gate. Treat the gate note as stale.
- The docs describe secret redaction as on by default. The changelog flipped it off in 0.1.46 and back on in 0.1.62. Current: on.
- `DEEPAGENTS_CODE_RECENT_THREADS` now defaults to 100 in the docs too (it was 20 there before), matching the 0.1.78 changelog.
- `DEEPAGENTS_CODE_LANGSMITH_TRACING=false` (or `--no-tracing` for one launch) turns agent tracing off and beats `LANGSMITH_TRACING=true`.
- An MCP tool-call timeout does not cancel the call on the server, so a retry can duplicate work.

## Sources

- `../sources/docs/oss/deepagents/code/configuration.md`
- `../sources/docs/oss/deepagents/code/config-file.md`
- `../sources/docs/oss/deepagents/code/providers.md`
- `../sources/docs/oss/deepagents/code/credentials.md`
- `../sources/docs/github/deepagents-code-CHANGELOG.md` (the docs changelog page now redirects to this GitHub file)

## See also

- [[index]]
- [[dcode]]
- [[dcode-safety]]
- [[dcode-extending]]
- [[dcode-goals]]
