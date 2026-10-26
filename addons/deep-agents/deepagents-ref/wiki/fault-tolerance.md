---
title: Fault tolerance
id: fault-tolerance
type: how-to
status: code
product: sdk
keywords: fault tolerance, retry, ModelRetryMiddleware, ToolRetryMiddleware, ModelFallbackMiddleware, ModelCallLimitMiddleware, ToolCallLimitMiddleware, rate_limiter, 429, resilience, error handling, timeout, fallback model
read_when: Read when adding retries, fallback models, call limits or rate limiting, or when errors kill a run or a subagent.
updated: 2026-10-21
sources_hash: bdc5f6b1a342
---

# Fault tolerance

One-line truth: resilience is added with LangChain prebuilt middleware passed through `create_deep_agent(middleware=[...])` (retry, fallback, call limits, tool-error conversion) plus a model-level `rate_limiter`; nothing is on by default, and top-level middleware does **not** reach declarative subagents.

## Strategy by error type

| Error | Who fixes | Tool |
| - | - | - |
| Transient (network, 429, 5xx) | system | `ModelRetryMiddleware`, `ToolRetryMiddleware` |
| LLM-recoverable (bad tool input, parse failure) | model | `ToolErrorMiddleware` -> error `ToolMessage` |
| User-fixable (missing info) | human | `interrupt_on` / `interrupt()` ([[human-in-the-loop]]) |
| Provider outage | system | `ModelFallbackMiddleware` |
| Runaway loops / budget | system | `ModelCallLimitMiddleware`, `ToolCallLimitMiddleware` |
| Unexpected | developer | let it propagate |

All middleware classes import from `langchain.agents.middleware`. Their signatures come from the docs; `langchain` is not in this repo's sources.

## Full resilient stack

```python
from deepagents import create_deep_agent
from langchain.agents.middleware import (
    ModelRetryMiddleware, ToolRetryMiddleware, ModelFallbackMiddleware,
    ModelCallLimitMiddleware, ToolCallLimitMiddleware, ToolErrorMiddleware,
)
from langchain.chat_models import init_chat_model
from langchain.rate_limiters import InMemoryRateLimiter

rate_limiter = InMemoryRateLimiter(
    requests_per_second=0.1,     # 1 request / 10 s
    check_every_n_seconds=0.1,
    max_bucket_size=10,          # burst size
)
model = init_chat_model("google_genai:gemini-3.6-flash", rate_limiter=rate_limiter)

def on_error(exc: Exception, request) -> str | None:     # request: ToolCallRequest
    if isinstance(exc, (ValueError, KeyError)):
        return f"Tool `{request.tool_call['name']}` failed: {type(exc).__name__}. Fix the input and retry."
    return None   # anything else propagates and halts the run

resilience = [
    ModelRetryMiddleware(max_retries=3, backoff_factor=2.0, initial_delay=1.0),
    ToolRetryMiddleware(max_retries=2, tools=["search", "fetch_url"], retry_on=(TimeoutError, ConnectionError)),
    ModelFallbackMiddleware("gpt-5.5"),
    ModelCallLimitMiddleware(run_limit=50),
    ToolCallLimitMiddleware(run_limit=200),
    ToolErrorMiddleware(on_error),          # langchain>=1.3.14
]

agent = create_deep_agent(
    model=model,
    tools=[search, fetch_url],
    middleware=resilience,
    subagents=[{
        "name": "researcher",
        "description": "Web research",
        "system_prompt": "...",
        "tools": [search, fetch_url],
        "middleware": resilience,          # must be repeated, see Gotchas
    }],
)
```

## Details per piece

- **Rate limiting**: `rate_limiter=` on the chat model throttles request rate; it is not middleware. It works with `create_deep_agent(model=<BaseChatModel>)`.
- **Retries**: `ModelRetryMiddleware(max_retries, backoff_factor, initial_delay)` uses exponential backoff. Standard LangChain exceptions (`ModelRateLimitError`, `ModelTimeoutError`, `ModelAuthenticationError`, ...) carry `is_retryable`, which the retry middleware respects by default. Scope `ToolRetryMiddleware(tools=[...], retry_on=(...))` to network tools; retrying `read_file` is pointless.
- **Fallback**: `ModelFallbackMiddleware("gpt-5.5")` switches model when the primary fails outright.
- **Call limits**: `run_limit` caps per invocation (resets each turn); `thread_limit` caps across a conversation and requires a checkpointer ([[persistence]]).
- **Tool errors**: without `ToolErrorMiddleware` a raising tool halts the run. The handler returns a string (sent to the model as an error `ToolMessage`) or `None` (re-raise). Async handlers and composition with retry are covered in LangChain's prebuilt-middleware docs.
- **Durability**: with a durable checkpointer a crashed/timed-out run resumes from the last checkpoint on the same `thread_id` without redoing completed steps.
- **Recursion**: `create_deep_agent` sets `recursion_limit=9_999` via `.with_config`. Use call limits, not the recursion limit, as the budget guard.

## Where user middleware lands (code)

- `_apply_custom_middleware`: a user middleware whose `.name` matches a built-in (e.g. `SummarizationMiddleware`) replaces it in place. Otherwise it is inserted after the core stack (Filesystem, SubAgent, the private `_ParentNotifierMiddleware`, Summarization, PatchToolCalls, AsyncSubAgent) and before the harness-profile / Skills / prompt-caching / `MemoryMiddleware` / `HumanInTheLoopMiddleware` / `UnsupportedContentMiddleware` tail (0.7.29 order; [[middleware]] has the full list).
- Declarative (`mode="isolated"`, the default) subagents get only their spec's `middleware`. Forked subagents (`mode="fork"`, experimental) inherit the parent `middleware` list. The auto-added general-purpose subagent inherits only user middleware whose name overrides one of its default slots, so a new `ModelRetryMiddleware` is **not** inherited by it. `CompiledSubAgent` runnables keep whatever they were built with.
- `create_agent` rejects two middleware with the same `.name`, so you cannot add two `ModelRetryMiddleware` instances with different settings to one stack.

## Gotchas

- Top-level `middleware=[...]` protects only the main agent loop. Subagent model calls get no retries, fallback or limits unless you put the middleware in each `SubAgent["middleware"]`. The GP subagent cannot receive them this way; to cover it, override it by declaring a subagent named `general-purpose` ([[subagents]]).
- Doc snippets reference `ToolCallRequest` without importing it; in the handler just annotate loosely or import it from LangChain's agent middleware types.
- The docs' "Transient errors" tab shows `langchain.agents.create_agent`; the same middleware works unchanged with `create_deep_agent(middleware=...)`.
- A call limit hit ends the run; pair it with a clear final message path so users are not left with a silent stop.
- Rate limiter is per model instance and in-memory: separate processes and subagents with a different `model` string do not share it.

## Sources

- `../sources/docs/oss/python/deepagents/fault-tolerance.md`
- `../sources/docs/oss/python/deepagents/going-to-production.md`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/middleware/subagents.py`

## See also

- [[index]]
- [[middleware]]
- [[human-in-the-loop]]
- [[subagents]]
- [[models]]
- [[production]]
- [[persistence]]
- [[create-deep-agent]]
