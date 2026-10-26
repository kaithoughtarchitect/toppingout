---
title: create_deep_agent
id: create-deep-agent
type: api
status: code
product: sdk
keywords: create_deep_agent, create deep agent, signature, parameters, kwargs, system_prompt, interrupt_on, response_format, structured output, state_schema, context_schema, checkpointer, store, backend, subagents, recursion_limit
read_when: Read when you need the exact create_deep_agent signature, a parameter default, or the middleware/prompt assembly order.
updated: 2026-10-21
sources_hash: a170c2cc95ed
---

# create_deep_agent

`deepagents.create_deep_agent` (defined in `deepagents/graph.py`) builds the harness: resolves the model, resolves the harness profile, assembles the middleware stack and subagents, and returns a compiled LangGraph graph from `langchain.agents.create_agent`. It is the only constructor you need for self-hosted Deep Agents ([[harness]]).

## Quick reference

- Signature: `create_deep_agent(model=None, tools=None, *, system_prompt, middleware, subagents, skills, memory, permissions, backend, interrupt_on, response_format, state_schema, context_schema, checkpointer, store, debug, name, cache)`; only `model` and `tools` are positional.
- Returns a `CompiledStateGraph` with `recursion_limit=9999` preset; override at invoke time via `config=`.
- `tools=` is additive; it never removes built-ins (hide via profile `excluded_tools`).
- Final prompt = `system_prompt` + profile BASE + profile SUFFIX; empty if none given.
- `middleware=` merges by `.name`: same name replaces in place, new names go after the last core entry.
- `interrupt_on` and multi-turn `StateBackend` need a `checkpointer`; `StoreBackend` needs `store=`.
- `response_format` result lands in `result["structured_response"]`.
- `state_schema` must subclass `DeepAgentState`; `context_schema` values pass via `invoke(..., context=...)`.
- Gotcha: `model_provider=` / `temperature=` are not params; build the model with `init_chat_model`.
- Gotcha: seeding `files` in input works only with `StateBackend`.

## Signature (0.7.29, verified in graph.py)

```python
from deepagents import create_deep_agent

create_deep_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware[StateT_co, ContextT]] = (),
    subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    permissions: list[FilesystemPermission] | None = None,
    backend: BackendProtocol | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    response_format: ResponseFormat[ResponseT] | type[ResponseT] | dict[str, Any] | None = None,
    state_schema: type[DeepAgentState] | None = None,
    context_schema: type[ContextT] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
) -> CompiledStateGraph[AgentState[ResponseT], ContextT, InputAgentState, OutputAgentState[ResponseT]]
```

Only `model` and `tools` are positional; everything else is keyword-only.

## Parameters

| Param | Default | Behaviour |
| - | - | - |
| `model` | `None` (deprecated) | `"provider:model"` string resolved via `init_chat_model` + provider profile, or a `BaseChatModel`. `None` warns and uses `ChatAnthropic(model_name="claude-sonnet-4-6")`; removed in 1.0.0. See [[models]]. |
| `tools` | `None` | Additive to built-ins (fs tools, `execute`, `task`). Never removes a built-in. Accepts `BaseTool`, plain callables, or provider tool dicts. Profile `tool_description_overrides` are applied to `BaseTool`/dict tools (not plain callables). See [[tools]]. |
| `system_prompt` | `None` | `USER` slot, placed first. Final = `USER` + `"\n\n"` + profile `BASE` + `"\n\n"` + profile `SUFFIX` (empty parts skipped). `None` and no profile -> empty system prompt. A `SystemMessage` keeps its content blocks (e.g. `cache_control`); profile text is appended as an extra text block. |
| `middleware` | `()` | Merged by `.name`: same name as a stack entry -> replaced in place; otherwise inserted after the last core entry (before profile extras / Skills / caching / memory / HITL). A `SkillsMiddleware` passed here with no `skills=` also supplies `skills` (its `sources`). See [[middleware]]. |
| `subagents` | `None` | `SubAgent` dicts (declarative), `CompiledSubAgent` (pre-built runnable), `AsyncSubAgent` (has `graph_id`). A `general-purpose` subagent is auto-added unless you pass one with that name or the profile disables it. See [[subagents]], [[async-subagents]]. |
| `skills` | `None` | POSIX paths relative to the backend root, e.g. `["/skills/"]`; later sources win on name clashes. Adds `SkillsMiddleware` near the end of the stack, after your middleware and profile extras, right before prompt caching (moved there in 0.7.29). See [[skills]]. |
| `memory` | `None` | `AGENTS.md` paths, e.g. `["/memory/AGENTS.md"]`; loaded at startup into the system prompt. Adds `MemoryMiddleware` (after caching). See [[memory]]. |
| `permissions` | `None` | `FilesystemPermission` rules, first match wins, no match = allow; modes `"allow"`/`"deny"`/`"interrupt"`. Enforced at tool level by `FilesystemMiddleware`, not by backends. Subagents inherit unless they set their own (which replaces). See [[permissions]]. |
| `backend` | `None` -> `StateBackend()` | Where files live; sandbox backends add `execute`. See [[backends]]. |
| `interrupt_on` | `None` | `{tool_name: True or False or InterruptOnConfig}`; adds `HumanInTheLoopMiddleware`. Declarative subagents inherit unless they set their own; `CompiledSubAgent` and `AsyncSubAgent` never inherit. Needs a checkpointer. See [[human-in-the-loop]]. |
| `response_format` | `None` | Structured output; result in `result["structured_response"]`. |
| `state_schema` | `None` -> `DeepAgentState` | Must subclass `deepagents.DeepAgentState` (keeps the `DeltaChannel` messages reducer; not validated at runtime). Forwarded to declarative subagents, not to compiled/async ones. |
| `context_schema` | `None` | Immutable per-run context type; pass values with `invoke(..., context=...)`. See [[context-engineering]]. |
| `checkpointer` | `None` | Passed to `create_agent`. Required for HITL, multi-turn threads, and `StateBackend` persistence across turns. See [[persistence]]. |
| `store` | `None` | Passed to `create_agent`; required by `StoreBackend` (omit on LangSmith Deployment, which provisions one). |
| `debug` | `False` | Passed through. |
| `name` | `None` | Passed through; also written to metadata `lc_agent_name`. |
| `cache` | `None` | LangGraph node cache, passed through. |

