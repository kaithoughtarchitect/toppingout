---
title: Context engineering in Deep Agents
id: context-engineering
type: concept
status: code
product: all
keywords: context engineering, context window, context management, system prompt assembly, context_schema, runtime context, prompt layers, token limits, compression, offloading, context overflow, five layers, custom state, input context
read_when: Read when deciding what goes in the prompt vs files vs state, passing per-run context, debugging how the system prompt is assembled, or context bloat.
updated: 2026-10-21
sources_hash: d59500c93853
---

# Context engineering in Deep Agents

One-line truth: every `create_deep_agent` graph already manages five context layers (prompt inputs, runtime context, compression, subagent isolation, long-term files); your job is choosing what goes in each layer, not re-implementing compression.

## The five layers

| Layer | You control | Lifetime |
| - | - | - |
| Input context | `system_prompt`, `memory=`, `skills=`, tool descriptions | rebuilt every model call |
| Runtime context | `context_schema` + `invoke(..., context=...)` | per run, propagates to subagents |
| Compression | automatic offloading + summarization ([[summarization]]) | kicks in near limits |
| Isolation | [[subagents]] via `task` | per delegated task |
| Long-term memory | files on a persistent route ([[memory]]) | across threads |

## Input context: how the system prompt is assembled (0.7.29 code)

Main-agent middleware order in `graph.py`: Filesystem -> SubAgent -> ParentNotifier -> Summarization -> PatchToolCalls -> AsyncSubAgent (if any) -> your middleware -> harness-profile extras -> Skills (if `skills=`) -> prompt caching -> Memory (if `memory=`) -> HITL (if `interrupt_on`/interrupt permissions) -> UnsupportedContent. Each prompt-producing middleware appends to the system message, so the model sees roughly:

1. your `system_prompt` + the profile base prompt (`base_system_prompt` / `system_prompt_suffix` from a harness profile)
2. filesystem host-path routing note (only for composite/host backends; the long built-in tool prose was dropped in 0.7, tool schemas carry it)
3. fragments from your own middleware
4. skills index (`## Skills System ...`)
5. `<agent_memory>` + `<memory_guidelines>` (last, with its own cache breakpoint so memory edits do not invalidate the cached prefix)

Checked on 0.7.29 with a scripted model that records its input: `system_prompt`, then a custom `wrap_model_call` fragment, then the skills index, then memory. Before 0.7.29 the skills index came right after your `system_prompt`, ahead of your own fragments.

The docs' list puts memory before skills and includes filesystem/subagent prompt sections; the code order above wins. A skill can also keep related tool schemas out of the prompt until the skill is read (`metadata.include_tools`, [[skills]]). See [[middleware]], [[customization]], [[harness]].

Guidance:
- `system_prompt` is static. For per-user/role text use a `@dynamic_prompt` or custom middleware reading `request.runtime.context` / `request.runtime.store`.
- Tools that only need context or the store do not need middleware: `ToolRuntime` gives `runtime.context`, `runtime.store`, `runtime.state`.
- Memory = always injected, keep it minimal. Skills = on-demand, keep each focused. See [[memory]], [[skills]].
- Unused built-in tools still ship schemas every turn; remove them with a harness profile `excluded_tools`. Override descriptions with `tool_description_overrides`. See [[tools]].
- Planning (`write_todos`) is opt-in in 0.7 ([[planning]]).

## Runtime context

```python
from dataclasses import dataclass
from langchain.tools import ToolRuntime, tool
from deepagents import create_deep_agent

@dataclass
class Context:
    user_id: str

@tool
def fetch_user_data(query: str, runtime: ToolRuntime[Context]) -> str:
    """Fetch data for the current user."""
    return f"{runtime.context.user_id}: {query}"

agent = create_deep_agent(model="anthropic:claude-sonnet-4-6", tools=[fetch_user_data], context_schema=Context)
agent.invoke({"messages": [{"role": "user", "content": "hi"}]}, context=Context(user_id="u1"))
```

- Not visible to the model unless a tool/middleware surfaces it.
- Propagates to all subagents. The same `rt.context` is what `StoreBackend(namespace=lambda rt: ...)` reads, which is how you scope memory per user/workspace.

