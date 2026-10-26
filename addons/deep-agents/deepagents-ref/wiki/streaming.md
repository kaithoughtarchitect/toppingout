---
title: Streaming (stream modes, subgraphs, event streaming v3)
id: streaming
type: how-to
status: sourced
product: sdk
keywords: streaming, stream, stream_mode, subgraphs=True, version v2, StreamPart, chunk type ns data, stream_events, astream_events, version v3, stream.subagents, stream.messages, subagent events, token streaming, custom stream, get_stream_writer, updates mode, progress events
read_when: Read when streaming agent output or tokens, seeing no subagent events, or moving to stream_events v3.
updated: 2026-10-21
sources_hash: c7d0b4aa9b85
---

# Streaming (stream modes, subgraphs, event streaming v3)

One-line truth: a deep agent is a compiled LangGraph graph, so you stream it with `agent.stream(..., stream_mode=..., subgraphs=True)`; subagent (`task`) runs are subgraphs identified by a `("tools:<id>", ...)` namespace. For new code the docs recommend the typed projection API `agent.stream_events(input, version="v3")` with `stream.subagents`.

## Two APIs

| API | Use | Notes |
| - | - | - |
| `agent.stream` / `astream` with `stream_mode` + `subgraphs=True` | classic tuple chunks | branch on namespace + mode yourself |
| `agent.stream_events(input, version="v3")` / `await agent.astream_events(...)` | "event streaming" (docs: introduced with Deep Agents v0.6) | typed projections: `.messages`, `.tool_calls`, `.values`, `.subagents`, `.subgraphs`, `.output` |

Neither is implemented inside the `deepagents` package; both come from LangGraph/LangChain. Deep Agents' contribution (verified in code): each subagent runnable is compiled with `name=spec["name"]` (declarative) or `.with_config({"metadata": {"lc_agent_name": name}, "run_name": name})` (compiled), and the top-level graph gets `metadata.lc_agent_name=name` and `recursion_limit=9_999`. That metadata is what lets projections label subagents by their `subagent_type`.

## Classic: stream modes + subgraphs

```python
for namespace, data in agent.stream(
    {"messages": [{"role": "user", "content": "Research quantum computing"}]},
    stream_mode="updates",
    subgraphs=True,            # without this you see no subagent events
):
    source = "main" if not namespace else namespace[0]
    print(source, data)
```

Namespaces:

| Namespace | Source |
| - | - |
| `()` | main agent |
| `("tools:abc123",)` | subagent spawned by a `task` call |
| `("tools:abc123", "model_request:def456")` | node inside that subagent |

Detect subagent: `any(s.startswith("tools:") for s in namespace)`.

The current docs pass `version="v2"`, which yields one dict per chunk instead of a tuple: `chunk["type"]` (the mode), `chunk["ns"]` (the namespace) and `chunk["data"]`. Checked on langgraph 1.2.16: `stream(..., stream_mode="updates", subgraphs=True, version="v2")` gives keys `data`, `ns`, `type`.

```python
for chunk in agent.stream(inp, stream_mode="updates", subgraphs=True, version="v2"):
    if chunk["type"] == "updates":
        print("subagent" if chunk["ns"] else "main", chunk["data"])
```

Chunk shapes:

| `subgraphs` | single mode | multiple modes |
| - | - | - |
| `True` | `(namespace, data)` | `(namespace, mode, data)` |
| `False` | `data` | `(mode, data)` |

Modes:

- `"updates"`: `{node_name: state_delta}` per step. Subagent completion = main-agent `"tools"` node emitting a `ToolMessage` (for `task`, `msg.name == "task"`). Subagent start = main model node emitting an `AIMessage` with a `tool_calls` entry named `"task"` (`args["subagent_type"]`, `args["description"]`).
- `"messages"`: `data = (token, metadata)`; `token` is `AIMessageChunk` (text in `.content`, tool-call deltas in `.tool_call_chunks` with partial `args` strings) or `ToolMessage`.
- `"custom"`: whatever a tool writes via `get_stream_writer()`.
- `"values"`: full state after each step (e.g. `files`, `todos` if [[planning]] middleware is on).

Custom progress from a tool (works inside subagents; arrives under the subagent namespace):

```python
from langchain.tools import tool
from langgraph.config import get_stream_writer

@tool
def analyze_data(topic: str) -> str:
    """Run a data analysis."""
    writer = get_stream_writer()
    writer({"status": "starting", "progress": 0})
    ...
    writer({"status": "complete", "progress": 100})
    return "result"

for ns, mode, data in agent.stream(inp, stream_mode=["updates", "messages", "custom"], subgraphs=True):
    ...
```

## Human-in-the-loop while streaming

With `interrupt_on` (or interrupt-mode `permissions`) set and a checkpointer + `thread_id` (see [[persistence]]), an `"updates"` chunk may contain `"__interrupt__"`; each item's `.value` holds the action requests. Resume by streaming again with `Command(resume={"decisions": [...]})` on the same `thread_id` — same payload as `invoke`. See [[human-in-the-loop]].

```python
for mode, data in agent.stream(inp, stream_mode=["messages", "updates"], config=config):
    if mode == "updates" and "__interrupt__" in data:
        for intr in data["__interrupt__"]:
            print("Approval needed:", intr.value)
```

## Event streaming (v3 projections)

```python
stream = agent.stream_events({"messages": [{"role": "user", "content": "..."}]}, version="v3")

for msg in stream.messages:                  # coordinator only
    print("[coordinator]", msg.text)

for sub in stream.subagents:                 # one handle per task() call
    print(sub.name, sub.path, sub.status)    # name == subagent_type
    for call in sub.tool_calls:
        print(call.tool_name, call.input)
        for delta in call.output_deltas:
            print(delta, end="")
        if call.completed and call.error is None:
            print(call.output)
    for nested in sub.subagents: ...
    final = sub.output                       # raises if the subagent failed
```

