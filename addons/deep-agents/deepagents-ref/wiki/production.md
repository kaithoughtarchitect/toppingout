---
title: Going to production
id: production
type: how-to
status: code
product: sdk
keywords: production, deploy, deployment, langgraph.json, LangSmith Deployment, thread_id, context_schema, multi-tenant, per-user memory, namespace, sandbox lifecycle, checkpointer, go live, self-hosted
read_when: Read when moving an agent to production, setting up thread_id/context/multi-tenancy, or choosing where the checkpointer and store come from.
updated: 2026-10-21
sources_hash: 7a60770614b5
---

# Going to production

One-line truth: a production deep agent = a compiled graph plus a durable checkpointer, a durable store, a stable `thread_id` per conversation, per-run `context`, an isolated execution environment, and guardrail middleware; LangSmith Deployment (or [[managed]]) provisions the checkpointer/store for you, self-hosting means you must supply them yourself (see [[persistence]]).

## Quick reference

- Production = compiled graph + durable checkpointer + durable store + stable `thread_id` + per-run `context` + isolated execution + guardrails.
- On LangSmith Deployment omit `checkpointer=` and `store=`; the platform injects them.
- `langgraph.json` maps `graphs` to `./file.py:variable` (compiled graph or factory); `langgraph dev` serves localhost:2024.
- `thread_id` scopes history and StateBackend files; `context` is per-run data read via `runtime.context`.
- Cross-thread memory: route `/memories/` to `StoreBackend(namespace=...)` including the user id.
- Never deploy `FilesystemBackend` or `LocalShellBackend`; use a sandbox backend for code.
- `StoreBackend.__init__(*, namespace, store=None)` is keyword-only; the docs' `StoreBackend(rt, ...)` is a `TypeError`.
- `rt.server_info` is only populated on LangGraph server; self-hosted read ids from `rt.context`.
- `create_deep_agent` already sets `recursion_limit` 9999; only raise it client-side.
- Keep `StateBackend` as default so internal artifacts do not land in the durable store.

## Deployment paths

| Path | What you author | Who provisions checkpointer + store |
| - | - | - |
| [[managed]] (Managed Deep Agents, public beta, LangSmith Cloud) | A project of files, declared for the managed runtime; you do not compile the graph | Platform |
| LangSmith Deployment (LangGraph server) | `agent.py` exporting a compiled graph or a graph factory + `langgraph.json` | Platform (threads, runs, store, checkpointer, auth, webhooks, cron, MCP/A2A exposure) |
| Self-hosted (plain Python process) | Your own server calling `agent.invoke/ainvoke` | You: `create_deep_agent(checkpointer=..., store=...)` |

Docs recommend Managed Deep Agents first; use a LangSmith Deployment when you need custom routes, custom app code or advanced auth.

### langgraph.json

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./agent.py:agent"
  },
  "env": ".env"
}
```

- `dependencies`: `["."]` installs the current dir (reads `requirements.txt` / `pyproject.toml`).
- `graphs`: `"<graph_id>": "./<file>:<variable>"`; `<variable>` is a compiled graph or a (possibly async) factory function. `graph_id` is what clients pass as the assistant (`"agent"` below).
- `env`: `.env` path. Same file drives `langgraph dev` (local, `http://localhost:2024`) and `langgraph deploy`.
- Multiple agents in one deployment: add more `graphs` entries (e.g. a `consolidation_agent`, see [[memory]]).

When deployed, omit `checkpointer=` and `store=` from `create_deep_agent`; the platform injects them (docs: "omit the `store` parameter" for LangSmith Deployment).

## Invoking: thread_id + context

Every call carries two independent things:

```python
from dataclasses import dataclass
from deepagents import create_deep_agent
from langchain_core.utils.uuid import uuid7

@dataclass
class Context:
    user_id: str

agent = create_deep_agent(model="anthropic:claude-sonnet-5", context_schema=Context)

config = {"configurable": {"thread_id": str(uuid7())}}   # conversation identity
agent.invoke({"messages": [{"role": "user", "content": "Plan a 3-day trip"}]},
             config=config, context=Context(user_id="user-123"))
agent.invoke({"messages": [{"role": "user", "content": "Make it 5 days"}]},
             config=config, context=Context(user_id="user-123"))  # same thread_id = same conversation
```

- `thread_id` scopes message history, checkpoints and `StateBackend` files. New `thread_id` = fresh conversation.
- `context` is per-run data (user id, keys, flags) read via `runtime.context` in tools/middleware/namespace factories. See [[context-engineering]].
- Through the SDK against a deployment:

```python
from langgraph_sdk import get_client
client = get_client(url="<DEPLOYMENT_URL>", api_key="<LANGSMITH_API_KEY>")
thread = await client.threads.create()
async for chunk in client.runs.stream(thread["thread_id"], "agent",
        input={"messages": [{"role": "user", "content": "hi"}]},
        context={"user_id": "user-123"}, stream_mode="updates"):
    print(chunk.data)
```

## Multi-tenancy and credentials

- End-user identity: LangSmith custom auth + authorization handlers (tag owner metadata, return filters, 403). Available in tools/namespace factories as `runtime.server_info.user.identity` (deepagents>=0.5.0; server only).
- Team RBAC (Admin / Editor / Viewer) is separate from end-user auth.
- Per-user OAuth: `langchain_auth.Client().authenticate(provider=..., scopes=[...], user_id=runtime.server_info.user.identity)` inside a tool; first use interrupts with a consent URL.
- Shared API keys: LangSmith workspace secrets (env vars at runtime).
- Sandbox code: use the sandbox auth proxy (`proxy_config.rules[].match_hosts` + `inject_headers` with `${SECRET}` refs resolved from workspace secrets). Never pass secrets into a sandbox via env vars or uploaded files; the agent can read them.

