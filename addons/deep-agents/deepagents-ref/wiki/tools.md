---
title: Tools (custom tools, ToolRuntime, built-ins)
id: tools
type: api
status: code
product: sdk
keywords: custom tools, add tool, tools=, @tool, ToolRuntime, runtime.context, runtime.store, runtime.state, tool_call_id, Command update, large tool results, tool eviction, built-in tools, excluded_tools, get_stream_writer, tool returns image
read_when: Read when adding a custom tool, a tool needs context/store/state via ToolRuntime, a tool returns Command or media, or a built-in tool is missing.
updated: 2026-10-21
sources_hash: 29d930e0cd46
---

# Tools (custom tools, ToolRuntime, built-ins)

One-line truth: `create_deep_agent(tools=[...])` accepts plain callables, LangChain `BaseTool`s (`@tool`), and tool dicts; they are **added on top of** the harness tools (filesystem, `execute`, `task`), never replacing them. Reach for this page whenever you give a Deep Agent a new capability.

## Quick reference

- `tools=` takes callables, `@tool` `BaseTool`s, or dicts; they are additive and never replace built-ins (`ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `delete`, `execute`, `task`).
- The docstring is the tool description; schema comes from type hints.
- Add a `runtime: ToolRuntime` param to get `.context`, `.store`, `.state`, `.tool_call_id`, `.config`; it is hidden from the model schema.
- Return `str`, a list of content blocks (multimodal), a `ToolMessage`, or `Command(update={...})` with a `ToolMessage` using `runtime.tool_call_id`.
- Custom state keys need `state_schema=` (subclass `DeepAgentState`) or a middleware `state_schema`.
- Declarative subagents inherit parent `tools` only if the spec omits `"tools"`; `CompiledSubAgent` gets none injected.
- Tool results over ~20k tokens are offloaded to `/large_tool_results/<tool_call_id>`; tune with `FilesystemMiddleware(tool_token_limit_before_evict=...)`.
- Gotcha: profile `tool_description_overrides` skip plain callables; wrap with `@tool`.
- Gotcha: `permissions=` covers only built-in fs tools; use `interrupt_on` for custom tools.
- Gotcha: `write_todos` is absent unless you add `TodoListMiddleware()`.

## Signature (0.7.29)

```python
create_deep_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *, ..., context_schema=None, state_schema=None, ...
)
```

- `tools` is positional-or-keyword (2nd arg); everything after is keyword-only. See [[create-deep-agent]].
- `tools` is forwarded to LangChain `create_agent(model, tools=...)`. Schema is inferred from type hints + docstring (docstring is the description the model reads).
- Passing tools is **additive**. To hide a built-in from the model use a `HarnessProfile(excluded_tools=...)`; to remove file tools entirely pass your own `FilesystemMiddleware(tools=[...])` in `middleware=` (same `.name` replaces the default in place). See [[harness]], [[middleware]].

## Custom tools

```python
from typing import Literal
from langchain.tools import tool
from deepagents import create_deep_agent

def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
) -> dict:
    """Run a web search"""          # becomes the tool description
    return tavily_client.search(query, max_results=max_results, topic=topic)

@tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"Sunny in {city}"

agent = create_deep_agent(model="anthropic:claude-sonnet-4-6", tools=[internet_search, get_weather])
```

Tool dicts (`{"name": ..., "description": ..., ...}`) are also accepted. Full LangChain tool details (StructuredTool, error handling) live in LangChain docs, not here.

## ToolRuntime: context, store, state, tool_call_id

Declare a parameter annotated `ToolRuntime` (import from `langchain.tools`); it is injected and hidden from the model's schema.

```python
from dataclasses import dataclass
from langchain.tools import ToolRuntime, tool
from deepagents import create_deep_agent

@dataclass
class Context:
    user_id: str
    api_key: str

@tool
def fetch_user_data(query: str, runtime: ToolRuntime[Context]) -> str:
    """Fetch data for the current user."""
    return f"Data for {runtime.context.user_id}: {query}"

agent = create_deep_agent(model="openai:gpt-5.5", tools=[fetch_user_data], context_schema=Context)
agent.invoke({"messages": [{"role": "user", "content": "recent activity"}]},
             context=Context(user_id="u-123", api_key="sk-..."))
```

Fields used by the package's own tools / docs:

| Attribute | What |
| - | - |
| `runtime.context` | run-scoped immutable context (`context_schema`); propagates to all subagents automatically |
| `runtime.store` | LangGraph `BaseStore` passed as `store=` |
| `runtime.state` | current graph state dict (`messages`, `files` with StateBackend, custom keys) |
| `runtime.tool_call_id` | id to put on a returned `ToolMessage` / `Command` |
| `runtime.config` | RunnableConfig (e.g. `configurable.thread_id`) |
| `runtime.server_info.user.identity` | authenticated user on a LangSmith Agent Server deployment (docs only) |

`ToolRuntime[ContextT, StateT]` is generic; built-ins use `ToolRuntime[None, FilesystemState]`. Tools that only need context/store do **not** need middleware; add middleware only when a tool must also change the system prompt or tool list per call. See [[context-engineering]], [[customization]].

## Return shapes

| Return | Effect |
| - | - |
| `str` | text `ToolMessage` |
| `list[dict]` of standard content blocks | multimodal `ToolMessage` (text/image/audio/video/file) — see [[multimodal]] |
| `ToolMessage(content=..., tool_call_id=runtime.tool_call_id, status="error")` | explicit error result |
| `Command(update={...,"messages":[ToolMessage(..., tool_call_id=runtime.tool_call_id)]})` | write state + result in one step (pattern used by `task`, `read_file` video path) |

```python
from langchain.messages import ToolMessage
from langgraph.types import Command

