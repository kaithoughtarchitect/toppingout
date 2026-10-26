---
title: The Deep Agents harness
id: harness
type: concept
status: code
product: all
keywords: deep agents harness, agent harness, create_agent, middleware stack, built-in tools, virtual filesystem, StateBackend, write_todos missing, planning removed, execute tool, install deepagents, pip install deepagents, task tool, prompt caching, LangGraph graph
read_when: Read when starting with Deep Agents, asking what is on or off by default, or wondering why write_todos or execute is missing.
updated: 2026-10-21
sources_hash: 6c04b706422f
---

# The Deep Agents harness

`deepagents` (PyPI, MIT, v0.7.29) is an opinionated "agent harness": LangChain's `create_agent` tool-calling loop plus a pre-assembled middleware stack (virtual filesystem, subagents, summarization, prompt caching, tool-call repair), compiled as a LangGraph graph. Reach for it when a task is long-horizon, multi-step, produces artifacts, or needs isolated delegation; drop to `create_agent` or raw LangGraph when you want less (see [[products]]).

## Quick reference

- `deepagents` 0.7.29 = `create_agent` loop + fixed middleware stack, compiled as a LangGraph `CompiledStateGraph`; entry point is `create_deep_agent(...)`.
- Python >=3.11; `pip install deepagents` (extras `[aws]`, `[quickjs]`, `[video]`); OpenAI etc. need their own integration package.
- On by default: file tools (`ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `delete`), `task` + `general-purpose` subagent, summarization, tool-call repair, prompt caching.
- Opt-in only: `write_todos` (add `TodoListMiddleware()`), skills (`skills=`), memory (`memory=`), HITL (`interrupt_on=`), async subagents, JS interpreter.
- `execute` exists only when the backend implements `SandboxBackendProtocol`; otherwise it is hidden from the model.
- Default backend is `StateBackend` (graph state, thread-scoped); files vanish after the run without a checkpointer.
- Authored system prompt is empty unless you pass `system_prompt=` or a harness profile adds text (since 0.7.0).
- Gotcha: README still says "can plan", but no `write_todos` since 0.7.0.
- Gotcha: `model=None` is deprecated (removal 1.0.0); use `provider:model`.

## Mental model

- **Same loop, more defaults.** Model calls tools until it stops. Everything "deep" is middleware wrapped around that loop ([[middleware]]).
- **One entry point:** `create_deep_agent(...)` returns a `CompiledStateGraph` (LangGraph). You `invoke` / `stream` / `ainvoke` it like any LangGraph graph ([[create-deep-agent]]).
- **The filesystem is the working memory.** Tools write large results to files instead of the context window; summarization offloads evicted history to `/conversation_history/...`; skills and memory are files. Where files live is decided by the *backend* ([[backends]]), default `StateBackend` (in graph state, thread-scoped).
- **Delegation isolates context.** The `task` tool spawns an ephemeral subagent with a fresh context that returns one final report ([[subagents]]).
- **Behaviour follows the model.** Harness profiles apply per-model prompt suffixes, tool-description overrides and extra middleware automatically ([[models]]).
- **"Trust the LLM" security model.** The agent can do anything its tools allow; enforce boundaries in tools / backends / sandboxes / [[permissions]], not in the prompt (README "Security").

## Built-in capabilities (0.7.29)

| Capability | On by default? | Provided by | Page |
| - | - | - | - |
| File tools `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep` | Yes | `FilesystemMiddleware` | [[filesystem-tools]] |
| `delete` (recursive) | Yes, if backend supports delete (hidden otherwise) | `FilesystemMiddleware` | [[filesystem-tools]] |
| `execute` (shell) | Only when backend implements `SandboxBackendProtocol`; filtered from the tool list otherwise | `FilesystemMiddleware` | [[sandboxes]] |
| Large tool-result / human-message eviction to files | Yes (20k / 50k tokens) | `FilesystemMiddleware` | [[context-engineering]] |
| `task` tool + auto `general-purpose` subagent | Yes | `SubAgentMiddleware` | [[subagents]] |
| Conversation summarization + history offload | Yes (model-aware thresholds) | `SummarizationMiddleware` (deepagents subclass) | [[summarization]] |
| Dangling tool-call repair | Yes | `PatchToolCallsMiddleware` | [[middleware]] |
| Prompt caching | Yes (Anthropic always; Bedrock / Fireworks if their packages are installed) | `append_prompt_caching_middleware` | [[middleware]] |
| Unsupported multimodal block scrubbing | Yes | `UnsupportedContentMiddleware` | [[middleware]] |
| Planning (`write_todos`) | **No** (opt-in since 0.7.0) | `TodoListMiddleware` from `langchain` | [[planning]] |
| Skills (catalog, `pinned_skills`, skill tools) | Only with `skills=` (or a `SkillsMiddleware` in `middleware=`) | `SkillsMiddleware` | [[skills]] |
| Memory (`AGENTS.md`) | Only with `memory=` | `MemoryMiddleware` | [[memory]] |
| Human-in-the-loop | Only with `interrupt_on=` or `mode="interrupt"` permissions | `HumanInTheLoopMiddleware` | [[human-in-the-loop]] |
| Async (remote) subagents | Only with `AsyncSubAgent` specs | `AsyncSubAgentMiddleware` | [[async-subagents]] |
| Reporting back to the parent when this agent runs as an async subagent | Always attached; acts only on runs started by `start_async_task`, async path only | `_ParentNotifierMiddleware` | [[async-subagents]] |
| Binary `read_file` results and inline media kept out of message history | **No** (`FilesystemMiddleware(offload_binary_content=True)` passed in `middleware=`) | `FilesystemMiddleware` | [[context-engineering]] |
| JS interpreter `eval` | Only if you pass `CodeInterpreterMiddleware` (`langchain_quickjs`, extra `deepagents[quickjs]`) | external | [[interpreters]] |

Docs group these into four pillars: **execution environment** (tools, virtual filesystem, permissions, code execution), **context management** (skills, memory, summarization/offloading, prompt caching), **delegation** (optional planning, subagents), **steering** (human-in-the-loop).

## Install

```bash
pip install deepagents          # or: uv add deepagents
pip install "deepagents[aws]"   # langchain-aws -> Bedrock prompt caching
pip install "deepagents[quickjs]"  # CodeInterpreterMiddleware
pip install "deepagents[video]" # video frame extraction in read_file
```

Python >=3.11. Hard deps include `langchain`, `langchain-core`, `langchain-anthropic`, `langchain-google-genai`, `langsmith`, `wcmatch` (see [[versions]]). Other providers need their integration package (e.g. `pip install -U "langchain[openai]"`). Set the provider key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, ...). Optional tracing: `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`.

## Minimal agent

```python
from deepagents import create_deep_agent

def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"

agent = create_deep_agent(
    model="openai:gpt-5.5",           # any tool-calling "provider:model" or BaseChatModel
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)
result = agent.invoke({"messages": [{"role": "user", "content": "what is the weather in sf"}]})
print(result["messages"][-1].content)
```

Provider-native server tools can be passed as dicts in `tools=` (quickstart): `{"type": "web_search"}` (OpenAI), `{"type": "web_search_20260209", "name": "web_search"}` (Anthropic), `{"google_search": {}}` (Google). MCP tools: see [[mcp]] / [[tools]].

## What the model sees by default

- **Authored system prompt is empty** unless you pass `system_prompt=` or the matched harness profile adds `base_system_prompt` / `system_prompt_suffix` (0.7.0 "lean prompts"). Tool guidance lives in tool schemas.
- Tool list: your `tools` + filesystem tools + `task` (+ `execute` / `delete` when supported).
- Graph config baked in via `.with_config`: `recursion_limit=9999`, metadata `ls_integration="deepagents"`, `lc_agent_name=name`.

## Related products

- **Deep Agents Code (`dcode`)**: pre-built terminal coding agent on this SDK ([[dcode]]).
- **Managed Deep Agents**: LangSmith-hosted runtime; owns backend/store/checkpointer ([[managed]]).
- JS/TS port: `deepagentsjs` (separate library; not covered here).
- Production path: LangSmith deployment / `langgraph build` ([[production]], [[persistence]]); streaming via `stream_events(version="v3")` with `stream.subagents` ([[streaming]]).

## Gotchas

- README / PyPI blurb still says "The agent can plan"; since 0.7.0 there is **no** `write_todos` unless you add `TodoListMiddleware()` (or use a model whose profile adds it, e.g. the built-in OpenAI Codex profiles).
- `execute` is removed from the model-visible tools when the backend is not a sandbox; if the model calls it anyway, it gets an error `ToolMessage`. The `create_deep_agent` docstring only mentions the error path.
- `FilesystemMiddleware` raises `NotImplementedError` if `permissions=` is combined with an execution-capable backend unless every permission path is scoped to a `CompositeBackend` route (execute cannot be permission-checked).
- Default `StateBackend` files live in graph state: without a checkpointer they vanish after the run; they are never shared across threads.
- Prompt caching is automatic only for Anthropic (and Bedrock/Fireworks when `langchain-aws` / `langchain-fireworks` are installed); other providers get no caching.
- `model=None` still works (defaults to `ChatAnthropic(model_name="claude-sonnet-4-6")`) but is deprecated since 0.5.3, removal in 1.0.0.

## Sources

- `../sources/docs/oss/python/deepagents/overview.md`
- `../sources/docs/oss/python/deepagents/quickstart.md`
- `../sources/docs/github/deepagents-README.md`
- `../sources/package/deepagents-0.7.29.dist-info/METADATA`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/middleware/filesystem.py`
- `../sources/package/deepagents/middleware/_prompt_caching.py`

## See also

- [[index]]
- [[create-deep-agent]]
- [[middleware]]
- [[customization]]
- [[models]]
- [[products]]
- [[versions]]
