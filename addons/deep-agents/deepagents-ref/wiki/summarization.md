---
title: Summarization and offloading (context compression)
id: summarization
type: api
status: code
product: sdk
keywords: summarizer, summarization, SummarizationMiddleware, context compression, compact_conversation, conversation history, large_tool_results, context overflow, ContextOverflowError, trim history, offload, compaction, artifacts_root, context window full, summarize old messages
read_when: Read when the context fills up, history is summarized or lost, tuning summarization triggers, finding offloaded conversation files, or hitting ContextOverflowError.
updated: 2026-10-21
sources_hash: f387ea905a70
---

# Summarization and offloading (context compression)

One-line truth: every deep agent (main, general-purpose and declarative subagents) gets Deep Agents' own `SummarizationMiddleware`, which clips big old tool args, summarizes history near the context limit, writes the evicted messages to a file on the backend, and never deletes `state["messages"]`; `FilesystemMiddleware` separately offloads oversized tool results to files.

## Quick reference

- Every deep agent gets `SummarizationMiddleware` automatically; it never deletes `state["messages"]`, it keeps a private `_summarization_event`.
- Default trigger 85% of `max_input_tokens`, keep 10%; with no model profile, trigger 170,000 tokens and keep 6 messages.
- Evicted messages are archived to `/conversation_history/<session_id>.md`; the summary message tells the agent that path.
- Tool results over 20,000 tokens (`tool_token_limit_before_evict`) go to `/large_tool_results/<tool_call_id>`; set `None` to disable.
- Customize by passing your own `SummarizationMiddleware` in `middleware=` (replaces the built-in by name); `trigger` list is OR, dict is AND.
- Cheaper summaries (0.7.26+): `SummarizationMiddleware(..., summarizer="provider:model")` writes summaries with another model; `model` still sets the profile and token counting.
- Disable with a harness profile `excluded_middleware={"SummarizationMiddleware"}`.
- Opt-in `compact_conversation` tool via `create_summarization_tool_middleware(model, backend)`; refuses below ~50% of the trigger.
- `artifacts_root` on `CompositeBackend` relocates archives; `history_path_prefix` was removed (`TypeError`).
- Gotcha: models without a profile use the 170k trigger, which may exceed a small window; set `profile` or your own trigger.
- Gotcha: summarization never touches memory files; save durable facts to memory first.

## Pieces and where they live

| Mechanism | Code | Default |
| - | - | - |
| Large tool result offload | `FilesystemMiddleware(tool_token_limit_before_evict=20000)` + `_message_eviction.py` | > 20,000 tokens (`4 * 20000` chars) -> `/large_tool_results/<sanitized tool_call_id>` |
| Large human message offload | `FilesystemMiddleware(human_message_token_limit_before_evict=50000)` | > 50,000 tokens (`4 * 50000` chars), last HumanMessage only |
| Old tool-arg truncation | `SummarizationMiddleware(truncate_args_settings=...)` | see defaults below; clip strings > 2000 chars to first 20 chars + `...(argument truncated)` |
| History summarization | `SummarizationMiddleware` | trigger 85% of `max_input_tokens`, keep 10% |
| Evicted-history archive | `_offload_to_backend` | `/conversation_history/<session_id>.md`, appended per event |
| Inline media in evicted msgs | `_offload_inline_media` | `/conversation_history/media/<sha256[:16]>.<ext>` |
| Overflow recovery | `_call_with_budget` | one smaller retry, else `ContextOverflowError` |
| Manual compaction tool | `SummarizationToolMiddleware` (opt-in) | `compact_conversation`, eligible at ~50% of trigger |

All paths are prefixed by `CompositeBackend.artifacts_root` (default `"/"`); non-composite backends use `"/"`. `history_path_prefix` was removed in 0.7 (`TypeError`); set `artifacts_root` instead.

## Defaults (`compute_summarization_defaults(model)`)

Model has `profile["max_input_tokens"]` (int):
- `trigger=("fraction", 0.85)`, `keep=("fraction", 0.10)`
- truncate args: `trigger=("fraction", 0.85)`, `keep=("fraction", 0.10)`

No profile:
- `trigger=("tokens", 170000)`, `keep=("messages", 6)`
- truncate args: `trigger=("messages", 20)`, `keep=("messages", 20)`

`create_summarization_middleware(model, backend)` (what `create_deep_agent` uses) sets `trim_tokens_to_summarize=None` (summarize all selected history). Constructing `SummarizationMiddleware(...)` directly defaults to `trim_tokens_to_summarize=4000`, `keep=("messages", 20)`, `trigger=None`, and truncation off. Token counting defaults to `count_tokens_approximately` and includes system message + tool schemas.

## What happens on a model call (`wrap_model_call`)

1. Rebuild effective messages: if `_summarization_event` exists, `[summary_msg] + messages[cutoff_index:]`.
2. Count tokens once; clip large string args of tool calls before the truncation keep window.
3. Summarize if the trigger is met or the request exceeds the input budget (`0.95 * max_input_tokens - max output tokens`).
4. Otherwise call the model; on a recognised context-overflow error (`ContextOverflowError`, or HTTP 400/413/422 with messages like "prompt is too long", "maximum context length") fall through to summarization.
5. Summarize: partition at cutoff, upload inline media, append the evicted messages (XML buffer string, filtered of previous summaries) under `## Summarized at <iso>` to the history file, generate the summary with the same model, or with `summarizer` when set (async path runs these concurrently).
6. Summary message is a `HumanMessage(additional_kwargs={"lc_source": "summarization"})`:

