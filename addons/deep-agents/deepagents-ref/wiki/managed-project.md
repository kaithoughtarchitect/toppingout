---
title: MDA project structure, agent definition and instructions
id: managed-project
type: reference
status: sourced
product: managed
keywords: MDA project layout, agent.py, instructions.md, define_deep_agent, agent factory, per-run configuration, shared local package, project structure, system prompt, Context Hub, managed context, skills folder, tools folder, middleware folder, interrupt_on, agent name, assistant_id, .env, hatchling
read_when: Read when unsure where a file goes in an MDA project, what define_deep_agent accepts, or when the name-is-required error appears.
updated: 2026-11-19
sources_hash: 116eb0f5d490
---

# MDA project structure, agent definition and instructions

A Managed Deep Agents project is a normal Python package with one required file, root `agent.py` exporting `agent = define_deep_agent(...)`; every other capability is switched on by the presence of a specific path. Use this page to know where a thing goes and what `define_deep_agent` accepts. Product overview: [[managed]].

## Layout

```text
my-agent/
├── agent.py              # REQUIRED: agent = define_deep_agent(...)
├── instructions.md       # managed context -> system prompt (Context Hub)
├── skills/<name>/SKILL.md  # managed context (Context Hub)
├── tools/                # application code (you import it)
│   └── mcp.py            # RESERVED: managed MCP declaration, exports `mcp`
├── middleware/           # application code (you import it)
├── channels/<name>.py    # managed config, exports `channel`
├── schedules/<name>.py   # managed config, exports `schedule`
├── sandbox/__init__.py   # managed config, exports `sandbox` (+ optional setup.sh)
├── identity.py           # managed config, exports `identity`
├── memory.py             # managed config, exports `memory`
├── browser.py            # managed config, exports `browser` (0.10.0; root file only)
├── AGENTS.md             # scaffolded by mda init for coding agents (0.10.2); left out of build and deploy
├── pyproject.toml        # deps; [tool.mda] python-version
├── .env                  # local + deploy secrets (never archived)
└── evals/                # Harbor workspace (harbor-job.json, <task>/...)
```

Three classes of path:

| Class | Paths | How it reaches the agent |
| - | - | - |
| Managed context | `instructions.md`, `skills/` | Synced to Context Hub on deploy; read-only to the agent |
| Application code | `tools/*` (except `mcp.py`), `middleware/`, any other module | Ordinary imports from `agent.py`; ships in build, not in Context Hub |
| Managed configuration | `identity.py`, `memory.py`, `channels/<name>.py`, `tools/mcp.py`, `schedules/<name>.py`, `sandbox/__init__.py`, `browser.py` | Discovered by path; presence enables the capability |

Rules:
- One agent entry per project. Export name must be exactly `agent`; the `define_deep_agent(...)` call must be written in `agent.py` itself (re-export fails with a misleading "`name` is required" error). Since 0.9.0 `agent` may also be a sync or async factory function returning `define_deep_agent(...)` per run ([[managed]]); `name` must still be an inline string there.
- For `channels/` and `schedules/` only **direct children** are declarations; nested modules are not. File stem = channel/schedule name.
- Each managed module exports a fixed variable: `agent`, `mcp`, `channel`, `schedule`, `sandbox`, `identity`, `memory`, `browser` (`browser.py` is the browser-use page's file, not listed on the project-structure page; see [[managed-capabilities]]).
- `connectors/` is gone: since 0.10.0 `mda` fails the build when a module under it still exports `connector`. Declare MCP servers in `tools/mcp.py`.
- `src/` layout is fine; keep packages where they are and import them from root `agent.py`.
- Evals-generated files live under `.mda/evals/` and are excluded from the deployed build.
- The build copies only the project directory. Code from a sibling directory must be its own package (`pyproject.toml` with `[project]` and `[build-system]`) added as a local dependency, e.g. `uv add ../shared`; MDA then copies it into the build, `mda dev` reloads on edits, and `mda deploy` ships it (0.9.2).

Details for each managed file: MCP/memory/sandbox/connections in [[managed-capabilities]]; channels/identity/schedules in [[managed-channels]]; evals in [[managed-dev]].

## `define_deep_agent`

```python
from managed_deepagents import define_deep_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from tools.customer import lookup_customer

agent = define_deep_agent(
    name="support-agent",                  # required
    model="openai:gpt-6.1-sol",            # or a BaseChatModel instance
    tools=[lookup_customer],
    middleware=[ModelCallLimitMiddleware(run_limit=50)],
    interrupt_on={"lookup_customer": True},
)
```

It returns a definition, not a graph. The runtime compiles it with `create_deep_agent` ([[create-deep-agent]]) and supplies backend, store, checkpointer, system prompt, skills, memory.

| Parameter | Notes |
| - | - |
| `name` | Required. Static string literal matching `[a-zA-Z][a-zA-Z0-9_-]*`. Becomes graph ID, `assistant_id` clients pass, default deployment name (override with `mda deploy --name`), and the tool name on the MCP endpoint. |
| `model` | `provider:model` string (key in `.env`) or chat model instance. Gateway: `"langsmith:provider/model"`. See [[models]]. |
| `tools` | Authored tools / provider tool dicts. Not auto-discovered. |
| `middleware` | Runs in list order. Must use async hooks. |
| `subagents` | Same shape as OSS [[subagents]], plus an optional `mcp` list (>=0.10.2): omitted = inherit (sync) or inherit the agent's MCP servers (async); a list of `define_mcp` definitions = only those (a sync subagent's list must also be loaded by the agent); `[]` or `None` = no MCP tools. Sync `mode: "fork"` subagents cannot set `mcp` (0.10.2 changelog). Only a factory can set `mcp` on the agent itself. Async subagents (`async: true`, 0.10.0) run in the background on the same deployment and share the lead agent's sandbox. |
| `permissions` | Filesystem rules ([[permissions]]). Cleared when `sandbox/` exists. |
| `interrupt_on` | Same as OSS [[human-in-the-loop]]. Slack renders only `approve`/`reject`. |
| `response_format` | Structured output. |
| `routes` | `{"/prefix/": backend}` mounts Deep Agents backends at path prefixes, like `CompositeBackend` routes (>=0.10.3). Prefix must start and end with `/` and must not overlap `/instructions.md`, `/skills/`, `/memories/`. File tools only; sandbox shell commands don't see it. See [[managed-capabilities]]. |
| `context_schema`, `cache`, `debug` | Accepted unchanged (migrate page; not in the agent-definition table). |

