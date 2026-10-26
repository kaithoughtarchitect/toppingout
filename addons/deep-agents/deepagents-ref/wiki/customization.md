---
title: Customizing a deep agent
id: customization
type: how-to
status: code
product: sdk
keywords: customize agent, system prompt, prompt composition, custom middleware, override middleware, SummarizationMiddleware, SkillsMiddleware, structured output, response_format, subagents, backends, human in the loop, HITL, interrupt_on, going fully custom, tools, memory, skills
read_when: Read when deciding which create_deep_agent knob changes a behaviour, overriding a default middleware, or composing the system prompt.
updated: 2026-10-21
sources_hash: 6b4df49fa021
---

# Customizing a deep agent

Every knob on `create_deep_agent` and what it changes, in one place: model, prompt, tools, middleware, subagents, backends, HITL, skills, memory, profiles, structured output. Reach for this when shaping an agent; follow the links for depth.

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="You are a helpful assistant.",
    tools=[search, fetch_url],
    memory=["/AGENTS.md"],
    skills=["/skills/"],
)
```

| Param | Changes | Detail |
| - | - | - |
| `model=` | which LLM | [[models]] |
| `system_prompt=` | your instructions (front of prompt) | below |
| `tools=` | domain tools (additive) | [[tools]], [[mcp]] |
| `memory=` | `AGENTS.md` loaded every turn | [[memory]] |
| `skills=` | skill dirs, progressive disclosure | [[skills]] |
| `backend=` | where files live (`StateBackend` default) | [[backends]] |
| `permissions=` | path-level fs access control | [[permissions]] |
| `subagents=` | delegated workers behind `task` | [[subagents]] |
| `middleware=` | add or replace stack entries by `.name` | [[middleware]] |
| `interrupt_on=` | pause before tool calls | [[human-in-the-loop]] |
| `response_format=` | structured output | below |
| `state_schema=` / `context_schema=` | extra state / per-run context | [[context-engineering]] |
| harness profiles | per-model defaults bundle | [[models]] |

## Quick reference

- Each `create_deep_agent` param maps to one knob: `model`, `system_prompt`, `tools`, `memory`, `skills`, `backend`, `permissions`, `subagents`, `middleware`, `interrupt_on`, `response_format`.
- Prompt = your `system_prompt` -> profile BASE -> profile SUFFIX; no authored base prompt since 0.7.0 (`BASE_AGENT_PROMPT` deprecated).
- Middleware with the same `.name` as a built-in replaces it; keep counters in graph state, not on `self`.
- A replacement middleware is not merged with defaults; an overriding `SummarizationMiddleware(...)` loses model-aware defaults.
- Hide built-ins with profile `excluded_tools` or allowlist via `FilesystemMiddleware(tools=[...])` (`read_file` mandatory).
- Declarative subagents inherit parent `tools` only if the spec omits `"tools"`; they never inherit parent `middleware=`.
- Default `StateBackend`; `StoreBackend` needs `store=` and an explicit `namespace`; `FilesystemBackend` has `virtual_mode=True`.
- HITL: `interrupt_on={"tool": True}` and a `checkpointer` are required.
- Skills/memory files must exist in the backend before the run.
- Going fully custom means `create_agent` + `deepagents.middleware` pieces.

## System prompt composition (code: graph.py, harness_profiles.py)

Main agent: `USER` (your `system_prompt`) -> `BASE` (profile `base_system_prompt`) -> `SUFFIX` (profile `system_prompt_suffix`), joined by blank lines, empty parts skipped. Deep Agents authors **no** base prompt since 0.7.0 (to restore the old one: `from deepagents.graph import BASE_AGENT_PROMPT`, deprecated, removal 0.9.0).

| Stack | Final prompt |
| - | - |
| Main agent | `system_prompt` + profile BASE + profile SUFFIX |
| Declarative subagent | (profile `base_system_prompt` if set, **replacing** the spec's `system_prompt`, else spec's) + SUFFIX of the subagent's own model profile |
| Forked subagent (`mode="fork"`, experimental) | parent's final prompt + spec's `system_prompt` as addendum |
| Auto `general-purpose` | `general_purpose_subagent.system_prompt` -> else profile `base_system_prompt` -> else SDK GP default; then SUFFIX |

Middleware then appends dynamic sections at call time, in stack order: filesystem host-path routing notes (composite backends only), your own middleware's fragments, the skills catalog (`SkillsMiddleware`, after your middleware since 0.7.29), then memory content (`MemoryMiddleware`). `SystemMessage` input keeps content blocks (useful for `cache_control`); subagent dict specs take strings only.

## Tools

```python
agent = create_deep_agent(model="openai:gpt-5.5", tools=[internet_search])
```

- Plain functions (docstring = description), `@tool` `BaseTool`s, or provider tool dicts.
- MCP: `pip install "langchain[mcp]"`, then `from langchain.mcp import MCPAdapter`; `async with MCPAdapter({"mcpServers": {"s": {"url": "http://localhost:8000/mcp"}}}) as a: tools = await a.list_tools()` ([[mcp]]).
- Hide built-ins with profile `excluded_tools`, or allowlist via `FilesystemMiddleware(backend=..., tools=["read_file", "ls", "glob", "grep"])` in `middleware=` (`read_file` mandatory, else `ValueError`).

## Middleware

Any LangChain `AgentMiddleware` (decorators `@wrap_tool_call`, `@wrap_model_call`, `before_agent`, etc.). Same `.name` as a built-in replaces it; new names insert after the core stack. Keep per-thread counters in graph state, not on `self` (subagents, parallel tools, and concurrent threads share the instance). Full ordering and override recipes: [[middleware]].

Common overrides (replace in place):

```python
from deepagents.backends import StateBackend
from deepagents.middleware import SummarizationMiddleware
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware

backend = StateBackend()
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    backend=backend,
    middleware=[
        SummarizationMiddleware(model="anthropic:claude-sonnet-4-6", backend=backend,
                                trigger=("tokens", 100000), keep=("messages", 20)),
        AnthropicPromptCachingMiddleware(ttl="1h"),   # default is 5m
    ],
)
```

Interpreter: `from langchain_quickjs import CodeInterpreterMiddleware`; `middleware=[CodeInterpreterMiddleware()]` adds an `eval` JS tool ([[interpreters]]).

## Subagents

```python
research_subagent = {
    "name": "research-agent",
    "description": "Used to research more in depth questions",
    "system_prompt": "You are a great researcher",
    "tools": [internet_search],
    "model": "openai:gpt-5.5",   # optional, defaults to parent model
}
agent = create_deep_agent(model="google_genai:gemini-3.6-flash", subagents=[research_subagent])
```

Declarative spec keys also accept `middleware`, `interrupt_on`, `skills`, `permissions`, `response_format`. Tools: inherit parent `tools` only if the spec omits `"tools"`. Details: [[subagents]].

## Backends

| Backend | Import | Notes |
| - | - | - |
| `StateBackend()` | `deepagents.backends` | default; thread-scoped, in graph state; seed via `invoke({"files": {...}})` |
| `FilesystemBackend(root_dir=".", virtual_mode=True)` | `deepagents.backends` | real disk; `virtual_mode=True` default since 0.7.0 |
| `LocalShellBackend(root_dir=".", virtual_mode=True, env={...})` | `deepagents.backends` | disk + unrestricted host shell (`execute`) |
| `StoreBackend(namespace=lambda rt: (...,))` | `deepagents.backends` | cross-thread; needs `store=`; namespace required |
| `ContextHubBackend("my-agent")` | `deepagents.backends` | LangSmith Hub repo |
| `CompositeBackend(default=..., routes={"/memories/": ...})` | `deepagents.backends` | path routing |
| `LangSmithSandbox(sandbox=...)` and partner sandboxes (`langchain_daytona.DaytonaSandbox`, `langchain_e2b.E2BSandbox`, `langchain_modal.ModalSandbox`, `langchain_runloop.RunloopSandbox`, `langchain_vercel_sandbox.VercelSandbox`) | various | add `execute` |

Skills and memory files must exist in the backend before the run. See [[backends]], [[sandboxes]].

## Human-in-the-loop

```python
from langgraph.checkpoint.memory import MemorySaver
agent = create_deep_agent(
    model="openai:gpt-5.5",
    tools=[remove_file, fetch_file, notify_email],
    interrupt_on={
        "remove_file": True,                                        # approve/edit/reject/respond
        "fetch_file": False,
        "notify_email": {"allowed_decisions": ["approve", "reject"]},
    },
    checkpointer=MemorySaver(),   # required
)
```

See [[human-in-the-loop]].

## Skills and memory

- `skills=["/skills/"]`: each skill is a dir with `SKILL.md` frontmatter; only metadata enters the prompt until needed ([[skills]]). Override `SkillsMiddleware(backend=..., sources=[...], system_prompt=TEMPLATE)` where the template must contain `{skills_locations}`, `{skills_list}`, `{skills_load_warnings}`; `system_prompt=None` suppresses the catalog. Your instance replaces the default by name; `skills=` is optional then, since its `sources` become `skills` (0.7.29). Pass it this way to give skills their own tools (`SkillsMiddleware(..., tools=[...])`) ([[skills]]).
- Pin a skill the user named for this turn: `invoke({"messages": [...], "pinned_skills": ["name"]})` ([[skills]]).
- `memory=["/AGENTS.md"]`: always loaded; agent can update it ([[memory]]).

## Structured output

```python
from pydantic import BaseModel
class WeatherReport(BaseModel):
    location: str
    temperature: float

