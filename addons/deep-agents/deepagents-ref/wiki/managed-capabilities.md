---
title: MDA capabilities (skills, tools, MCP, connections, middleware, memory, sandbox, Context Hub)
id: managed-capabilities
type: how-to
status: sourced
product: managed
keywords: MDA tools, define_mcp, MCP connectors, connections, connections.get, OAuth, mda connections create, define_memory, MemoryLayer, durable memory, remember across sessions, define_sandbox, sandbox setup.sh, runtime.backend, Context Hub, async middleware, ManagedDeepAgentRuntime, ManagedToolRuntime, ManagedRuntime
read_when: Read when adding tools, MCP servers, OAuth connections, memory or a sandbox to a Managed Deep Agent, or when memory or a connection does nothing.
updated: 2026-10-21
sources_hash: b3fe819d47b6
---

# MDA capabilities (skills, tools, MCP, connections, middleware, memory, sandbox, Context Hub)

How to give a Managed Deep Agent its abilities: which file to add, the exact `managed_deepagents` API, and what the runtime does with it. Layout rules are in [[managed-project]]; the product overview is [[managed]].

## Quick reference

- Tools and middleware are never auto-discovered; import them and pass `tools=` and `middleware=`. Custom middleware must be async.
- Skills in `skills/<name>/SKILL.md` are auto-discovered; do not pass `skills=`. Deploy prunes deployed skill files missing locally.
- `tools/mcp.py` exports `mcp = define_mcp(servers={...})`; http or sse only, no stdio; one declaration per project.
- `connections.get(slug, {'type': 'agent' or 'user'})`: await it inside tools, pass it un-awaited inside `define_mcp` or `define_sandbox`.
- Agent-owned connection missing fails the run; user-owned missing raises a `credential_authorization_required` interrupt. Locally, agent-owned opaque ones read `MDA_DEV_<SLUG>`.
- Memory is off by default: `memory = define_memory(agent=MemoryLayer(), user=MemoryLayer())` in `memory.py` (>=0.8.0). `AGENTS.md` at a mount root is hot memory.
- User memory and user-owned connections need a person principal; the default API-key identity is a service and gets neither.
- Sandbox: `define_sandbox(idle_ttl_seconds=600, default_timeout=600, proxy_config=...)`; declaring it clears `permissions`; `runtime.backend` is None without one.
- `sandbox/setup.sh` runs once and is baked into a snapshot; existing threads keep their old `/workspace`.
- Gotcha: do not call `connections.get` in channel `verify` or `parse`; use env vars.

## Skills (`skills/<name>/SKILL.md`)

- Same format as OSS [[skills]]: YAML frontmatter `name` + `description`, body loaded on demand (progressive disclosure). Supporting files (`templates/`, `scripts/`) are fine; reference them from `SKILL.md`.
- Auto-discovered; do NOT pass `skills=` to `define_deep_agent`.
- `mda deploy` syncs every UTF-8 file under `skills/` to Context Hub and **removes deployed skill files missing locally**. Read-only to the agent.

## Tools (`tools/*.py`)

Not auto-discovered: import and pass in `tools=`. Plain LangChain tools ([[tools]]).

```python
# tools/customer.py
from langchain.tools import tool

@tool(parse_docstring=True)
def lookup_customer(customer_id: str) -> str:
    """Look up a customer record by ID.

    Args:
        customer_id: Customer ID from the CRM.
    """
    return f"Customer {customer_id} is on the enterprise plan."
```

- Secrets: read `os.environ` (from `.env` locally, forwarded on deploy) or better, a connection.
- HITL: `interrupt_on={"lookup_customer": True}` ([[human-in-the-loop]]); managed checkpointer, nothing to set up. Resume a deployed run with `Command(resume=...)` via Agent Server API.
- Typed runtime: annotate `runtime: ManagedToolRuntime[Context, State]` (`ManagedDeepAgentRuntime` is an alias) to get `runtime.backend` (sandbox), `runtime.channel` (`None` on direct API and schedule runs), `runtime.server_info` (caller principal: `runtime.server_info.principal.id`, `.kind` in `person|service|channel`, `.claims["email"]`, `.claims["groups"]`). Middleware hooks keep `Runtime[Context]`; narrow with `isinstance(runtime, ManagedRuntime)`. Agent factories get `ManagedServerRuntime` ([[managed]]). `runtime.identity` was removed in 0.7.0.