Not accepted: `system_prompt`, `backend`, `store`, `checkpointer`, `state_schema` (Python); a static definition also can't set `skills` or `memory`. OSS `create_deep_agent` in 0.7.40 has all of these plus an optional `name` (`graph.py`); MDA makes `name` required. `backend` still cannot be replaced, but since 0.10.3 `routes` can mount extra backends under prefixes. A definition returned by an agent factory may also set `instructions`, `skills`, `mcp`, `sandbox`, `memory` and `browser` to override the project files for that run; static definitions can't ([[managed]]). Wrap a factory in `@cached_agent(keyed_by=...)` (>=0.10.2) to reuse compiled graphs.

## `instructions.md`

- The always-on system prompt, inserted every run. Agent cannot modify it.
- `mda deploy` syncs it to the deployment's Context Hub repo. You can edit it in the LangSmith UI for a live change without redeploy, but the next deploy re-syncs the project copy (conflict prompt, or `--context-strategy overwrite|keep-hub`).
- Keep the repo copy as source of truth for lasting changes.
- Do not restate memory mechanics here: the runtime injects a memory-policy message on every model call when memory is mounted (changelog 0.5.0). Only say *what* is worth remembering.

```markdown
# Research assistant

You are a careful research assistant. Use internet search to find sources,
keep notes, and return concise answers with citations.
```

## When to use which

| Concept | Role | Loaded |
| - | - | - |
| Instructions | Always-on system prompt | Every run |
| Skills ([[skills]]) | Task procedures, progressive disclosure | When the agent selects them |
| Memory ([[memory]]) | Knowledge the agent can update | When a memory layer is declared and allowed |
| Tools / MCP / middleware | Application logic | Imported or declared |

## Gotchas

- `mda build` does not validate the definition call; a forbidden param (e.g. `backend=`) only fails when `mda dev` loads the graph (0.8.3 notes build-time catching of unsupported settings).
- Syntax errors in authored files are reported as `failed to parse <file>:<line>:<column>` since 0.5.0; before that they surfaced as "agent `name` is required".
- `name` must be a literal; computed names are rejected (static extraction).
- `mda init` scaffolds `model="openai:gpt-6-luna"` since 0.10.5 (changelog); the docs' examples still show `openai:gpt-6.1-sol`. Either works; set the model you pay for. `mda init --from` (0.10.5, changelog only) builds the project from an existing Fleet agent instead of the template ([[managed]]).
- `channels/channel.py` is a forbidden declaration name.
- `tools/mcp.py` is reserved; do not put a regular tool there.
- `.env` is loaded locally and non-reserved values are forwarded as deployment secrets; anything else next to `agent.py` ships in the upload (200 MB cap).

## Sources

- `../sources/docs/langsmith/python/managed-deep-agents-project-structure.md`
- `../sources/docs/langsmith/python/managed-deep-agents-agent-definition.md`
- `../sources/docs/langsmith/python/managed-deep-agents-instructions.md`
- `../sources/docs/langsmith/python/managed-deep-agents-migrate.md`
- `../sources/docs/langsmith/python/managed-deep-agents-subagents.md` (subagent `mcp`)
- `../sources/docs/langsmith/python/managed-deep-agents-browser-use.md` (`browser.py`)
- `../sources/docs/github/managed-deepagents-CHANGELOG.md`
- `../sources/package/deepagents/graph.py` (create_deep_agent parameters for comparison)

## See also

- [[index]]
- [[managed]]
- [[managed-capabilities]]
- [[managed-channels]]
- [[managed-dev]]
