---
title: Managed Deep Agents (MDA)
id: managed
type: product
status: sourced
product: managed
keywords: managed deep agents, MDA, mda CLI, managed-deepagents, define_deep_agent, mda deploy, mda dev, mda init, LangSmith deployment, Agent Server, hosted agent, Context Hub, deploy agent to production, migrate from create_deep_agent
read_when: Read when deciding between the OSS SDK and Managed Deep Agents, running mda init, build, dev or deploy, or migrating create_deep_agent code to define_deep_agent.
updated: 2026-10-21
sources_hash: a4efb216681f
---

# Managed Deep Agents (MDA)

LangSmith-hosted Deep Agents: you write a project folder (`agent.py` + `instructions.md` + optional `skills/`, `tools/`, `memory.py`, `sandbox/`, `channels/`, `schedules/` ...) and the `mda` CLI compiles it into a LangGraph app that runs on LangSmith Agent Server. Reach for it when you want the agent in production with Slack/webhooks, OAuth for end users, cron, a managed sandbox and durable memory, without running any of that yourself.

Status: public beta on LangSmith Cloud. `LANGSMITH_ENDPOINT` picks the region: GCP US (default), GCP EU, GCP APAC or AWS US; LangSmith managed tools are GCP US only. Package `managed-deepagents` (PyPI and npm publish together at the same version; latest in sources 0.9.4, 2026-10-20). The `mda` binary is a Rust CLI shipped inside the package. None of this is in the `deepagents` 0.7.29 source; everything here is docs-only.

## Quick reference

- MDA = LangSmith-hosted Deep Agents; public beta on LangSmith Cloud (region via `LANGSMITH_ENDPOINT`, GCP US default); package `managed-deepagents`, CLI `mda` (latest in sources 0.9.4).
- Only required file is root `agent.py` exporting `agent = define_deep_agent(name=..., model=..., tools=[...])`; `name` is required, static, `[a-zA-Z][a-zA-Z0-9_-]*`.
- `define_deep_agent` returns a definition; the runtime supplies backend, store, checkpointer, system prompt, skills and memory.
- `agent` can instead be a sync or async factory `agent(runtime)` that returns a definition per run (0.9.0); only a factory may set `instructions`, `skills`, `mcp`, `sandbox`.
- Quickstart: `uvx --from managed-deepagents mda init <name>`, then `uv run mda dev`, then `uv run mda deploy`.
- Not accepted: `system_prompt`, `skills`, `memory`, `backend`, `store`, `checkpointer`, `state_schema`. Prompt goes to `instructions.md`, skills to `skills/`, memory to `memory.py`, backend to `sandbox/`.
- Middleware must use async hooks; `permissions` is cleared when `sandbox/` exists.
- `mda deploy` flags: `--name`, `--deployment-type dev|prod`, `--context-strategy overwrite|keep-hub`, `--no-wait` (not allowed with Slack).
- Put provider keys in `.env` or workspace secrets; `.env` is not archived but non-reserved values are forwarded as deployment secrets.
- Gotcha: `mda build` does not validate the definition call; a forbidden param like `backend=` only fails under `mda dev`.
- Stay on OSS for custom backends, own store or checkpointer, custom routes, `state_schema`, or stdio MCP.

## Mental model

- MDA runs the **same OSS harness** ([[harness]]): the managed runtime ultimately calls `create_deep_agent` ([[create-deep-agent]]). Tools, middleware, subagents, filesystem tools, skills behave the same.
- The difference is **who compiles**:
  - `create_deep_agent(...)` returns a compiled graph; you own backend, store, checkpointer, server.
  - `define_deep_agent(...)` returns a *definition* (config, not runnable). `mda dev` / `mda deploy` hand it to the runtime, which injects backend, store, checkpointer, system prompt, skills, memory, then compiles.
- Every `define_*` works this way: declare, let the runtime own lifecycle (`define_deep_agent`, `define_memory`, `define_sandbox`, `define_mcp`, `define_schedule`, `define_identity`, `channels.slack()` / `channels.http()`).
- Deploy result is a normal Agent Server deployment: threads, runs, streaming, Agent Server API, and an MCP endpoint at `/mcp`.

```python
# agent.py  (only required file; must export a variable named `agent`)
from managed_deepagents import define_deep_agent
from tools.search import internet_search

agent = define_deep_agent(
    name="research-assistant",          # required, static, [a-zA-Z][a-zA-Z0-9_-]*
    model="openai:gpt-5.5",
    tools=[internet_search],
)
```

Project layout and every file's role: [[managed-project]]. Tools/MCP/memory/sandbox/connections: [[managed-capabilities]]. Slack/HTTP/identity/schedules/MCP endpoint: [[managed-channels]]. `mda dev`, evals, tutorial: [[managed-dev]].

## Quickstart (Python)

