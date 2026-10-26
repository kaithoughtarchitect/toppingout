---
title: Subagents (task tool, SubAgent, CompiledSubAgent)
id: subagents
type: api
status: code
product: sdk
keywords: subagent, sub-agent, sub agent, task tool, SubAgent, CompiledSubAgent, general-purpose subagent, context quarantine, delegate to specialist, fork mode, subagent_type, SubAgentMiddleware, parallel fan-out
read_when: Read when a subagent can't see parent middleware/memory, when adding a specialist agent, or when a task call is rejected.
updated: 2026-10-21
sources_hash: f48c95a22748
---

# Subagents (task tool, SubAgent, CompiledSubAgent)

One-line truth: synchronous subagents are child agents that the main agent calls through a single `task(description, subagent_type)` tool. The call blocks until the child finishes, and only the child's final text (or structured JSON) comes back as one `ToolMessage`. Use them for context quarantine, specialist prompts/tools/models, and parallel fan-out (several `task` calls in one turn).

## Quick reference

- `task(description, subagent_type)` blocks; only the child's final text (or structured JSON) returns as one `ToolMessage`.
- Unknown keys such as `prompt`, `name`, `task` are rejected; unknown `subagent_type` returns a string error.
- A `general-purpose` subagent is auto-added unless you pass one with that name or the profile disables it.
- Declarative `SubAgent`: `name`, `description` required; `system_prompt` is optional in code (default `""`), so always write one.
- Omitting `tools` inherits ALL the parent's custom tools; setting `tools=[...]` replaces them.
- Parent `middleware=` (TodoListMiddleware, RubricMiddleware) does NOT reach declarative children; children get no `task` tool.
- Children share the parent `backend`, so files are visible both ways; the child is stateless across calls.
- `CompiledSubAgent(name, description, runnable)` inherits nothing and its state must have `messages`.
- `mode="fork"` (beta, >=0.7.13) inherits parent history; `skills` on a fork raises `ValueError`.
- Subagent HITL interrupts need a checkpointer on the parent.

## Mental model

- `create_deep_agent(subagents=[...])` sorts the specs into three kinds:
  - dict with `graph_id` → `AsyncSubAgent`, which goes to `AsyncSubAgentMiddleware` ([[async-subagents]])
  - dict with `runnable` → `CompiledSubAgent`, used as-is
  - anything else → declarative `SubAgent`, compiled with `create_agent`
- `SubAgentMiddleware` exposes **one** `task` tool. The tool description lists every sync subagent as `- {name}: {description}`. That listing is the only way the model learns which subagents exist.
- A `general-purpose` subagent is auto-added (inserted first) unless you pass one with that name or the harness profile disables it.
- There is no `task` tool (and no `SubAgentMiddleware`) only when there are zero sync subagents: none passed **and** GP disabled.
- An isolated child receives `[HumanMessage(description)]` plus the parent's non-excluded state keys. It never sees the parent's messages.

## The `task` tool (exact schema)

```python
class TaskToolSchema(BaseModel):
    description: str      # full instructions + expected output format
    subagent_type: str    # must be a listed subagent name
```

- Unknown keys are **rejected** with a validation error: "Unexpected argument 'prompt'; put all instructions for the subagent in `description`." This stops models from hiding the real instructions under an invented key.
- An unknown `subagent_type` returns a string error that lists the allowed types. It does not raise.
- The tool has both a sync and an async implementation (`task` / `atask`). The child runs via `invoke`/`ainvoke` with config `{"configurable": {"ls_agent_type": "subagent"}}`. The parent's callbacks, tags, configurable and metadata propagate through LangGraph config merging.
- Result extraction (`_return_command_with_state_update`):
  1. If the child state has a non-None `structured_response`, it is JSON-serialized (`model_dump_json`, `dataclasses.asdict`, or `json.dumps`).
  2. Otherwise the content is the text of the **last `AIMessage` with non-empty text**. It walks backwards, which skips Anthropic's trailing empty `end_turn` messages.
  3. Other child state keys flow back as a `Command(update=...)`, **except** `messages`, `todos`, `structured_response`, `skills_metadata`, `pinned_skills`, `_skill_tools_disclosed`, `rubric`, the fork marker, and private (`PrivateStateAttr`) keys. Since 0.7.27, a key the child returns exactly as it received it is also dropped, so an untouched key without a reducer no longer conflicts across parallel `task` calls and an additive reducer doesn't add the inherited value twice.
  4. A key the children really change, in parallel `task` calls, still needs a reducer in your `state_schema`, or the step fails with `InvalidUpdateError`.
- A `CompiledSubAgent` whose output lacks a `messages` key raises `ValueError`.

## Declarative `SubAgent` (TypedDict, `from deepagents import SubAgent`)

