---
title: Deep Agents Code (dcode)
id: dcode
type: product
status: sourced
product: dcode
keywords: dcode, deepagents-code, Deep Agents Code, terminal coding agent, CLI coding agent, TUI, headless mode, non-interactive, dcode -n, ACP server, slash commands, --model, --resume, --sandbox, install dcode
read_when: Read when choosing between dcode and the SDK, installing or running dcode, scripting it headless in CI, or looking up a dcode flag or slash command.
updated: 2026-10-21
sources_hash: 19b662bf25ad
---

# Deep Agents Code (dcode)

`dcode` (package `deepagents-code`) is LangChain's open-source terminal coding agent built on the Deep Agents SDK. Reach for it when you want a ready-made coding agent in the terminal (interactive TUI, headless `-n` runs, or an ACP server). Reach for the SDK (`create_deep_agent`) when you are building your own agent.

## Quick reference

- Package `deepagents-code`, binary `dcode`; needs Python >= 3.12 and WSL on Windows. Install with `curl -LsSf https://langch.in/dcode | bash`.
- Modes: interactive TUI (`dcode`), headless (`dcode -n "task"` or piped stdin), ACP server (`dcode --acp`).
- Headless has no shell unless `-S` is given; `-y` and `--yolo` are ignored. `--max-turns`, `--timeout`, `-q`, `--no-stream` and `--rubric*` need `-n` or stdin, else exit code 2. Timeout exit is 124.
- Model resolution: `-M provider:model` > `[models].default` > `[models].recent` > first env key among OPENAI, ANTHROPIC, GOOGLE_API_KEY, GOOGLE_CLOUD_PROJECT.
- `-a NAME` selects an agent profile under `~/.deepagents/<name>/`; `-r` resumes a thread. Threads are checkpointed to `~/.deepagents/.state/sessions.db`.
- `--allow-fs-tools` must include `read_file`; `-S` without `execute` does nothing, and `execute` without `-S` pre-approves nothing.
- `--sandbox` takes an optional value, so keep the bare form last on the command line.
- Gotcha: dcode is not in the SDK source, so there are no `deepagents_code` imports to find there.
- Gotcha: `--startup-cmd` output is not visible to the model; pipe content in instead.
- SDK version (0.7.29 here) and dcode version (0.1.x) are separate; `dcode doctor` shows both.

## What it is, relative to the SDK

- dcode wraps the SDK [[harness]]: planning, filesystem tools, `task` subagents, [[summarization]] and compaction, [[memory]] (`AGENTS.md`) and [[skills]]. You configure it with files and flags. You do not write Python, except for the optional experimental extensions (see [[dcode-extending]]).
- Architecture: the TUI talks to a local LangGraph agent server (`/restart` restarts it). Threads are checkpointed to SQLite at `~/.deepagents/.state/sessions.db`.
- `dcode --version` and `/version` print both `deepagents-code` and SDK versions. `dcode doctor` shows `deepagents (SDK): 0.7.x`. Keep the SDK version (this repo documents 0.7.29; see [[versions]]) separate from the dcode version (0.1.x).
- The SDK source has no dcode code. The only mentions are comments that name the "deepagents-code TUI/CLI" in `backends/utils.py` and `middleware/summarization.py`. Everything below comes from the docs only.
- SDK features that dcode exposes: the JS [[interpreters]] (`js_eval`, QuickJS, on by default), which make [[dynamic-subagents]] work out of the box; `RubricMiddleware`, which backs goals and rubrics ([[rubric]], [[dcode-goals]]); forked `general-purpose` subagents; and the sandbox-as-tool pattern for [[sandboxes]].
- For the product landscape (SDK vs dcode vs Managed), see [[products]]. To build the same thing yourself, see [[create-deep-agent]].

## Install and run

```bash
curl -LsSf https://langch.in/dcode | bash    # installs via uv as a uv tool
dcode                                         # interactive TUI
```

- Requires Python >= 3.12 (breaking change in 0.1.58). The install script's `DEEPAGENTS_CODE_PYTHON` defaults to `3.13`.
- Windows is not officially supported. Use WSL.
- Uninstall with `uv tool uninstall deepagents-code`. This leaves `~/.deepagents/` in place.
- Provider and sandbox extras: `dcode --install groq`, `/install fireworks`, `dcode uninstall groq`. For an arbitrary package: `dcode --install my_pkg --package`.
- Updates: auto-update is on by default. Manual options are `/update`, `dcode update`, and `dcode --update`.

## Modes

| Mode | How | Notes |
| - | - | - |
| Interactive TUI | `dcode`, optionally `-m "first prompt"` | Slash commands, `!` shell mode, `@file` injection, `@@` thread references |
| Non-interactive | `dcode -n "task"` or pipe stdin | Fresh thread per run (the docs; 0.1.87 added resuming threads in non-interactive mode). Shell is disabled unless `-S` is given. `-y`/`--yolo` are ignored |
| ACP server | `dcode --acp` | Agent Client Protocol over stdio for editors such as Zed (see [[protocols]]) |

