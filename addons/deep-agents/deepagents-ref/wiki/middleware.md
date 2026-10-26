---
title: The middleware stack
id: middleware
type: reference
status: code
product: sdk
keywords: middleware stack, middleware order, AgentMiddleware, _ParentNotifierMiddleware, SkillsMiddleware placement, custom middleware, wrap_tool_call, wrap_model_call, before_agent, PatchToolCallsMiddleware, prompt caching, FilesystemMiddleware, SubAgentMiddleware, SummarizationMiddleware, excluded_middleware, remove middleware, UnsupportedContentMiddleware
read_when: Read when you need the exact middleware order, where custom middleware lands, how to replace or remove a built-in, or why a hook misbehaves across subagents.
updated: 2026-10-21
sources_hash: 39b20f6a9649
---

# The middleware stack

`create_deep_agent` is `create_agent` plus a fixed, ordered list of `AgentMiddleware`. Know the exact order (from `graph.py`, which beats the docs) to predict prompt-cache prefixes, where your middleware lands, and what you can replace or exclude.

## Quick reference

- Main stack order: Filesystem, SubAgent, ParentNotifier, Summarization, PatchToolCalls, AsyncSubAgent, then your middleware, profile extras, Skills (if `skills=`), prompt caching, Memory, HITL, UnsupportedContent.
- Skills moved from the head of the stack to the tail in 0.7.29. It now runs after your middleware, so your `before_agent`/`before_model` hooks don't see freshly loaded `skills_metadata` and your `wrap_model_call` can't edit the skills section of the prompt.
- `FilesystemMiddleware` and `SubAgentMiddleware` are protected; excluding them raises `ValueError`.
- Merge rule: same `.name` replaces in place; new names splice after the last core entry; `create_agent` rejects duplicate names.
- Remove middleware via `HarnessProfile(excluded_middleware=frozenset({...}))`, not `middleware=`; unmatched entries raise.
- `_ToolExclusionMiddleware` (from `excluded_tools`) is appended last so nothing can restore excluded tools.
- Declarative subagents have their own stack; auto `general-purpose` inherits your middleware only where `.name` matches a default slot.
- Raw `SubAgentMiddleware` specs need `model` and `tools` and get no filesystem/summarization.
- `TodoListMiddleware` is not in the stack since 0.7.0; add it for `write_todos`.
- Gotcha: mutating `self` in hooks races across subagents/threads; use state.
- Gotcha: where docs and `graph.py` disagree on order, code wins.

## Main agent stack, exact order (0.7.29)

Core (built first):

1. `FilesystemMiddleware(backend, custom_tool_descriptions=profile overrides, _permissions=permissions)` - always. Tools `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`, `execute`; filters `execute`/`delete` when unsupported; evicts tool results > 20k tokens and human messages > 50k tokens to files; enforces [[permissions]] ([[filesystem-tools]]). **Protected** (cannot be excluded).
2. `SubAgentMiddleware(backend, subagents=inline, task_description=profile["task"] override, state_schema)` - only if at least one sync subagent (the auto `general-purpose` counts). Adds `task`. **Protected**.
3. `_ParentNotifierMiddleware()` - always (since 0.7.27). Does nothing unless this run was started by another agent's `start_async_task`. Then, on the async path only (`aafter_agent`, `awrap_model_call`), it reports the run's final answer, or a failed model call, back to that parent once per run. Sync `invoke` passes straight through ([[async-subagents]]).
4. `SummarizationMiddleware` (deepagents subclass `_DeepAgentsSummarizationMiddleware`, `.name == "SummarizationMiddleware"`) via `create_summarization_middleware(model, backend)` - always. Model-aware thresholds, offloads history to `/conversation_history/{session_id}.md` ([[summarization]]).
5. `PatchToolCallsMiddleware()` - always. `before_agent`: inserts synthetic `ToolMessage`s for AI tool calls (incl. invalid ones) that never got a response (e.g. after an interrupt).
6. `AsyncSubAgentMiddleware(async_subagents=...)` - only with `AsyncSubAgent` specs ([[async-subagents]]).

*Your new middleware (names not already in the stack) is inserted here, after the last core entry.*

Tail:

7. Harness profile `extra_middleware` (materialized fresh per stack) ([[models]]).
8. `SkillsMiddleware(backend, sources=skills)` - only if `skills is not None` (or you passed a `SkillsMiddleware` in `middleware=`, see below). Injects the skill catalog into the system prompt, pins skills named in `pinned_skills`, and discloses skill tools ([[skills]]). It sits innermost before caching so it sees the summarized conversation and the model actually called, after any fallback or routing middleware you added. It is not a core entry, so your new middleware lands ahead of it.
9. `AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore")` - always (no-op for non-Anthropic).
10. `BedrockPromptCachingMiddleware(unsupported_model_behavior="ignore")` - only if `langchain_aws.middleware.prompt_caching` imports.
11. `FireworksPromptCachingMiddleware(unsupported_model_behavior="ignore")` - only if `langchain_fireworks.middleware.prompt_caching` imports.
12. `MemoryMiddleware(backend, sources=memory, add_cache_control=True)` - only if `memory is not None`. Placed after caching so memory edits don't invalidate the cached prefix ([[memory]]).
13. `HumanInTheLoopMiddleware(interrupt_on=merged)` - only if `interrupt_on` or any `mode="interrupt"` permission rule (user entries win per tool) ([[human-in-the-loop]]).
14. `UnsupportedContentMiddleware()` - always. Replaces image/audio/video/file blocks the model's `model.profile` rejects with a text notice, per request (thread keeps originals) ([[multimodal]]).

Post-processing:

- Profile `excluded_middleware` filter runs, then your `middleware=` is merged, then the filter runs again (so exclusions also remove your instances).
- `_ToolExclusionMiddleware(excluded=profile.excluded_tools)` is appended **last** if the profile excludes tools, so no later `wrap_model_call` can restore them; excluded tools are also non-executable.

Confirmed on 0.7.29 (2026-10-21) by capturing the list `create_deep_agent` passes to `create_agent`, with a scripted fake model, `skills`, `memory`, `interrupt_on`, one async subagent and one custom middleware: `FilesystemMiddleware, SubAgentMiddleware, _ParentNotifierMiddleware, SummarizationMiddleware, PatchToolCallsMiddleware, AsyncSubAgentMiddleware, <yours>, SkillsMiddleware, AnthropicPromptCachingMiddleware, MemoryMiddleware, HumanInTheLoopMiddleware, UnsupportedContentMiddleware`.

Passing a `SkillsMiddleware` in `middleware=` (its `.name` is `"SkillsMiddleware"`) replaces the default in place. If you passed no `skills=`, its `sources` become `skills`, so the default slot exists and the general-purpose subagent gets the same sources.

Bare stack (model only, no profile extras): Filesystem, SubAgent, ParentNotifier, Summarization, PatchToolCalls, AnthropicPromptCaching (+Bedrock/Fireworks if installed), UnsupportedContent.

## Subagent stacks

Declarative `SubAgent` (not forked), built in `graph.py`:
`FilesystemMiddleware(_permissions=spec perms or parent perms)` -> `SummarizationMiddleware` (subagent model) -> `PatchToolCallsMiddleware` -> *spec `middleware` (new names)* -> profile extras (subagent's model) -> `SkillsMiddleware` (only if the spec has `skills`, or a `SkillsMiddleware` in its own `middleware`) -> prompt caching -> `_ToolExclusionMiddleware`; then `HumanInTheLoopMiddleware` (if `interrupt_on`) and `UnsupportedContentMiddleware` are appended when the runnable is compiled (`subagents.py`).

Auto `general-purpose`: Filesystem -> Summarization -> Patch -> profile extras -> `SkillsMiddleware` (parent `skills`) -> caching, with the parent profile. It inherits your `middleware=` entries **only** where `.name` matches one of its default slots.

Forked subagent (`mode="fork"`): uses the parent's `skills` (a fork can't set its own), puts parent `MemoryMiddleware` after caching, and merges parent `middleware=` with spec middleware (spec wins by name); the merged list lands after Patch, ahead of profile extras and Skills. No `SubAgentMiddleware` and no `_ParentNotifierMiddleware` exist inside any subagent.

Since 0.7.29, skills sit in the same place on the main agent and in subagents: after your middleware and profile extras, right before caching. Before, the main agent ran skills first and subagents ran them right after Patch.

## Adding custom middleware

```python
from langchain.agents.middleware import AgentMiddleware, wrap_tool_call
from deepagents import create_deep_agent

@wrap_tool_call
def log_tool_calls(request, handler):
    print("tool:", request.tool_call["name"])
    return handler(request)

class CountTurns(AgentMiddleware):
    def before_agent(self, state, runtime):
        return {"x": state.get("x", 0) + 1}   # state, never self.x += 1

agent = create_deep_agent(model="openai:gpt-5.5", middleware=[log_tool_calls, CountTurns()])
```

Merge rule (`_apply_custom_middleware`): if `m.name` matches a name in the assembled stack it **replaces in place** (keeps position); otherwise it is spliced after the last core entry (before profile extras, Skills, caching, memory, HITL, UnsupportedContent). `create_agent` rejects two middleware with the same name.

Replace recipes (all need `deepagents>=0.7`):