| key | req | default when omitted (via `create_deep_agent`) |
| - | - | - |
| `name` | yes | must be unique across sync subagents (`ValueError` on a duplicate) |
| `description` | yes | shown in the `task` tool description |
| `system_prompt` | no | `""` plus profile overlays. **Does not inherit the parent's prompt** |
| `tools` | no | **inherits the parent's `tools=`**. If you set it, it replaces them entirely (`[]` means no custom tools) |
| `model` | no | the parent's model. Accepts a `"provider:model"` string or a `BaseChatModel` |
| `middleware` | no | merged into the default child stack by `.name` (see below) |
| `interrupt_on` | no | inherits the top-level `interrupt_on`. If set, it overrides |
| `skills` | no | none (unless the spec's own `middleware` holds a `SkillsMiddleware`). Only GP inherits the parent's `skills` |
| `permissions` | no | inherits the parent's `permissions`. If set, it **replaces** them |
| `response_format` | no | none. Accepts a Pydantic model, dataclass, TypedDict, JSON-schema dict, `ToolStrategy`, `ProviderStrategy` or `AutoStrategy` |
| `mode` | no | `"isolated"`. Can be `"fork"` (beta, >=0.7.13). `"handoff"` is accepted as a legacy alias for `"isolated"` |

The default child middleware stack (for `create_deep_agent`) is built in `graph.py`:
`FilesystemMiddleware(backend, permissions)` → `SummarizationMiddleware` → `PatchToolCallsMiddleware` → *spec `middleware` (new names)* → profile `extra_middleware` → `SkillsMiddleware` (only if the spec has `skills`) → prompt caching → `_ToolExclusionMiddleware` (if the profile excludes tools) → `HumanInTheLoopMiddleware` (if `interrupt_on`) → `UnsupportedContentMiddleware`. (0.7.29 moved Skills from right after Patch to just before caching.)
- Spec `middleware` entries whose `.name` matches a default **replace it in place**. For example, `FilesystemMiddleware(backend=..., tools=["read_file","ls"])` restricts the child's file tools. New entries land after the core entries and before the profile, Skills, caching and memory tail.
- The child **does not inherit** the parent's `middleware=`. That includes `TodoListMiddleware` ([[planning]]) and `RubricMiddleware`.
- The child gets **no** `SubAgentMiddleware`. An isolated declarative child therefore has no `task` tool and cannot delegate further.
- The child **does** share the parent's `backend`, so its files are visible to the parent ([[filesystem-tools]]). It is compiled with the parent's `state_schema` as well.

```python
from deepagents import create_deep_agent
from pydantic import BaseModel

class Findings(BaseModel):
    summary: str
    confidence: float

researcher = {
    "name": "researcher",
    "description": "In-depth web research needing many searches; returns findings.",
    "system_prompt": "Research thoroughly. Return <300 words. No raw tool output.",
    "tools": [internet_search],
    "model": "openai:gpt-5.5",
    "response_format": Findings,   # parent gets '{"summary": ..., "confidence": ...}'
}
agent = create_deep_agent(model="anthropic:claude-sonnet-5", subagents=[researcher])
```

## `CompiledSubAgent` (`from deepagents import CompiledSubAgent`)

```python
from langchain.agents import create_agent
from deepagents import CompiledSubAgent

analyzer = CompiledSubAgent(
    name="data-analyzer",
    description="Complex data analysis",
    runnable=create_agent("openai:gpt-5.5", tools=[...], system_prompt="..."),
    # mode="fork"  # optional: receive parent history; keeps its own prompt
)
```

- Fields: `name`, `description`, `runnable`, and optionally `mode`. The runnable's state **must** have `messages`.
- Used as-is. It does **not** inherit `tools`, `model`, `middleware`, `interrupt_on`, `permissions`, `skills` or `state_schema`, so configure HITL inside the graph yourself.
- It gets `run_name` / `lc_agent_name` metadata set to its `name`.
- To return structured output, set `response_format` on `create_agent`, or have a custom graph write `structured_response`.

## General-purpose subagent

- `name="general-purpose"`. The description says it has "access to all tools as the main agent". The prompt is `DEFAULT_SUBAGENT_PROMPT` plus profile overlays, and it tells the child that only its final message reaches the caller.
- It uses the parent's `model`, `tools`, `permissions`, `interrupt_on` and `skills` (the only child that inherits skills). It gets its own Filesystem, Summarization and PatchToolCalls middleware.
- From the parent's `middleware=`, it inherits only instances whose `.name` overrides a default GP slot.
- To **replace** it, pass a spec named `"general-purpose"`. Yours fully replaces the default, with no merge.
- To **rename or re-prompt** it, or **disable** it: `HarnessProfile(general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False | description=... | system_prompt=...))` registered via `register_harness_profile("provider:model", ...)` ([[customization]]).
- Listing `SubAgentMiddleware` in `excluded_middleware` raises `ValueError`, because it is required scaffolding. Disable GP instead.

## Forked subagents (`mode="fork"`, beta)

- The child receives the parent's **effective** history, meaning the summarization event is applied ([[summarization]]). The trailing AIMessage that holds the `task` call is dropped, and a `HumanMessage` is appended containing a continuation preamble plus the `description`.
- A declarative fork inherits the full parent state, including private keys, except `structured_response`, the summarization event/session id, `rubric`, `pinned_skills` and `_skill_tools_disclosed` (the rubric grades the parent's goal, pending pins and disclosed skill tools belong to the parent). It also mirrors the parent's system prompt and prompt-producing middleware (Skills with the parent's `skills`, Memory, and the parent `middleware=`), which is good for prompt-cache reuse.
- A fork inherits the parent's `tools=` unless it sets `tools`, which replaces them. Its spec `middleware` replaces inherited entries with the same `.name` and adds the rest. Middleware that rewrites the inherited system-prompt prefix or changes tool definitions shortens the shared cache prefix.
- A fork's own `system_prompt` is **appended** to the parent's, which breaks the cache. `skills` on a fork raises `ValueError`.
- The fork *does* carry a `task` tool (so tool lists match the parent's for caching), but any call returns the refusal "You are a subagent and cannot delegate to another subagent...".
- The `task` listing appends "(inherits your full conversation and system prompt — no need to restate context here)" to fork entries.
- A compiled fork gets the parent's messages but keeps its own prompt, and it gets only the non-private state.

## Context, state and tracing

- Runtime `context=` (with `context_schema`) propagates to every subagent's tools unchanged. For per-subagent settings, use namespaced fields.
- Every run carries `metadata["lc_agent_name"] = <subagent name>`, and the subagent tracing context sets `ls_agent_type="subagent"`. Inside a shared tool, branch on `runtime.config["metadata"]["lc_agent_name"]`.
- Streaming: `agent.stream_events(..., version="v3")` exposes `stream.subagents` handles (`.name`, `.messages`, `.tool_calls`, `.output`, `.status`) ([[streaming]]).
- `SubAgentMiddleware.subagent_names` (a frozenset) is public so streamers can discover the names.

## Using `SubAgentMiddleware` directly (without `create_deep_agent`)

```python
from deepagents.middleware import SubAgentMiddleware
SubAgentMiddleware(
    backend=backend,
    subagents=[{"name": "x", "description": "...", "system_prompt": "...",
                "model": "openai:gpt-5.5", "tools": []}],
    system_prompt=None,        # default: no prose injected (0.7)
    task_description=None,     # custom template; include {available_agents}
)
```

In this path each raw `SubAgent` **must** specify `model` and `tools` (`create_sub_agent` raises otherwise). No default child middleware is added apart from HITL (if `interrupt_on`) and `UnsupportedContentMiddleware`.

## Gotchas

- Docs call `system_prompt` "Required" for isolated subagents. In code it is optional and defaults to `""` (no instructions), so always write one.
- Omitting `tools` gives the child **all of the parent's custom tools**, not none. Set `tools=[...]` to scope it down.
- The docs' GP example shows `task(name="general-purpose", task="...")`. Those are **not** the real args, and they would be rejected. The real args are `description` and `subagent_type`.
- The docs' comparison table says forks "cannot use `task`". In code the tool is present but refuses at call time.
- The child's report is not shown to the user, so the parent must relay it. The child is stateless across calls: each `task` is a fresh run.
- Parent `middleware=` (for example `TodoListMiddleware`, `RubricMiddleware` or custom logging) does not reach declarative isolated children, GP excepted for slot overrides.
- The parent's `rubric` is not passed to children, so a child running its own `RubricMiddleware` is not graded against the parent's whole goal (fixed in 0.7.24/0.7.27).
- Custom `state_schema` fields are written back to the parent. If parallel `task` calls may change the same field, give it a reducer, or the step fails with `InvalidUpdateError`.
- Subagent HITL interrupts need a checkpointer on the **parent** ([[human-in-the-loop]]).
- Dynamic `response_format` per call (used by interpreter `task()` with `responseSchema`) works only on declarative specs. A compiled one raises `ValueError` ([[dynamic-subagents]]).

## Sources

- `../sources/docs/oss/python/deepagents/subagents.md`
- `../sources/docs/oss/python/deepagents/overview.md`
- `../sources/docs/oss/python/deepagents/profiles.md`
- `../sources/package/deepagents/middleware/subagents.py`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/profiles/harness/harness_profiles.py`
- `../sources/package/deepagents/__init__.py`

## See also

- [[index]]
- [[create-deep-agent]]
- [[middleware]]
- [[customization]]
- [[models]]
- [[tools]]
- [[context-engineering]]
- [[dynamic-subagents]]
- [[async-subagents]]
- [[human-in-the-loop]]
- [[permissions]]
- [[skills]]
- [[memory]]
- [[planning]]
- [[summarization]]
- [[filesystem-tools]]
- [[streaming]]