## Memory scoping

Default filesystem is `StateBackend` (thread-scoped). Cross-thread memory = route a prefix to `StoreBackend` inside a `CompositeBackend`:

```python
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

backend = CompositeBackend(
    default=StateBackend(),
    routes={"/memories/": StoreBackend(
        namespace=lambda rt: (rt.server_info.assistant_id, rt.server_info.user.identity))},
)
```

| Scope | Namespace | Use |
| - | - | - |
| User (recommended default) | `(user_id,)` | preferences |
| Assistant | `(assistant_id,)` | shared instructions for one assistant |
| Global / org | `(org_id,)` | read-only policies; write only from app code |

Shared (non-user) memory is a prompt-injection vector: make it read-only with [[permissions]] or backend policy hooks. Full detail: [[memory]], [[backends]], [[persistence]].

## Execution environment

- File I/O only: `StateBackend` / `StoreBackend` / `CompositeBackend` / `ContextHubBackend` (LangSmith Hub repo persistence, no LangGraph store needed).
- Needs to run code: a sandbox backend ([[sandboxes]]), which adds the `execute` tool in an isolated container.
- Never deploy `FilesystemBackend` or `LocalShellBackend`: they touch the host.

Sandbox lifecycle via an async graph factory (server calls it per run and injects `RunnableConfig`; factories get no `Runtime`, so read ids from `config["configurable"]`):

```python
from deepagents import create_deep_agent
from deepagents.backends.langsmith import LangSmithSandbox
from langchain_core.runnables import RunnableConfig
from langsmith.sandbox import SandboxClient

client = SandboxClient()

async def agent(config: RunnableConfig):
    name = f"thread-{config['configurable']['thread_id']}"   # or f"assistant-{...['assistant_id']}"
    existing = [sb for sb in client.list_sandboxes() if getattr(sb, "name", None) == name]
    sb = existing[0] if existing else client.create_sandbox(name=name, idle_ttl_seconds=3600)
    return create_deep_agent(model="anthropic:claude-sonnet-5", backend=LangSmithSandbox(sandbox=sb))
```

- Thread-scoped (most common): fresh per conversation, TTL cleanup. Assistant-scoped: shared repo/deps across threads; needs TTL/snapshots/cleanup or it grows unbounded.
- Move data across the boundary with `backend.upload_files([(path, bytes)])` / `backend.download_files([paths])` (seed skills/memories before, pull artifacts after). A `before_agent`/`after_agent` middleware can sync store <-> sandbox.

## Async, durability, frontend

- Prefer async tools and async middleware hooks (`abefore_agent`, ...); sandbox/MCP setup should be awaited, which is why factories are async.
- Durability comes from the checkpointer: runs resume from the last checkpoint after crash/timeout/interrupt; enables indefinite HITL pauses ([[human-in-the-loop]]) and time travel.
- Frontend: `useStream` (React/Vue/Svelte/Angular) pointed at the deployment URL; pass `streamSubgraphs: true` and a high `recursionLimit`. See [[frontend]], [[streaming]].

## Resilience checklist

- [ ] Durable checkpointer (platform, or Postgres/SQLite self-hosted) and durable store; prove it with a restart test ([[persistence]]).
- [ ] Stable `thread_id` per conversation; `context` per run; `context_schema` set.
- [ ] Every `StoreBackend` has an explicit namespace that includes the user (or tenant) id.
- [ ] Shared memory paths read-only via [[permissions]].
- [ ] Sandbox (not local shell) for code; secrets via auth proxy; sandbox TTL set.
- [ ] Retries, fallback model, call limits, tool error handling ([[fault-tolerance]]); add them to subagent specs too.
- [ ] `interrupt_on` / permission `mode="interrupt"` for irreversible tools (requires checkpointer).
- [ ] `PIIMiddleware("email", strategy="redact", apply_to_input=True)` etc. if user data may contain PII (strategies: `redact`, `mask`, `hash`, `block`).
- [ ] LangSmith tracing on (`LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`).

## Gotchas

- The docs' "sync skills and memories" example constructs `StoreBackend(rt, namespace=...)` with an undefined `rt`. In 0.7.29 `StoreBackend.__init__(self, *, namespace, store=None)` is keyword-only; positional `rt` is a `TypeError`. Use `StoreBackend(namespace=...)`.
- `rt.server_info` is only populated on LangGraph server. In a plain local `agent.invoke`, a namespace lambda reading `rt.server_info.user.identity` raises. For self-hosting read ids from `rt.context` instead.
- `create_deep_agent` already applies `.with_config({"recursion_limit": 9_999, ...})` (graph.py). You only need a higher limit on the client side (the frontend docs suggest `recursionLimit: 10000`).
- Deep Agents write internal artifacts (`/conversation_history/...`, `/large_tool_results/...`) to the default backend (the root of `CompositeBackend.artifacts_root`). Keep `StateBackend` as the default so these don't land in a durable store or on disk.
- A graph factory is invoked every run; the sandbox lookup-by-name is what gives reuse. Without it you create a new sandbox per run.

## Sources

- `../sources/docs/oss/python/deepagents/going-to-production.md`
- `../sources/docs/oss/python/deepagents/memory.md`
- `../sources/docs/oss/python/deepagents/backends.md`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/backends/store.py`
- `../sources/package/deepagents/backends/langsmith.py`
- `../sources/package/deepagents/middleware/summarization.py`

## See also

- [[index]]
- [[persistence]]
- [[fault-tolerance]]
- [[sandboxes]]
- [[backends]]
- [[memory]]
- [[permissions]]
- [[human-in-the-loop]]
- [[managed]]
- [[frontend]]
- [[create-deep-agent]]
- [[context-engineering]]
- [[middleware]]
- [[streaming]]