Subagent handle fields: `name`, `path` (namespace), `status` (`started` | `completed` | `failed` | `interrupted`), `messages`, `tool_calls`, `values`, `subagents`, `output`. Projections are lazy: message/tool/value streams open only when accessed.

Concurrency:
- async: `stream = await agent.astream_events(inp, version="v3")`, then `asyncio.gather` over `async for` loops; message text is `await message.text`.
- sync: `for name, item in stream.interleave("messages", "subagents"): ...`
- exact arrival order: iterate `for event in stream:` raw protocol events; `event["method"] == "messages"`, payload `event["params"]["data"][0]` with `payload["event"] == "content-block-delta"` and `payload["delta"]["type"] == "text-delta"`; `event["params"]["namespace"]` empty = coordinator.

`stream.subgraphs` = raw graph structure; `stream.subagents` = product-level task delegations (use for UIs).

## Failed turns (for a Trace tab)

Checked with a scripted model on 0.7.20 / langgraph 1.2.12 (2026-09-30), and re-run on 0.7.29 / langgraph 1.2.16 / langchain 1.4.6 on 2026-10-21 with the same results.

| Failure | Default behaviour |
|---|---|
| Model calls an unknown tool, or passes bad args | The stream continues. The `ToolMessage` has `status="error"` and content `Error: nope is not a valid tool, try one of [...]` |
| **A tool raises an exception** | **The whole stream raises**, e.g. `ValueError: boom`. The UI gets no error event, and other tool calls in the same step never appear |
| Model or provider error (e.g. OpenRouter 429) | Raised from the stream. Middleware can't turn it into a tool message |

Fix for raising tools: convert exceptions into an error `ToolMessage`. The agent sees the error and can recover (**ran**: stream completed with `bad_tool error "Tool error: boom"`, then the final answer):

```python
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage

@wrap_tool_call
def catch_tool_errors(request, handler):
    try:
        return handler(request)
    except Exception as e:
        return ToolMessage(content=f"Tool error: {e}", tool_call_id=request.tool_call["id"],
                           name=request.tool_call["name"], status="error")

agent = create_deep_agent(..., middleware=[catch_tool_errors])   # repeat in each subagent spec
```

For model or provider failures, wrap the stream loop in `try/except` and send the UI a synthetic `{"event": "turn_failed", "error": ...}`. The checkpoint keeps the state up to the failed step, and `PatchToolCallsMiddleware` repairs dangling tool calls on the next turn.

Trace-row recipe with `stream_mode=["updates", "messages", "custom"]`, `subgraphs=True` (chunks are `(namespace, mode, data)`):
- `updates` from node `model`: an `AIMessage.tool_calls` entry means a pending row, keyed by `id`.
- `updates` from node `tools`: a `ToolMessage` means the outcome. Match it by `tool_call_id`; `status` is `"success"` or `"error"`.
- `messages`: token deltas. Tool-argument deltas are in `.tool_call_chunks`.
- `custom`: whatever a tool emits via `get_stream_writer()`.
- There's **no Python `"tools"` stream mode**. The JS docs' `on_tool_start` / `on_tool_error` events are JS-only. Python's `StreamMode` is `values | updates | checkpoints | tasks | debug | messages | custom`.
- The v3 `stream_events` API also raised on the tool exception in testing, and `call.error` didn't surface it. Use the middleware either way.

## Gotchas

- Forgetting `subgraphs=True` in the classic API silently hides all subagent tokens/steps; you only see the final `task` `ToolMessage`.
- The `tools:<id>` segment is the Pregel task id, **not** the `tool_call_id` of the `task` call; correlate start/finish via main-agent `tool_calls[i]["id"]` ↔ `ToolMessage.tool_call_id`.
- Docs are inconsistent on node names: one example filters `{"model", "tools"}`, sample output prints `model_request`, and middleware hooks add their own nodes. Print node names from your installed `langchain` before filtering.
- `version="v2"` on `stream` gives `StreamPart` dicts (`type`, `ns`, `data`), which the current Deep Agents streaming docs use; without it you get tuples. `version="v3"` is a different API, the `stream_events` projections. Don't mix them up.
- Subagent output returned to the parent is only the last non-empty AI text (or `structured_response` JSON); the parent never streams subagent tokens unless you subscribe to subgraph/subagent streams.
- Async subagents ([[async-subagents]]) run on a remote deployment; they do not appear as local subgraph namespaces. On an Agent Server their status updates arrive as user-role messages marked with `additional_kwargs["deepagents_notification"]` (since 0.7.26).
- Default recursion limit is `9_999` in 0.7.29 code (frontend docs say "10,000").
- For frontends, prefer `useStream` / AG-UI rather than hand-parsing chunks — see [[frontend]], [[protocols]].

## Sources
- `../sources/docs/oss/python/deepagents/streaming.md`
- `../sources/docs/oss/python/deepagents/event-streaming.md`
- `../sources/package/deepagents/graph.py` (with_config: recursion_limit, lc_agent_name)
- `../sources/package/deepagents/middleware/subagents.py` (subagent naming, result extraction)

## See also
- [[index]]
- [[subagents]]
- [[async-subagents]]
- [[human-in-the-loop]]
- [[frontend]]
- [[protocols]]
- [[tools]]
- [[create-deep-agent]]
- [[persistence]]
- [[planning]]