```bash
uvx --from managed-deepagents mda init research-assistant   # creates a NEW dir; fails if it exists
cd research-assistant
# .env: OPENAI_API_KEY=...  LANGSMITH_API_KEY=...
uv sync
uv run mda dev        # local Agent Server + opens LangSmith Studio
uv run mda deploy     # hosted deployment; prints dashboard URL
```

Built-in provider search needs no extra key; pass the provider tool dict matching the model:

| Model | `tools=` entry |
| - | - |
| `openai:gpt-5.5` | `{"type": "web_search"}` |
| `google_genai:gemini-3.6-flash` | `{"google_search": {}}` |
| `anthropic:claude-sonnet-4-6` | `{"type": "web_search_20260209", "name": "web_search"}` |
| Microsoft Foundry (`AzureAIOpenAIApiChatModel` instance, `uv add langchain-azure-ai`) | `{"type": "web_search"}` |

If search never shows in the trace, the dict does not match the model provider.

## CLI reference (`mda`)

| Command | Purpose |
| - | - |
| `mda init <name>` | Scaffold project. Flags: `--instructions TEXT`, `--instructions-file PATH\|-`, `--identity`, `--memory agent\|none`, `--model provider:model`, `--no-sandbox`, `--channel slack` (repeatable), `--gateway` |
| `mda build [path]` | Compile to `<path>/.mda/build` (`--out`); does NOT validate the definition call |
| `mda dev [path]` | Compile + run local LangGraph dev server (`--port`, `--hostname`, `--no-browser`, `--no-reload`, `--no-schedules`; creates `schedules/` on the local server since 0.9.3) |
| `mda deploy [path]` | Compile, sync Context Hub, upload, deploy |
| `mda logs [path]` | Tail Agent Server logs (`--lines 1000`, `--level`, `--follow/--no-follow`) |
| `mda delete` / `mda destroy` | Delete deployment + tracing project + Context Hub repo + sandboxes/snapshots/registry + crons (`--yes`) |
| `mda connections catalog\|create\|list\|get\|delete` | Workspace credentials, see [[managed-capabilities]] |
| `mda channels init slack` | Add `channels/slack.py` |
| `mda evals init [-i]` | Harbor eval workspace, see [[managed-dev]] |
| `mda chat` | Terminal chat client (added 0.8.3; since 0.8.6 starts its own dev server if none runs; changelog only) |

Scaffold language follows the install channel: PyPI package always writes Python and refuses a TypeScript project.

### `mda deploy`

Flags: `--name` (default: agent `name`), `--deployment-type dev|prod` (default `dev`, only on create), `--workspace-id` (overrides `LANGSMITH_WORKSPACE_ID`), `--context-strategy overwrite|keep-hub` (required in non-interactive shells when Hub copy changed), `--no-wait`. The 0.8.6 changelog also adds `--yes` (confirm first-deploy overwrites unattended) and `--agent-environment`; the docs don't list them yet.

Region: set `LANGSMITH_ENDPOINT` in `.env` or the shell before the first deploy (for example `https://eu.api.smith.langchain.com`). Credentials must belong to that region, and it also picks the region browser sign-in uses. In CI there is no browser sign-in, so set `LANGSMITH_API_KEY` for the target region.

Steps: validate + load entry -> resolve LangSmith key/workspace -> collect non-reserved `.env` values as deployment secrets -> verify model provider key exists (`.env`, shell, or workspace secrets) -> sync `instructions.md` + `skills/` to Context Hub -> compile to `.mda/build`, extract `schedules/` + `channels/` -> create/find deployment by name -> archive + upload + remote build -> poll until `DEPLOYED` -> reconcile crons -> provision Slack.

Routing of inputs:

```text
instructions.md + skills/**  -> Context Hub deploy-owned context
.env                         -> deploy auth + non-reserved hosted secrets, not archived
project source files         -> .mda/build source archive -> hosted deployment
schedules/**                 -> LangSmith cron jobs after the deployment is live
```

Auth key lookup order: `LANGGRAPH_HOST_API_KEY`, `LANGSMITH_API_KEY`, `LANGCHAIN_API_KEY` (project `.env` first, then process env; an interactive terminal prompts for a key, saved to `.env`, or offers browser sign-in). Reserved platform vars (`LANGSMITH_API_KEY`, `LANGGRAPH_HOST_API_KEY`, `LANGCHAIN_API_KEY`, `LANGSMITH_WORKSPACE_ID`) are never uploaded as deployment secrets.

Python version (needs `managed-deepagents>=0.8.0`): image is 3.11-3.14, newest allowed by `requires-python` unless pinned:

```toml
[tool.mda]
python-version = "3.14"   # quoted major.minor only
```

Per-build override: `MDA_PYTHON_VERSION=3.12 uv run mda deploy`. Affects deployment image only (not `mda dev`, Harbor, or sandboxes).