@tool
def set_page(url: str, runtime: ToolRuntime) -> Command:
    """Record the page URL in state."""
    return Command(update={
        "page_url": url,
        "messages": [ToolMessage(f"page set to {url}", tool_call_id=runtime.tool_call_id)],
    })
```

Custom state keys (`page_url`) must exist in the graph schema: pass `state_schema=` a subclass of `deepagents.DeepAgentState`, or ship the key via a middleware's `state_schema` (preferred). Declarative subagents receive the same `state_schema`.

## Built-in harness tools

| Tool | Source | Present when |
| - | - | - |
| `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep` | `FilesystemMiddleware` | always (see [[filesystem-tools]]) |
| `delete` | `FilesystemMiddleware` | backend supports delete (filtered per call); needs `deepagents>=0.7` |
| `execute` | `FilesystemMiddleware` | backend implements `SandboxBackendProtocol` (for `CompositeBackend`: its default backend). Otherwise hidden from the model at call time — see [[sandboxes]] |
| `task` | `SubAgentMiddleware` | any sync subagent exists (the auto `general-purpose` one counts) — see [[subagents]] |
| async-subagent tools | `AsyncSubAgentMiddleware` | `subagents=` contains specs with `graph_id` — see [[async-subagents]] |
| skill tools | `SkillsMiddleware(tools=[...] or resolver)` | only after the model reads (or you pin) a skill that lists them in `metadata.include_tools`; calls fail as unknown tools before that (`deepagents>=0.7.22`). See [[skills]] |
| `write_todos` | LangChain `TodoListMiddleware` | **only if you add it** (`middleware=[TodoListMiddleware()]`) — see [[planning]] |

`FsToolName = Literal["ls","read_file","write_file","edit_file","delete","glob","grep","execute"]` (exported from `deepagents`).

## How your tools reach subagents

- Declarative `SubAgent` without a `"tools"` key **inherits the parent's `tools`**; with `"tools": [...]` (even `[]`) it gets only those. Built-in file tools are always added by the subagent's own `FilesystemMiddleware`. Forks follow the same rule.
- To show a tool only when a skill needs it, pass it to `SkillsMiddleware(tools=...)`, not to `tools=`. A tool in `tools=` is always visible, unless it is deferred (`extras={"defer_loading": True}`), in which case reading the skill reveals it ([[skills]]).
- The auto `general-purpose` subagent gets the main agent's custom tools.
- `CompiledSubAgent` runnables get nothing injected.

## Large tool results

`FilesystemMiddleware.wrap_tool_call` offloads any custom tool result whose text exceeds `tool_token_limit_before_evict * 4` chars (default `20000` tokens → 80,000 chars) to `/large_tool_results/<tool_call_id>` on the backend (under `artifacts_root` for `CompositeBackend`) and gives the model a pointer to page it back with `read_file`. Built-in fs tools (`ls, glob, grep, read_file, edit_file, write_file, delete`) are excluded. Configure via a replacement `FilesystemMiddleware(tool_token_limit_before_evict=...)`; `None` disables. See [[context-engineering]].

## Gotchas

- `write_todos` is not a default tool in 0.7.x even though older docs/tutorials assume it.
- Harness-profile `tool_description_overrides` rewrite only `BaseTool` and dict tools; **plain callables are left unchanged** (`_tools.py`). Wrap with `@tool` if you need profile overrides.
- `create_deep_agent`'s docstring says `execute` "will return an error message" on non-sandbox backends; in practice `FilesystemMiddleware` also strips it from the tool list per model call, so the model normally never sees it. The error path only fires if it is called anyway.
- Two `write_file`/`edit_file`/`delete` calls on the same path in one model turn: the later ones get `Error: parallel file mutations to the same path are not allowed.`
- Tool exceptions propagate through `FilesystemMiddleware.wrap_tool_call` unhandled; error-to-message conversion is LangChain's tool node behavior, not deepagents'.
- Tool names collide with built-ins at your own risk; `HarnessProfile.excluded_tools` filters **all** tools by name, including yours, and runs last so custom middleware cannot restore them.
- For interrupts before a tool runs use `interrupt_on={"my_tool": True}` — see [[human-in-the-loop]]; `permissions=` only governs built-in fs tools, not custom tools ([[permissions]]).
- Emit progress from inside a tool with `langgraph.config.get_stream_writer()`; consume with `stream_mode="custom"` — see [[streaming]].
- MCP tools are just tools: load them and pass the list — see [[mcp]].

## Sources
- `../sources/docs/oss/python/deepagents/tools.md`
- `../sources/docs/oss/python/deepagents/context-engineering.md` (runtime context / ToolRuntime section)
- `../sources/docs/oss/python/deepagents/subagents.md` (context propagation section)
- `../sources/docs/oss/python/deepagents/memory.md` (ToolRuntime.server_info example)
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/_tools.py`
- `../sources/package/deepagents/middleware/filesystem.py`
- `../sources/package/deepagents/middleware/subagents.py`
- `../sources/package/deepagents/middleware/__init__.py`

## See also
- [[index]]
- [[create-deep-agent]]
- [[filesystem-tools]]
- [[planning]]
- [[subagents]]
- [[async-subagents]]
- [[mcp]]
- [[multimodal]]
- [[middleware]]
- [[harness]]
- [[backends]]
- [[sandboxes]]
- [[streaming]]
- [[context-engineering]]
- [[customization]]
- [[human-in-the-loop]]
- [[permissions]]