Raises `ImportError` (missing/old provider package, e.g. `langchain-openrouter<0.2.0`) and `ValueError` (bad profile `excluded_middleware`: protected class, private name, ambiguous, or unmatched).

## Return value

A `CompiledStateGraph` already wrapped with `.with_config({"recursion_limit": 9_999, "metadata": {"ls_integration": "deepagents", "lc_versions": {"deepagents": "0.7.29"}, "lc_agent_name": name}})`. State schema defaults to `DeepAgentState` (messages use `DeltaChannel` with `snapshot_frequency=50`, making checkpoint growth O(N)). With the default `StateBackend`, state also carries a `files` channel.

## Invoke / stream basics

```python
from langgraph.checkpoint.memory import MemorySaver
from deepagents import create_deep_agent
from deepagents.backends.utils import create_file_data

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    skills=["/skills/"],
    checkpointer=MemorySaver(),
)
config = {"configurable": {"thread_id": "t-1"}}

result = agent.invoke(
    {
        "messages": [{"role": "user", "content": "What is langgraph?"}],
        # seed the default StateBackend's in-state filesystem (paths start with "/")
        "files": {"/skills/langgraph-docs/SKILL.md": create_file_data(skill_md)},
    },
    config=config,
)
print(result["messages"][-1].content)

# async
result = await agent.ainvoke({"messages": [{"role": "user", "content": "next"}]}, config=config)

# typed event streaming (v3), incl. per-subagent handles
stream = agent.stream_events({"messages": [...]}, version="v3", config=config)
for msg in stream.messages:
    print(msg.text)
```

`"messages"` may also be a bare string (`{"messages": "Research X"}`). Streaming details: [[streaming]].

## Assembly order inside the function

1. Resolve model (`resolve_model`) and harness profile (`_harness_profile_for_model`); validate profile exclusions.
2. Rewrite tool descriptions per profile; default backend to `StateBackend()`.
3. Build final system prompt (USER, BASE, SUFFIX).
4. If `skills` is `None`, take it from a `SkillsMiddleware` passed in `middleware=`. Split `subagents` into async (has `"graph_id"`) vs inline; build each declarative subagent's own stack.
5. Auto-add `general-purpose` subagent (index 0) unless disabled or overridden.
6. Build main stack (core, then profile extras, Skills, caching, Memory, HITL, UnsupportedContent), merge `middleware`, apply profile exclusions, append tool-exclusion middleware.
7. Call `create_agent(...)` and `.with_config(...)`.

Full stack order: [[middleware]].

## Gotchas

- Passing kwargs such as `model_provider=`, `temperature=` to `create_deep_agent` (shown in some customization-page tabs for Bedrock / HuggingFace) is invalid; the function has no such params. Build the model with `init_chat_model(...)` and pass the instance.
- `tools=` cannot hide built-ins. Hide with a harness profile `excluded_tools`, or restrict via `FilesystemMiddleware(tools=[...])` passed in `middleware=`.
- Planning is not included; add `TodoListMiddleware()` yourself ([[planning]]).
- `recursion_limit` is preset to 9999; overriding requires passing `config={"recursion_limit": ...}` at invoke time.
- `state_schema` that is not a `DeepAgentState` subclass is not rejected at runtime but loses the O(N) messages channel.
- Seeding `files` in the input only works with `StateBackend`; other backends need `backend.upload_files([...])` or `store.put(...)`.

## Sources

- `../sources/docs/oss/python/deepagents/customization.md`
- `../sources/docs/oss/python/deepagents/quickstart.md`
- `../sources/docs/oss/python/reference/deepagents-python.md`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/_models.py`

## See also

- [[index]]
- [[harness]]
- [[middleware]]
- [[customization]]
- [[models]]