```
You are in the middle of a conversation that has been summarized.

The full conversation history has been saved to /conversation_history/session_<hex>.md should you need to refer back to it for details.

A condensed summary follows:

<summary>
...
</summary>
```

   If the archive write failed: `Here is a summary of the conversation to date:` and a Python warning ("Older messages will not be recoverable").
7. State update: private `_summarization_event` (`cutoff_index`, `summary_message`, `file_path`) and `_summarization_session_id`. `state["messages"]` is untouched, unlike LangChain's middleware which `RemoveMessage`s everything. A UI reading thread state still sees the full raw transcript.
8. If still over budget, trailing big tool results are clipped/offloaded once (`_clip_overflow_tail`); if that cannot shrink the request, `ContextOverflowError("Model input still does not fit after recovery...")`.

The session id is reused for the whole thread, so one history file per thread (and per subagent invocation).

## Large tool result stub

```
Tool result too large, the result of this tool call <id> was saved in the filesystem at this path: /large_tool_results/<id>
You can read the result from the filesystem by using the read_file tool, but make sure to only read part of the result at a time.
...
Here is a preview showing the head and tail of the result (...):
<first 5 lines> ... [N lines truncated] ... <last 5 lines>
```

Preview lines clip at 1000 chars each. Non-text blocks (images) in the tool message are kept. If the backend write fails the original message is kept. Exempt tools: `ls`, `glob`, `grep`, `read_file`, `edit_file`, `write_file`, `delete` (they self-limit instead). Set `tool_token_limit_before_evict=None` to disable.

## Customizing

Replace the default by passing your own instance: `_apply_custom_middleware` replaces a built-in whose `.name` matches (`SummarizationMiddleware` reports `"SummarizationMiddleware"`), keeping its stack position. Only the main agent is affected; GP subagent inherits it only because the name matches a GP slot, declarative subagents keep their own default.

```python
from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from deepagents.middleware.summarization import SummarizationMiddleware

summ = SummarizationMiddleware(
    model="anthropic:claude-haiku-4-5",          # summarizer model, str or BaseChatModel
    backend=StateBackend(),
    trigger=[("fraction", 0.7), {"messages": 200}],   # list = OR; dict = AND
    keep=("fraction", 0.15),
    trim_tokens_to_summarize=None,
    truncate_args_settings={"trigger": ("fraction", 0.5), "keep": ("messages", 20),
                            "max_length": 2000, "truncation_text": "...(truncated)"},
)
agent = create_deep_agent(model="anthropic:claude-sonnet-4-6", middleware=[summ])
```

### A separate summarizer (0.7.26+)

`summarizer=` replaces the summarization model call, for both automatic summarization and `compact_conversation`. `model` is still used for its profile (the trigger fractions) and token counting, but is no longer called to write summaries.

- A model string or `BaseChatModel`: prompted with `summary_prompt`.
- A `Runnable` or function (sync or async) that takes the messages to summarize and returns the summary text: `summary_prompt` is not used.

```python
summ = SummarizationMiddleware(
    model="openai:gpt-6-sol",          # the agent's model: profile + token counting
    backend=backend,
    trigger=("fraction", 0.85),
    keep=("fraction", 0.10),
    summarizer="openai:gpt-6-luna",    # writes the summaries
)
agent = create_deep_agent(model="openai:gpt-6-sol", backend=backend, middleware=[summ])
```

`create_summarization_middleware(model, backend, summarizer=...)` takes it too and keeps the model-aware defaults. `create_deep_agent` has no `summarizer` argument; pass the middleware. For the tool, build `SummarizationToolMiddleware(summ)` from the same instance; `create_summarization_tool_middleware(model, backend)` has no `summarizer` argument.

Disable entirely via a harness profile `excluded_middleware={"SummarizationMiddleware"}` (the private class reports that public name). See [[middleware]], [[customization]].

Manual compaction tool:

```python
from deepagents.middleware.summarization import create_summarization_tool_middleware
agent = create_deep_agent(model=model, middleware=[create_summarization_tool_middleware(model, StateBackend())])
```

`compact_conversation` takes no args; it refuses until usage is >= ~50% of the auto trigger; shares `_summarization_event` with auto-summarization. `system_prompt=` adds a nudge (default none). Deep Agents Code wires this tool to a user command ([[dcode]]).

## Gotchas
- `max_input_tokens` comes from the model profile; custom/unknown models fall back to the 170k-token trigger, which can exceed small context windows. Set `profile` or pass your own trigger. See [[models]].
- Summarization uses the agent's model by default (unless `summarizer=` is set), so its tokens show up in `stream_mode="messages"`; filter `metadata["lc_source"] == "summarization"` ([[streaming]]).
- With `CompositeBackend(default=StateBackend())`, archives and offloaded results are per-thread state files. Route `artifacts_root` to a store prefix if you need them after the thread.
- Docs say "preview of the first 10 lines"; code shows head 5 + tail 5.
- Docs' compaction example passes the `StateBackend` class; pass an instance.
- Summarization never touches memory files; durable facts must be written to [[memory]] by the agent before they are summarized away.
- Summaries are lossy; the archive path is the recovery path, and the agent must still `read_file` it.
- Evicted media that fails to upload becomes `<image error="failed_to_offload" />` and is unrecoverable.

## Sources
- `../sources/docs/oss/python/deepagents/context-engineering.md`
- `../sources/package/deepagents/middleware/summarization.py`
- `../sources/package/deepagents/middleware/_message_eviction.py`
- `../sources/package/deepagents/middleware/filesystem.py`
- `../sources/package/deepagents/graph.py`

## See also
- [[index]]
- [[context-engineering]]
- [[filesystem-tools]]
- [[backends]]
- [[multimodal]]
- [[fault-tolerance]]
- [[subagents]]