Headless recipe:

```bash
git diff | dcode -n "Review these changes" -q --no-stream        # piped content comes first, then -n text
dcode -n "fix the failing tests" --max-turns 10 --timeout 300 \
      --allow-fs-tools execute,read_file,edit_file,write_file,ls,glob,grep \
      -S "pytest,git,make"                                         # exit 124 on budget hit
dcode -n "implement X" --rubric @acceptance.md --rubric-max-iterations 3
```

- Piped input is capped at 10 MiB. `--stdin` forces a stdin read.
- `--max-turns`, `--timeout`, `-q`, `--no-stream` and the `--rubric*` flags require `-n` or piped stdin. Without them dcode exits with code 2.
- In headless mode the agent is told to assume and proceed, not ask clarifying questions.
- `--startup-cmd CMD` output is shown in the transcript but is not added to the agent's history. To give the agent command output, pipe it in. In headless mode `--startup-cmd` has a 60 s timeout.

## Key flags (full table in the docs)

| Flag | Purpose |
| - | - |
| `-M/--model provider:model` | Pin the model for this session. Resolution order: flag > `[models].default` > `[models].recent` > first env key among `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_CLOUD_PROJECT` |
| `--default-model [M]` / `--clear-default-model` | Persist, view, or clear the default model |
| `--summarization-model M` | Separate model for compaction, `/offload`, `/compact`. In a session: `/offload model [M|clear]` |
| `--model-params JSON`, `--profile-override JSON`, `--max-retries N` (default 5) | Model kwargs, profile fields, retry budget |
| `-a/--agent NAME` | Named agent profile under `~/.deepagents/<name>/` (default `agent`) |
| `-r/--resume [ID]` | Resume the latest thread or a given thread. Restores that thread's agent |
| `--skill NAME` | Invoke a skill at launch |
| `-y/--auto-approve`, `--yolo`, `-S/--shell-allow-list` | Approval modes and shell allowlist (see [[dcode-safety]]) |
| `--allow-fs-tools LIST` | Expose only some filesystem tools. The list must include `read_file` |
| `--sandbox [TYPE]`, `--sandbox-id`, `--sandbox-snapshot-name`, `--sandbox-setup` | Remote execution (see [[dcode-safety]]) |
| `--mcp-config PATH`, `--no-mcp`, `--trust-project-mcp` | MCP loading (see [[mcp]], [[dcode-extending]]) |
| `-e/--extension PATH`, `--trust-project-extensions` | Python extensions (experimental) |
| `--interpreter`, `--interpreter-tools safe/all/list` | JS interpreter toggle and PTC allowlist (default `safe`) |
| `--recursion-limit N` | LangGraph step budget per turn |
| `--show-reasoning` | Show provider-visible reasoning for one launch. Since 0.1.84 it is on by default in the TUI and off in headless mode (where it goes to stderr); `DEEPAGENTS_CODE_SHOW_REASONING=0` hides it in both |
| `--no-tracing` | Disable LangSmith agent tracing for this session |
| `--json` | JSON envelope `{"schema_version": 1, "command": ..., "data": ...}` for management subcommands |

## Management subcommands

`dcode tools list`, `agents list|reset [--target SRC]`, `skills list|create|info|delete [--project]`, `threads list|delete` (with `--sort`, `--branch`, `--cwd`, `-n/--limit`), `mcp login [NAME]`, `mcp config`, `config show|list|get|path`, `auth list|status|set|remove|path`, `plugin ...`, `doctor`, `update`, `uninstall NAME`. The destructive ones (`agents reset`, `skills delete`, `threads delete`) accept `--dry-run`. Put tool-shaping flags before the subcommand: `dcode --allow-fs-tools ls,read_file tools list --json`.

## Most-used slash commands

`/model`, `/effort`, `/agents`, `/auth`, `/goal`, `/rubric`, `/remember`, `/skill:<name>`, `/offload` (alias `/compact`), `/context`, `/context-doctor` (token attribution for system prompt, `AGENTS.md`, skills index, tool and MCP schemas), `/tools`, `/cost`, `/tokens`, `/btw` (side question that does not interrupt the task), `/threads` (alias `/resume`), `/rename [name]` (name the thread; names are also generated automatically after the first model call, `[threads].auto_rename = false` turns that off), `/mcp`, `/plugins`, `/extensions`, `/reload` (re-reads `.env`, config, skills, MCP, plugin skills), `/restart`, `/trace`, `/offload model` (was `/summarization-model` before 0.1.81), `/auto model`, `/clear`, `/update`. Keys: `Shift+Tab` cycles approval modes, `Ctrl+G` opens an external editor, `Ctrl+R` searches prompt history, `Ctrl+O` expands the last tool output, `Ctrl+T` toggles the subagent panel.

## Tracing