```python
from deepagents.middleware import FilesystemMiddleware, SummarizationMiddleware, SkillsMiddleware
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain.agents.middleware import TodoListMiddleware

FilesystemMiddleware(backend=backend, tools=["read_file", "ls", "glob", "grep"])  # read-only
SummarizationMiddleware(model=model, backend=backend, trigger=("tokens", 100000), keep=("messages", 20))
AnthropicPromptCachingMiddleware(ttl="1h")
SkillsMiddleware(backend=backend, sources=["/skills/"], system_prompt=None)  # no catalog; also sets skills= if you passed none
TodoListMiddleware()   # not a replacement: adds write_todos (opt-in planning)
```

Other opt-ins: `create_summarization_tool_middleware(model, backend)` (agent-triggered `compact_conversation` tool), `RubricMiddleware` ([[rubric]]), `CodeInterpreterMiddleware` ([[interpreters]]), LangChain prebuilt middleware (retries, fallbacks, PII), provider middleware.

## Removing middleware

Use a harness profile, not `middleware=`:

```python
from deepagents import HarnessProfile, register_harness_profile
register_harness_profile("openai", HarnessProfile(excluded_middleware=frozenset({"SummarizationMiddleware"})))
```

Class entries match exact type; strings match `.name`. Excluding `FilesystemMiddleware` or `SubAgentMiddleware` raises `ValueError` at `HarnessProfile` construction; entries matching nothing across main + GP stacks raise at `create_deep_agent`. To drop `task`: `general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)` and no sync subagents. To hide tools only: `excluded_tools`.

## Building without create_deep_agent

```python
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from deepagents.middleware import (FilesystemMiddleware, SkillsMiddleware,
    SubAgentMiddleware, SummarizationMiddleware, UnsupportedContentMiddleware)

agent = create_agent(
    model="google_genai:gemini-3.6-flash",
    tools=[],
    middleware=[
        FilesystemMiddleware(backend=backend),
        TodoListMiddleware(),
        SubAgentMiddleware(backend=backend, subagents=[visualizer]),
        SummarizationMiddleware(model="google_genai:gemini-3.6-flash", backend=backend),
        SkillsMiddleware(backend=backend, sources=["/skills/"]),  # after summarization and any fallback, before caching
        UnsupportedContentMiddleware(),   # keep last
    ],
)
```

Raw `SubAgentMiddleware` specs must include `model` and `tools` (else `ValueError`) and get **no** filesystem/summarization middleware: only their own `middleware` + HITL + `UnsupportedContentMiddleware`.

## Gotchas

- Docs' full-stack list puts "your middleware" right after Patch and omits `_ParentNotifierMiddleware`, Fireworks caching and `UnsupportedContentMiddleware`. Code: user middleware goes after `AsyncSubAgentMiddleware` (the last core entry), and tool exclusion is the very last entry (the docs now agree on that one). Code wins.
- Middleware you pass runs **before** Skills now. If a custom hook needs this turn's `skills_metadata`, or must rewrite the skills prompt section, replace `SkillsMiddleware` by name instead of adding a separate middleware.
- One docs sentence says unmatched middleware lands "after `PatchToolCallsMiddleware`"; with async subagents it actually lands after `AsyncSubAgentMiddleware`.
- `TodoListMiddleware` is no longer in the stack (removed 0.7.0) ([[planning]]).
- A directly constructed `SummarizationMiddleware` has `trigger=None`, `keep=("messages", 20)`, `trim_tokens_to_summarize=4000`, no arg truncation; the default factory uses fraction thresholds (0.85/0.10) when the model profile exposes `max_input_tokens`, else 170k tokens / keep 6 messages.
- The from-scratch guide's `visualizer` subagent (raw `SubAgentMiddleware`, `"tools": []`) has no file or execute tools in code, despite the prose saying it writes and saves scripts.
- Mutating `self` in hooks races across subagents / parallel tools / threads; use state.
- `UnsupportedContentMiddleware` should stay last so it sees the final `request.model` (matters with runtime model swaps).

## Sources

- `../sources/docs/oss/python/deepagents/customization.md`
- `../sources/docs/oss/python/deepagents/overview.md`
- `../sources/docs/oss/python/langchain/deep-agent-from-scratch.md`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/middleware/__init__.py`
- `../sources/package/deepagents/middleware/_prompt_caching.py`
- `../sources/package/deepagents/middleware/patch_tool_calls.py`
- `../sources/package/deepagents/middleware/unsupported_content.py`
- `../sources/package/deepagents/middleware/summarization.py`
- `../sources/package/deepagents/middleware/subagents.py`
- `../sources/package/deepagents/middleware/filesystem.py`

## See also

- [[index]]
- [[harness]]
- [[create-deep-agent]]
- [[customization]]
- [[context-engineering]]
- [[subagents]]