agent = create_deep_agent(model="openai:gpt-5.5", response_format=WeatherReport, tools=[internet_search])
result = agent.invoke({"messages": [{"role": "user", "content": "Weather in SF?"}]})
result["structured_response"]   # WeatherReport instance
```

## Profiles

Per-model bundle applied automatically: `register_harness_profile("openai:gpt-5.5", HarnessProfile(system_prompt_suffix="..."))`. Use a profile when behaviour should follow the model; use call-site args for global behaviour (there is no wildcard profile key). See [[models]].

## Going fully custom

Compose `langchain.agents.create_agent` with `deepagents.middleware` pieces yourself (`FilesystemMiddleware`, `SummarizationMiddleware`, `SkillsMiddleware`, `SubAgentMiddleware`, `TodoListMiddleware`); see [[middleware]].

## Gotchas

- A replacement middleware is **not merged** with the default: an overriding `FilesystemMiddleware` does not inherit `backend=`/`permissions=` from `create_deep_agent`. Docs say pass permissions to it, but the public constructor has only a private `_permissions` kwarg.
- An overriding `SummarizationMiddleware(...)` constructed directly loses the model-aware defaults (`trigger=None`, `keep=("messages", 20)`, `trim_tokens_to_summarize=4000`, arg truncation off) unless you set them ([[summarization]]). Its new `summarizer=` (0.7.26) writes summaries with another model while `model` still sets thresholds and token counting.
- Custom middleware now runs before `SkillsMiddleware` (0.7.29), so it can't see this turn's freshly loaded `skills_metadata` or edit the skills prompt section. Replace `SkillsMiddleware` by name if you need to.
- Overrides propagate to the auto GP subagent only for middleware whose name matches a GP default slot; declarative subagents never inherit parent `middleware=` (except forks). Put overrides in the spec's `middleware`.
- Some customization-page examples pass `model_provider=` / `temperature=` to `create_deep_agent`; those params do not exist ([[create-deep-agent]]).
- `StoreBackend` example in the Memory tab both `store.put(...)` and seeds `files` in the input; the `files` seed is ignored for non-state backends.
- HITL and multi-turn `StateBackend` require a `checkpointer`; on LangSmith Deployment omit `checkpointer`/`store` (platform provides them) ([[persistence]]).

## Sources

- `../sources/docs/oss/python/deepagents/customization.md`
- `../sources/docs/oss/python/deepagents/profiles.md`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/profiles/harness/harness_profiles.py`
- `../sources/package/deepagents/middleware/summarization.py`
- `../sources/package/deepagents/middleware/filesystem.py`
- `../sources/package/deepagents/backends/__init__.py`

## See also

- [[index]]
- [[harness]]
- [[create-deep-agent]]
- [[middleware]]
- [[models]]
- [[context-engineering]]