## MCP connectors (`tools/mcp.py`)

```python
from managed_deepagents import connections, define_mcp

mcp = define_mcp(
    servers={
        "langchainDocs": {
            "transport": "http",                 # "http" (Streamable HTTP) or "sse"
            "url": "https://docs.langchain.com/mcp",
            "include_tools": ["search_docs_by_lang_chain"],
        },
        "notion": {
            "transport": "http",
            "url": "https://mcp.notion.com/mcp",
            "connection": connections.get("engineering-notion", {"type": "user"}),  # no await here
        },
    },
)
```

- One declaration per project, module-level `mcp`. No stdio servers.
- Per-server: `transport`, `url` (required), `headers`, `include_tools`, `exclude_tools` (applied after include; a tool cannot be in both), `default_tool_timeout` (seconds in Python), `automatic_sse_fallback`, `reconnect`, `connection`.
- Definition-level: `prefix_tool_name_with_server_name=True` (tools exposed as `{server}__{tool}`; filters use raw names), `throw_on_load_error=True`.
- Renamed in 0.7.0: `connectors.mcp` -> `define_mcp`, `mcp_servers` -> `servers` (old aliases slated for removal in 0.8.0).
- See OSS [[mcp]] for adapter concepts.

### Built-in Parallel search (LangSmith Managed Tools)

No Parallel key; needs `LANGSMITH_WORKSPACE_ID` and a personal `LANGSMITH_API_KEY` in `.env`. Plus/Startup plans only, and LangSmith managed tools run in the GCP US region only.

```python
mcp = define_mcp(servers={"Parallel": {
    "transport": "http",
    "url": "https://api.smith.langchain.com/v1/managed-tools/servers/parallel/mcp",
}})
```

## Connections (workspace credentials)

`connections.get(slug, {"type": "agent"|"user"})` resolves a string credential at runtime. `await` it inside tools; pass the un-awaited reference inside `define_mcp` / `define_sandbox`.

| Owner | Resolves to | Missing credential |
| - | - | - |
| `agent` | One credential owned by this deployment | Run fails (`no agent connection is set for slug '<slug>'`) |
| `user` | The authenticated caller's own OAuth grant | `credential_authorization_required` interrupt before first model turn |

Create modes (the mode sets the owner; there is no `--owner`):

```bash
# opaque secret -> agent-owned
uv run mda connections create organization-tavily --secret-from-env TAVILY_API_KEY
# general OAuth (BYOT) -> per-caller; add --authorize to store one agent-owned grant
uv run mda connections create frontend-github --oauth github --client-id "..." --secret-from-env GITHUB_CLIENT_SECRET
# client credentials -> agent-owned, no browser
uv run mda connections create acme-api --grant-type client_credentials \
  --token-url https://auth.acme.com/oauth/token --client-id "..." --secret-from-env ACME_CLIENT_SECRET --scope read
# MCP OAuth (discovery + dynamic registration) -> per-caller
uv run mda connections create engineering-notion --mcp https://mcp.notion.com/mcp
```

- Slug is your name (lowercase, single hyphens); provider goes to `--oauth`. Catalog: `mda connections catalog` (github, google, linear, slack, atlassian, notion-api, stripe-link, x, ...). Custom providers: `--authorize-url` + `--token-url` + `--scope` (no scope = most providers refuse).
- Agent-owned credentials belong to one deployment: create after the first successful deploy, and re-run `create` from each project root that needs the same slug.
- Local: agent-owned opaque connections read `MDA_DEV_<SLUG>` (upper-cased, hyphens -> underscores), e.g. `MDA_DEV_ORGANIZATION_TAVILY`.
- Custom frontend handling the interrupt: open each `connect_url`, poll `GET /v1/agent-auth/oauth-authorization-sessions/{auth_id}?wait_seconds=25`, resume with `{"type": "credential_authorization_completed", "connected_slugs": [...]}`. Slack and Studio handle it automatically.
- Limits: Slack/Studio cannot collect per-user API keys; no connections UI in LangSmith; `list` is workspace-wide and does not show which deployment holds a credential.

