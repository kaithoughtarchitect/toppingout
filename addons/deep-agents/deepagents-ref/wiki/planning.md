---
title: Planning (write_todos / TodoListMiddleware)
id: planning
type: how-to
status: code
product: sdk
keywords: write_todos, TodoListMiddleware, todo list, planning tool, task planning, todos state, progress tracking, plan and track tasks, write_todos missing, opt-in planning, Codex harness profile
read_when: Read when write_todos is missing or a prompt says use write_todos, or when adding planning/progress tracking to a long multi-step agent.
updated: 2026-10-21
sources_hash: 3bf6b7970a8e
---

# Planning (write_todos / TodoListMiddleware)

One-line truth: since `deepagents` 0.7.0 the `write_todos` planning tool is **opt-in**. You get it only by adding LangChain's `TodoListMiddleware` yourself (or via a harness profile that ships it). Reach for it on long multi-step tasks, with weaker models that need an accountability tool, or when a UI renders progress from `state["todos"]`.

## Where it comes from

- `write_todos` is **not** a deepagents tool. It comes from `langchain.agents.middleware.TodoListMiddleware`, which adds:
  - the `write_todos` tool
  - a `todos` state channel: a list of items with `content` and `status` (`"pending"` | `"in_progress"` | `"completed"`)
  - a todo-planning system-prompt fragment
- `deepagents/graph.py` in 0.7.29 **never** adds `TodoListMiddleware`. The default main-agent stack is Filesystem → SubAgent → ParentNotifier → Summarization → PatchToolCalls → AsyncSubAgent (if any) → *your middleware* → profile extras → Skills (if `skills=`) → prompt caching → Memory → HITL → UnsupportedContent. See [[middleware]] and [[harness]].
- The only place the package itself adds it is the **OpenAI Codex harness profile** (`profiles/harness/_openai_codex.py`), for `openai:gpt-5.1-codex`, `openai:gpt-5.2-codex` and `openai:gpt-5.3-codex`. Its `extra_middleware` factory returns `[TodoListMiddleware()]`, because the Codex prompt suffix tells the model to reconcile every `write_todos` item before it finishes.

## Enable it

```python
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware

agent = create_deep_agent(
    model="anthropic:claude-sonnet-5",
    middleware=[TodoListMiddleware()],
)
result = agent.invoke({"messages": [{"role": "user", "content": "Plan and do X"}]})
result["todos"]  # [{"content": "...", "status": "completed"}, ...]
```

User middleware is spliced in after the core stack, before the profile, prompt-caching and memory tail (`_apply_custom_middleware(..., core_names=...)`). If a profile already contributes a `TodoListMiddleware`, yours replaces it by `.name` in place, so you never end up with two.

## Planning in subagents

`todos` does **not** cross the subagent boundary. `_EXCLUDED_STATE_KEYS = {"messages", "todos", "structured_response", "skills_metadata", ...}` in `middleware/subagents.py` is stripped from the state the `task` tool passes in, and from the update it returns ("no defined reducer and no clear meaning"). Each subagent has its own list, or none.

To give a subagent a todo list:

```python
researcher = {
    "name": "researcher",
    "description": "Multi-step web research",
    "system_prompt": "Plan with write_todos, then research.",
    "middleware": [TodoListMiddleware()],   # per-SubAgent opt-in
}
agent = create_deep_agent(model=..., subagents=[researcher],
                          middleware=[TodoListMiddleware()])
```

**The general-purpose subagent does not inherit it.** GP inherits only those main-agent middleware whose `.name` matches a default GP slot (Filesystem, Summarization, PatchToolCalls, Skills, profile extras, prompt caching). `TodoListMiddleware` is not one of those slots, so it is dropped. You have two ways around this:
- Pass your own `{"name": "general-purpose", ..., "middleware": [TodoListMiddleware()]}`. This fully replaces the default GP (see [[subagents]]).
- Register a harness profile whose `extra_middleware` returns `[TodoListMiddleware()]`. Profile extras are materialized fresh for the main agent, for GP, and for each declarative subagent whose model resolves to that profile (see [[customization]]).

## How the agent plans (behaviour)

- The model calls `write_todos` with the **full** list each time. The middleware stores it in `state["todos"]`, which is persisted by the checkpointer like any other state.
- Nothing in deepagents forces the model to use the tool or to finish every item. Only a prompt does that: yours, or a profile suffix such as the Codex "Plan Hygiene" section.
- The 0.7 default prompts are lean (the base prompt is empty). So if you want planning behaviour, say so in `system_prompt`. For example, the deep-research example says "Plan: Create a todo list with write_todos to break down the research into focused tasks".
- Parallel delegation pairs well with planning: plan with `write_todos`, then issue several `task` calls in one turn ([[subagents]]).

## UI / streaming

- `stream.values.todos` in `useStream`, or `values` stream mode in Python, gives you live progress. Without `TodoListMiddleware`, `todos` is simply absent from state (see [[frontend]] and [[streaming]]).
- dcode ([[dcode]]) conditionally drops `TodoListMiddleware` (dcode changelog #4685) and renders TODO tool calls expanded.

## Gotchas

- **Pre-0.7 code and tutorials assume `write_todos` exists.** In 0.7.x it silently isn't there: the model just never sees the tool. The changelog lists this as a 0.7.0 breaking change (see [[versions]]).
- Import path: `from langchain.agents.middleware import TodoListMiddleware`. It is not exported from `deepagents`.
- Adding it to the main agent does **not** reach the auto-added general-purpose subagent or custom subagents.
- `todos` is never merged back from a subagent, so parent plans and child plans are independent.
- Codex models (`openai:gpt-5.x-codex`) get `write_todos` automatically through their harness profile, even if you did not ask for it. Other models don't.
- `TodoListMiddleware` constructor options (custom prompt or tool description) are LangChain's API. They are not in the deepagents 0.7.29 source, so check the LangChain reference before relying on specific kwargs.
- `BASE_AGENT_PROMPT` (deprecated, removed in 0.9.0) restores the old authored prompt text, but **not** the todo middleware.

## Sources

- `../sources/docs/oss/python/deepagents/overview.md`
- `../sources/docs/github/deepagents-CHANGELOG.md`
- `../sources/docs/oss/python/deepagents/frontend/todo-list.md`
- `../sources/docs/oss/python/deepagents/tools.md`
- `../sources/docs/oss/python/deepagents/quickstart.md`
- `../sources/docs/oss/python/deepagents/deep-research.md`
- `../sources/docs/oss/python/deepagents/data-analysis.md`
- `../sources/docs/oss/python/langchain/deep-agent-from-scratch.md`
- `../sources/docs/github/deepagents-code-CHANGELOG.md`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/middleware/subagents.py`
- `../sources/package/deepagents/profiles/harness/_openai_codex.py`

## See also

- [[index]]
- [[harness]]
- [[create-deep-agent]]
- [[middleware]]
- [[subagents]]
- [[customization]]
- [[frontend]]
- [[streaming]]
- [[versions]]
- [[dcode]]