Store a LangSmith key via `/auth`, or set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in `~/.deepagents/.env`. dcode's own traces go to `DEEPAGENTS_CODE_LANGSMITH_PROJECT` (default `deepagents-code`). Shell commands that dcode runs keep the user's `LANGSMITH_PROJECT`, so app traces stay separate. `DEEPAGENTS_CODE_LANGSMITH_REPLICA_PROJECTS` dual-writes to a second project. Client-side secret redaction is on by default. To turn agent tracing off: `dcode --no-tracing` for one session, or `DEEPAGENTS_CODE_LANGSMITH_TRACING=false`; an explicit `false` there overrides `LANGSMITH_TRACING=true`.

## Changelog highlights

- **Fork:** `deepagents-code` was forked from `deepagents-cli` at v0.1.0 (2026-05-12), "ported from `libs/cli`". History before the fork is in the `deepagents-cli` changelog. The binary is `dcode`. Older docs may say `deepagents` (for example, 0.1.17's "non-interactive `deepagents auth` subcommands").
- 0.1.4: `js_eval` interpreter via `langchain-quickjs`. `js_eval` became on by default later.
- 0.1.13: pluggable third-party sandbox backends, the `dcode config` command, `[retries]`.
- 0.1.16: ChatGPT OAuth (`openai_codex`) and the Vercel sandbox.
- ~0.1.3x: `RubricMiddleware`-backed `/goal` and `/rubric`, plugins and marketplaces reach GA, `[startup].mode`.
- 0.1.40: saved per-server project MCP approvals. `DEEPAGENTS_CODE_ENABLED_PROJECT_MCP_SERVERS` is now ignored.
- 0.1.45: `--allow-fs-tools`, the Hooks v2 engine.
- 0.1.46: Auto mode GA. The recursion limit was raised to 2000. It was later deferred to the LangGraph server in 0.1.64.
- 0.1.52: Hooks v2 GA, including plugin hooks.
- 0.1.58: Python 3.12+ required.
- 0.1.59: `managed_config.toml`. 0.1.63 added remote managed config.
- 0.1.61: `[models].allowed` is enforced. Goal and rubric context is injected directly (replaces the `get_goal` and `get_rubric` tools).
- 0.1.62: `/context-doctor`, `DEEPAGENTS_HOME`, secret redaction re-enabled by default.
- 0.1.65: Python extensions, `/summarization-model`, `--show-reasoning`, `uninstall`.
- 0.1.66: the `general-purpose` subagent defaults to fork mode. The Auto classifier default is chosen per provider.
- 0.1.71: MCP moved onto FastMCP and `langchain.mcp`.
- 0.1.74: `@@` thread mentions.
- 0.1.78 (2026-09-28): `/btw`, an offer to summarize and switch threads when the prompt cache expires, persisted project-MCP startup denials, and 100 recent threads shown by default.
- 0.1.79 (2026-09-29): MCP tool calls get configurable timeouts (no more indefinite hangs), stdio MCP servers start in the session directory, and a few TUI fixes.
- 0.1.80: a `cache_expiring` hook fires before the prompt cache expires.
- 0.1.81: `--no-tracing`; `/summarization-model` renamed to `/offload model`; the agent can discover marketplace plugins; hooks fail closed if their context changes on resume.
- 0.1.82: automatic and manual thread names (`/rename`).
- 0.1.84: invoked skills are resolved on the server and checked for trust; provider-visible reasoning shown by default in the TUI; Daytona snapshots.
- 0.1.86: NVIDIA OpenShell sandbox provider; `/resume` alias.
- 0.1.87 (2026-10-20): resume threads in non-interactive mode; large idle sessions are compacted before the prompt cache expires.

## Gotchas

- dcode is not in `sources/package`. Do not look for `deepagents_code` imports in the SDK. `deepagents_code.extensions.ExtensionAPI` and `deepagents_code.integrations.sandbox_provider` exist only in the dcode package.
- Startup model auto-detection checks only 4 env vars. Groq, Fireworks and others need `--model` or a saved default.
- `--sandbox` takes an optional value. Keep the bare form last, or the next argument is consumed as the provider name.
- `-S` without `execute` in `--allow-fs-tools` does nothing. `execute` without `-S` means no command is pre-approved.
- `--startup-cmd` output is not visible to the model.
- The quickstart and CLI reference still say each non-interactive run starts a fresh thread, while the 0.1.87 changelog adds resuming threads in non-interactive mode. The docs lag the changelog; check `dcode --help` on your install.

## Sources

- `../sources/docs/oss/deepagents/code/overview.md`
- `../sources/docs/oss/deepagents/code/quickstart.md`
- `../sources/docs/oss/deepagents/code/cli-reference.md`
- `../sources/docs/github/deepagents-code-CHANGELOG.md` (the docs changelog page now redirects to this GitHub file)
- `../sources/package/deepagents/backends/utils.py` (only a comment mentioning the TUI)
- `../sources/package/deepagents/middleware/summarization.py` (only a comment mentioning the CLI)

## See also

- [[index]]
- [[dcode-config]]
- [[dcode-extending]]
- [[dcode-safety]]
- [[dcode-goals]]
- [[products]]