## Per-run configuration (agent factory, 0.9.0)

Export a function named `agent` instead of a definition. It gets a `ManagedServerRuntime` (the LangGraph `ServerRuntime` plus `channel` and `backend`) and returns `define_deep_agent(...)`. Read run context from `runtime.execution_runtime.context`; `execution_runtime` is `None` when Agent Server loads the graph for inspection, and context is `None` on channel runs.

```python
from typing import TypedDict
from managed_deepagents import ManagedServerRuntime, define_deep_agent

class AppContext(TypedDict, total=False):
    repository: str

def agent(runtime: ManagedServerRuntime[AppContext]):
    execution = runtime.execution_runtime
    context = execution.context if execution is not None else None
    py = context is not None and context.get("repository") == "payments-service"
    return define_deep_agent(
        name="open-swe",                       # inline string: mda build reads it without calling the factory
        model="openai:gpt-5.5",
        instructions="Follow the payments conventions." if py else "Follow the storefront conventions.",
        skills=["./skills/python-service" if py else "./skills/typescript-web"],
        context_schema=AppContext,
    )
```

- Factory-only fields: `instructions` (omit = `instructions.md`, `""` = none), `skills` (paths ending `skills/<name>`; `[]` = none), `mcp` (`[]` = none), `sandbox` (`None` = off). Static definitions can't set them.
- The factory runs at the start of every run and again on resume or retry: no side effects, same definition for the same context, keep any interrupting middleware in every configuration, install the integration package for every model it can return.
- Callers pick the configuration with `client.runs.create(..., context={...})`. Context is not verified identity; authorize in tools against `runtime.server_info.principal`.

## Model options

- `provider:model` string (key in `.env`), or a LangChain chat model instance.
- LLM Gateway: `model="langsmith:moonshotai/kimi-k3"` (slash between provider/model; colon for direct providers). LangChain-hosted models bill Gateway Credits; `langsmith:anthropic/...` uses your workspace provider secret. `mda init --gateway` scaffolds this.

## Choose MDA vs the OSS SDK

| Need | OSS `deepagents` | MDA |
| - | - | - |
| Hosting | Your process/container or a LangSmith deployment | `mda deploy`, Agent Server |
| Filesystem/shell | Any [[backends]] incl. provider [[sandboxes]] | One managed LangSmith sandbox, or thread-scoped state |
| Cross-thread memory | You wire a store ([[memory]], [[persistence]]) | `memory.py` (Context Hub) |
| End-user third-party creds | You store them | Connections + managed OAuth |
| Chat surfaces / cron | You build them | `channels/`, `schedules/` |
| Custom routes / app code | Yes | No; use a plain LangSmith deployment |

Stay on OSS when you need: a custom `BackendProtocol`, your own store/checkpointer, custom HTTP routes/app code, a Python `state_schema` (`define_deep_agent` rejects it; TS `defineDeepAgent` accepts `stateSchema`), non-US or self-hosted, or stdio MCP. Building on OSS first and moving later is the documented path ([[production]], [[products]]).

## Migrating from `create_deep_agent`

Convert in place (not `mda init`). `uv add managed-deepagents`, pin to `mda --version`.

| `create_deep_agent` param | MDA |
| - | - |
| `model`, `tools`, `middleware`, `subagents`, `interrupt_on`, `response_format`, `context_schema`, `cache`, `debug` | Unchanged on `define_deep_agent` |
| `name` | Required, static string (graph ID, `assistant_id`, default deployment name) |
| `system_prompt` | Move to `instructions.md` |
| `skills` | Move to `skills/<name>/SKILL.md` ([[skills]]) |
| `memory` | `memory.py` (new tree is EMPTY; old AGENTS.md content does not transfer) |
| `backend` | `sandbox/__init__.py` with `define_sandbox(...)`, or nothing |
| `permissions` | Accepted, but cleared when `sandbox/` exists ([[permissions]]) |
| `store`, `checkpointer` | Delete; runtime owns them |
| `state_schema` | No equivalent |

Other migration rules:
- The `define_deep_agent(...)` call must be physically in root `agent.py`; re-exporting from another module fails with an error that misleadingly names `name`.
- Hatchling projects need `[tool.hatch.metadata] allow-direct-references = true` (`mda build` rewrites the requirement into a path ref; otherwise `mda dev` fails installing with `Dependency #N ... cannot be a direct reference`).
- `.gitignore`: `.env`, `.env.*`, `.mda/`. `mda build` copies the whole project root into `.mda/build` and deploy uploads it; build limit 200 MB.
- A leftover managed param (e.g. `backend=`) passes `mda build` (exit 0) and only fails at graph load under `mda dev` (0.8.3 changelog: "Catch unsupported agent settings during build" may tighten this).