## Custom state (`deepagents>=0.6.6`)

Subclass `DeepAgentState` (keeps the `DeltaChannel` messages reducer for linear checkpoint growth) and pass `state_schema=`. Use for mutable, checkpointed values; use runtime context for immutable per-run inputs. Declarative subagents inherit the parent `state_schema`; `CompiledSubAgent` and `AsyncSubAgent` do not.

```python
from deepagents import DeepAgentState, create_deep_agent
class ResearchState(DeepAgentState):
    page_url: str
agent = create_deep_agent(model=..., state_schema=ResearchState)
```

## Compression (automatic)

Always on; details in [[summarization]]. Summary of defaults:
- Tool results > 20,000 tokens (approx `4 * 20000` chars) are written to `/large_tool_results/<tool_call_id>` and replaced by a head/tail preview (5 + 5 lines). `ls`, `glob`, `grep`, `read_file`, `edit_file`, `write_file`, `delete` are exempt.
- Human messages > 50,000 tokens are evicted to a file too.
- Old tool-call args > 2,000 chars are clipped once the history hits the truncation trigger.
- At 85% of the model's `max_input_tokens` (fallback 170k tokens) history is summarized; the evicted messages go to `/conversation_history/<session>.md`; 10% (fallback 6 messages) kept verbatim.
- A provider context-overflow error triggers summarize-and-retry once.
- Opt-in `compact_conversation` tool via `create_summarization_tool_middleware`.
- Summaries can be written by a different, cheaper model: `SummarizationMiddleware(..., summarizer="provider:model")` (also a `Runnable` or function), passed in `middleware=` to replace the default. `model` still drives the profile and token counting ([[summarization]]).
- Opt-in `FilesystemMiddleware(backend=..., offload_binary_content=True)` (in `middleware=`) writes binary `read_file` results and inline `HumanMessage` media to `blobs/` under the artifacts root, keeps a reference in history, and rehydrates it for each model call. It has no effect (and warns) when `blobs/` routes to a `StateBackend`.
- Images are never resized or embedded ([[multimodal]]).
- When streaming tokens, skip `metadata.get("lc_source") == "summarization"` to hide summary generation ([[streaming]]).

## Isolation with subagents

`task` runs a subagent in a fresh context; only its final message returns. Tell subagents to return short summaries, and have them write bulky outputs to files the parent can `read_file`/`grep` selectively. See [[subagents]].

## Long-term memory

The default `StateBackend` is per-thread. Route a prefix to a store for cross-thread files:

```python
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
backend = CompositeBackend(default=StateBackend(),
                           routes={"/memories/": StoreBackend(namespace=lambda _rt: ("memories",))})
```

The directory can start empty; tell the agent in the prompt what to save where (e.g. `/memories/preferences.md`). See [[memory]], [[backends]], [[persistence]].

## Best practices
1. Minimal memory, focused skills.
2. Delegate output-heavy work to subagents; ask for summaries.
3. Persist big data to files; read fragments with `read_file` offsets and `grep` ([[filesystem-tools]]).
4. Document the `/memories/` layout for the agent.
5. Put ids, keys, flags in runtime context.

## Gotchas
- The docs' compaction example writes `backend = StateBackend` (the class). Pass an instance: `create_summarization_tool_middleware(model, StateBackend())`.
- Docs say the large-result preview is "first 10 lines"; code shows first 5 and last 5 lines (`_create_content_preview(head_lines=5, tail_lines=5)`).
- Offloaded results and conversation history land on the default route (usually per-thread `StateBackend`) unless you set `CompositeBackend(artifacts_root=...)` to a routed prefix.
- Prompt order in the docs (memory before skills) does not match code (memory last).

## Sources
- `../sources/docs/oss/python/deepagents/context-engineering.md`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/middleware/summarization.py`
- `../sources/package/deepagents/middleware/filesystem.py`
- `../sources/package/deepagents/middleware/_message_eviction.py`
- `../sources/package/deepagents/middleware/memory.py`
- `../sources/package/deepagents/middleware/skills.py`

## See also
- [[index]]
- [[summarization]]
- [[memory]]
- [[skills]]
- [[subagents]]
- [[middleware]]
- [[backends]]