## Middleware (`middleware/`)

Import and pass in `middleware=` (LangChain built-ins like `PIIMiddleware`, `ModelCallLimitMiddleware` work). See [[middleware]]. Custom middleware **must be async** because MDA always runs `ainvoke`/`astream`:

```python
from langchain.agents.middleware import wrap_tool_call

@wrap_tool_call
async def log_tool_calls(request, handler):
    result = await handler(request)
    return result
```

Middleware cannot replace the runtime-owned backend, store, checkpointer, memory, skills or system prompt.

## Durable memory (`memory.py`, >=0.8.0)

Off by default. Two independent Context Hub-backed layers:

| Layer | Mount | Scope | Default policy |
| - | - | - | - |
| `agent` | `/memories/agent/` | Whole deployment, every caller | Allowed everywhere |
| `user` | `/memories/user/` | One authenticated **person** | Only Slack 1:1 DM and verified Studio users |

```python
from managed_deepagents import MemoryLayer, define_memory

memory = define_memory(
    agent=MemoryLayer(),
    user=MemoryLayer(allow=lambda context: context.get("remember") is True),
)
```

- `allow(context)` (sync or async) runs once per run before mounting; denial removes that layer's mount and hot memory for that run (data not deleted). It can widen only within the already-authenticated person; never grants user memory to a service principal (e.g. LangSmith API-key identity) or selects another person.
- The memory page's DM example reads `context.channel.get("raw_event")` from a `ManagedChannelContext`, but since 0.9.0 channel runs get `context = None` and the delivery moved to `runtime.channel.raw_event` (runtime page, 0.9.0 changelog). The example is stale; don't copy it. Slack `channel_type == "im"` = DM.
- 0.9.0 deprecates `allow` callbacks: select memory per run in an agent factory with `define_memory(...)` instead ([[managed]]). Root `memory.py` stays the fallback; factory-selected memory can't have `allow`. Since 0.9.4, writes to a layer that isn't mounted fail instead of being silently dropped.
- `AGENTS.md` at each mount root is hot memory, injected into every model call (not saved in thread state). Other files are cold, read on demand with `read_file`. Writes elsewhere under `/memories/` are not durable. See OSS [[memory]].
- Deploy never overwrites stored memory. `mda dev` memory lives in `.mda/__contexthub__` and is separate from deployed memory.
- Agent memory is a trust boundary: any caller can write content later callers read. No secrets/PII; never let memory grant authority.
- Pre-0.8 legacy: `define_memory(scope="agent")`. 0.8.0 changelog says string scopes are now rejected (object-based legacy scope still works); the migrate page still shows the string form.

## Sandbox (`sandbox/__init__.py`)

Scaffolded by `mda init` (omit with `--no-sandbox`); enabled only while `sandbox/` exists. LangSmith Sandboxes, one per durable thread.

```python
from managed_deepagents import bearer, connections, define_sandbox

github = connections.get("github", {"type": "user"})

sandbox = define_sandbox(
    idle_ttl_seconds=600,     # default 600; sandbox + files deleted after idle, unrecoverable
    default_timeout=600,      # default 600; per-command seconds
    proxy_config={
        "rules": [{"name": "github-api", "match_hosts": ["api.github.com"],
                   "headers": [{"name": "Authorization", "value": bearer(github)}]}],
        "access_control": {"allow_list": ["api.github.com"]},
    },
)
```