## Recent changelog highlights

- 0.9.x (2026-10-07 to 2026-10-20): per-run agent factory; runtime `schedules` SDK (create, list, update, delete schedules from tools or middleware; `cron` or `at`); **breaking** channel code reads `runtime.channel.event` / `runtime.channel.raw_event` instead of `runtime.context.channel["event"]`; memory `allow` callbacks deprecated in favour of selecting memory in the factory; Slack `upload_files(paths)` batches and an `eyes` reaction on pickup (`reactions=False` turns it off); per-call HITL (`HumanInTheLoopMiddleware(interrupt_mode="per_call")`, `mda dev` then needs `langgraph-api` 0.16+); `sandbox/setup.sh` for dynamic agents; Agent Auth user-scoped secrets; writes to unmounted memory layers now fail instead of being dropped (0.9.4).

- 0.8.0 (2026-09-24): agent + user memory layers (`define_memory(agent=MemoryLayer(), user=MemoryLayer())`), `runtime.backend` sandbox file API, `[tool.mda].python-version`, HTTP channels, agent-owned prompt responses (`INTERRUPT_CORRELATION_KEY`), Slack file transfer, OAuth client credentials, connections in sandbox proxy headers, LangSmith Managed Tools (e.g. Parallel search via `define_mcp`), telemetry (`MDA_TELEMETRY_DISABLED=1` / `DO_NOT_TRACK=1`). Channel API: `runtime.channel`, `post({"type": "content"|"native", ...})`.
- 0.7.x: `connectors.mcp` -> `define_mcp`, `mcp_servers` -> `servers`; `runtime.identity` removed -> `runtime.server_info.principal`; OAuth catalog, `--authorize`, `--mcp`; channel threads owned by source conversation (in-flight Slack conversations stopped responding after upgrade); MDA default recursion limit removed (0.7.3).
- 0.5.3: `mda deploy` stopped reading deployment secrets from the shell (later docs say shell provider key is forwarded; see Gotchas).
- 0.5.0: durable memory made opt-in; identity reduced to `auth=` only; guest ingress removed.

## Gotchas

- Beta on LangSmith Cloud; LangSmith managed tools are GCP US only. The runtime page now documents direct Agent Server calls (`client.runs.create(thread_id, "<name>", input=..., context=...)`); treat the Agent Server API as the contract.
- `define_deep_agent` has no `backend`/`store`/`checkpointer`/`system_prompt`/`skills`/`memory`/`state_schema`. Middleware must use **async** hooks: MDA always calls `ainvoke`/`astream`.
- Declaring `sandbox/` clears `permissions`. OSS code agrees with the reason: in 0.7.29 `FilesystemMiddleware` raises `NotImplementedError` for permissions plus an execution-capable backend unless every rule is scoped to CompositeBackend routes.
- Doc contradiction on memory: migrate page shows `define_memory(scope="agent")`; memory page and 0.8.0 changelog use `MemoryLayer` and say string scopes are rejected. For >=0.8.0 use `define_memory(agent=MemoryLayer())`.
- Doc contradiction on secrets: deploy/CLI pages say a provider key only in the shell is forwarded; 0.5.3 changelog says shell values are no longer read for deployment secrets. Put keys in `.env` or workspace secrets to be safe.
- Doc contradiction on per-run memory: the agent-definition page says memory is not selected per run and access is controlled with an `allow` policy; the 0.9.0 changelog deprecates `allow` callbacks and says to select memory in the factory with `define_memory(...)`. Prefer the changelog, and check the memory page before relying on either.
- `--no-wait` skips cron reconciliation and is not allowed with a Slack channel.
- mcp-endpoint page says deploy prints only the dashboard URL; 0.5.0 changelog says it also prints the Agent Server URL.

## Sources

- `../sources/docs/langsmith/python/managed-deep-agents-overview.md`
- `../sources/docs/langsmith/python/managed-deep-agents-quickstart.md`
- `../sources/docs/langsmith/python/managed-deep-agents-migrate.md`
- `../sources/docs/langsmith/python/managed-deep-agents-deploy.md`
- `../sources/docs/langsmith/python/managed-deep-agents-cli.md`
- `../sources/docs/langsmith/python/managed-deep-agents-runtime.md`
- `../sources/docs/github/managed-deepagents-CHANGELOG.md`
- `../sources/docs/langsmith/python/managed-deep-agents-agent-definition.md`
- `../sources/package/deepagents/graph.py` (create_deep_agent signature, for param mapping)
- `../sources/package/deepagents/middleware/filesystem.py` (permissions + execute backend check)

## See also

- [[index]]
- [[managed-project]]
- [[managed-capabilities]]
- [[managed-channels]]
- [[managed-dev]]
- [[create-deep-agent]]
- [[products]]
- [[versions]]