- Proxy headers: `{"type": "workspace_secret", "value": "Bearer {OPENAI_API_KEY}"}`, or a connection ref / `bearer(ref)` / `basic(username, ref)` (type auto `opaque`). Credentials never enter the sandbox.
- `sandbox/setup.sh` (not scaffolded): run once with `bash -e` on deploy/dev, baked into a snapshot; new threads clone it; rebuilt when the script changes. Forwarded `.env` values are visible during setup only; do not write secrets to disk. Existing threads keep their `/workspace`.
- Bake base: exactly one of `snapshot_name`, `snapshot_id`, `docker_image`; private image via `registry={"url":..., "username":..., "password_env": "GHCR_TOKEN"}`.
- Agent gets OSS [[filesystem-tools]] plus `execute`. Declaring a sandbox clears `permissions` ([[permissions]]).
- `runtime.backend` (>=0.8.0) in tools/middleware: OSS backend contract ([[backends]], [[sandboxes]]): `ls`, `read`, `write`, `edit`, `delete`, `grep`, `glob`, `execute`, `upload_files([(path, bytes)])`, `download_files([paths])` plus `a*` async twins. Results carry `.error` (`file_not_found|permission_denied|is_directory|invalid_path`). `None` when no sandbox; guard every call. Cannot reach Context Hub (skills, instructions, memory). Lazy: never touching it never provisions a sandbox.
- `mda dev` falls back to a local temp dir if the provider is unavailable.
- 0.9.x changelog: a factory-built (dynamic) agent's `sandbox/setup.sh` is baked even without a sandbox declaration, on the default image; a run that picks a different base fails. Sandbox identity comes from image and box-shape options only, so changing `idle_ttl_seconds` or `default_timeout` keeps the thread's sandbox and applies to new ones.

## Context Hub

| Content | Source | Synced on deploy | Agent-writable |
| - | - | - | - |
| System prompt | `instructions.md` | Yes | No |
| Skills | `skills/` | Yes (and prunes) | No |
| Memory | `memory.py` | Enables tree only, never overwrites | Yes |

Everything else (tools, middleware, MCP, channels, schedules, sandbox, agent definition) ships in the build. Hub edits apply live until the next deploy; on conflict deploy prompts (default keeps Hub and skips that section) or, non-interactive, fails until `--context-strategy overwrite|keep-hub`. Concurrent repo change during sync = commit conflict, re-run. `mda dev` uses a local mock.

## Gotchas

- Tools and middleware are never discovered; forgetting to add them to `define_deep_agent` silently omits them.
- Sync-only middleware hooks will not run under MDA.
- `connections.get` needs a run: do not call it in channel `verify`/`parse` (use env).
- User memory and user-owned connections both need a *person* principal; the default LangSmith API-key identity is a service and gets neither.
- `runtime.backend` method names match OSS 0.7.29 `BackendProtocol` (`ls`, `read`, `grep`, `glob`, `write`, `edit`, `delete`, `upload_files`, `download_files`, `execute`), verified in source.

## Sources

- `../sources/docs/langsmith/python/managed-deep-agents-skills.md`
- `../sources/docs/langsmith/python/managed-deep-agents-tools.md`
- `../sources/docs/langsmith/python/managed-deep-agents-search.md`
- `../sources/docs/langsmith/python/managed-deep-agents-connections.md`
- `../sources/docs/langsmith/python/managed-deep-agents-mcp-connectors.md`
- `../sources/docs/langsmith/python/managed-deep-agents-middleware.md`
- `../sources/docs/langsmith/python/managed-deep-agents-memory.md`
- `../sources/docs/langsmith/python/managed-deep-agents-sandboxes.md`
- `../sources/docs/langsmith/python/managed-deep-agents-context-hub.md`
- `../sources/docs/langsmith/python/managed-deep-agents-runtime.md`
- `../sources/docs/github/managed-deepagents-CHANGELOG.md`
- `../sources/package/deepagents/backends/protocol.py` (backend method names, FileOperationError)
- `../sources/package/deepagents/middleware/filesystem.py` (permissions vs execute backend)

## See also

- [[index]]
- [[managed]]
- [[managed-project]]
- [[managed-channels]]
- [[managed-dev]]
