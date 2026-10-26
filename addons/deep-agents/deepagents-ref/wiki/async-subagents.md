---
title: Async subagents (background tasks on Agent Protocol servers)
id: async-subagents
type: api
status: code
product: sdk
keywords: async subagent, async sub-agent, background task, AsyncSubAgent, start_async_task, Agent Protocol, graph_id, long-running agent, non-blocking subagent, LangSmith Deployment, remote subagent, cancel task, update task, TaskEvent, task notification, deepagents_notification, waiting status, fork mode, parent_thread_id
read_when: Read when work should run in the background while the supervisor keeps talking, or when wiring a remote graph as a subagent.
updated: 2026-10-21
sources_hash: 9a208c16024b
---

# Async subagents (background tasks on Agent Protocol servers)

One-line truth: `AsyncSubAgent` specs point at graphs on an Agent Protocol server (LangSmith Deployment or self-hosted). The supervisor gets five tools to start, check, update, cancel and list background runs. `start_async_task` returns a task id immediately, so the supervisor keeps talking to the user while the work runs. On an Agent Server (async path) the supervisor is also told when a task finishes, fails or waits for a human (since 0.7.26, beta). Use this for long-running, parallel or steerable work. Use sync [[subagents]] when the parent should wait for the result.

## Configure

```python
from deepagents import AsyncSubAgent, create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-5",
    subagents=[
        AsyncSubAgent(name="researcher", description="Deep research; many searches + synthesis",
                      graph_id="researcher"),                      # no url -> ASGI (in-process)
        AsyncSubAgent(name="coder", description="Code generation and review",
                      graph_id="coder", url="https://coder.example.langsmith.dev",
                      headers={"x-api-key": "..."}),                # url -> HTTP
    ],
)
```

`AsyncSubAgent` is a `TypedDict` with these fields:
- `name` (required)
- `description` (required)
- `graph_id` (required; the graph name or assistant id on the server, which must match `langgraph.json`)
- `url` (optional)
- `headers` (optional)
- `mode` (optional, since 0.7.24): `"isolated"` (default) sends only the task description; `"fork"` sends a snapshot of the parent's conversation at launch, then the description. Fork is experimental (it emits a beta warning) and later parent messages are not forwarded. Any other value raises `ValueError`. For prompt-cache hits the remote agent needs the same model, system prompt, tools and prompt middleware as the parent; fork copies history, not settings.

`create_deep_agent` routes any spec that has a `graph_id` key to `AsyncSubAgentMiddleware`, which is appended after `PatchToolCallsMiddleware` ([[middleware]]). Async and sync subagents coexist, and disabling GP does not affect async ones.

Co-deployed `langgraph.json`:

```json
{"graphs": {"supervisor": "./src/supervisor.py:graph",
            "researcher": "./src/researcher.py:graph",
            "coder": "./src/coder.py:graph"}}
```

## Tools (exact names and args)

| tool | args | behaviour (code) |
| - | - | - |
| `start_async_task` | `description`, `subagent_type` | `threads.create(metadata={"subagent_name": <name>, "parent_thread_id": <parent thread>})`, then `runs.create(thread_id, assistant_id=graph_id, input={"messages": [...]})`. The messages are one user message with `description` (isolated) or the parent's conversation plus the description (fork). Returns `"Launched async subagent. task_id: <thread_id>"`. **task_id == thread_id** |
| `check_async_task` | `task_id` | `runs.get`. On `success` it fetches thread values and returns JSON `{"status","thread_id","result"}`, where `result` is the **last message's content**. On `error` it returns `{"error": ...}`. On `waiting` it returns `interrupts` (`id` and `value` each) and a `note` that the user, not the supervisor, answers |
| `update_async_task` | `task_id`, `message` | new `runs.create` on the same thread with `multitask_strategy="interrupt"`. The old run is interrupted and the subagent sees the full history plus the new message. Same task_id, new run_id. On a `waiting` task the pending human request is dropped (the reply says so) |
| `cancel_async_task` | `task_id` | `runs.cancel`, then marks the task `"cancelled"`. A `waiting` task has no active run, so it is only marked |
| `list_async_tasks` | `status_filter` (`running`, `waiting`, `success`, `error`, `cancelled` or `all`; default all) | filters on **cached** status, then fetches live status for non-terminal tasks (in parallel when async) |

Terminal statuses skipped by the live fetch: `cancelled`, `success`, `error`, `timeout`, `interrupted`. `waiting` (the run finished but the thread is interrupted, for example by `interrupt()` or HITL) is not terminal. `interrupted` means a run cancelled or replaced on the server, not a human pause.

## Task notifications and `waiting` (beta, since 0.7.26)

Only on the async path (`ainvoke`/`astream`, which the Agent Server uses). With `invoke` only the five tools work.

- `AsyncSubAgentMiddleware` checks unfinished tasks (`running`, `pending`, `waiting`) in `abefore_agent`, `abefore_model` and, after a final answer, `aafter_model`. Each task check times out after 5 s and is retried next time. A new outcome (`success`, `error`, `timeout`, `waiting`) is added as a user message. When a final answer brings an update, it jumps back to the model for another turn.
- `create_deep_agent` adds `_ParentNotifierMiddleware` to every deep agent. When that agent runs as an async subagent on the same deployment and its run ends (or a model call fails), it starts a notification run on the parent's thread, but only if the parent thread is `idle` or `error` (`multitask_strategy="reject"`). A busy parent picks the update up itself; a parent waiting for a human gets it after the user answers.
- The message carries a `TaskEvent` (`task_id`, `agent_name`, `status`, optional `run_id`) in `additional_kwargs["deepagents_notification"]`, so a UI can render it apart from user messages. Import it with `from deepagents.middleware import TaskEvent` (it is not exported from `deepagents`). Result text is cut at 80,000 characters; images in the result pass through.

```python
for message in state["messages"]:
    if event := message.additional_kwargs.get("deepagents_notification"):
        print(event["agent_name"], event["status"])  # success, error, timeout or waiting
```

- A `waiting` subagent is answered by your app on the subagent's own thread (the task id), for example `client.runs.create(task_id, graph_id, command={"resume": {interrupt_id: answer}})`. The supervisor cannot approve for the user.
- Find a supervisor's subagent threads with `client.threads.search(metadata={"parent_thread_id": ...})`; a subagent's graph factory can read `config["metadata"]["parent_thread_id"]`. Check access first: anyone with access to a thread can edit its metadata.

## State: `async_tasks`

- `AsyncSubAgentState.async_tasks: dict[task_id, AsyncTask]` uses a merge reducer (dict update).
- `AsyncTask` fields: `task_id`, `agent_name`, `thread_id`, `run_id`, `status`, `created_at`, `last_checked_at`, `last_updated_at`. Timestamps are ISO-8601 UTC `YYYY-MM-DDTHH:MM:SSZ`.
- Task ids live in state rather than only in messages, so they survive compaction by [[summarization]]. The supervisor can always recover them with `list_async_tasks`.
- An unknown or truncated id returns `"No tracked task found for task_id: ..."`. Ids are `.strip()`ed but otherwise must match exactly.

## Transports and auth

- **No `url`**: the LangGraph SDK uses ASGI (in-process) transport. Both graphs must be in the same deployment. This is the recommended default, with zero network latency.
- **`url` set**: HTTP transport. Auth comes from env `LANGSMITH_API_KEY`, `LANGGRAPH_API_KEY` or `LANGCHAIN_API_KEY`, handled by the SDK. `headers` is for custom auth on self-hosted servers.
- The header `x-auth-scheme: langsmith` is added by default unless you supply your own `x-auth-scheme`.
- Clients are cached per `(url, headers)`.
- Topologies: single deployment (all ASGI), split (supervisor and workers on different servers over HTTP), or hybrid ([[production]], [[managed]], [[protocols]]).

## Operating tips

- Local `langgraph dev`: each active run holds a worker slot. A supervisor with 3 concurrent tasks needs 4 slots, so use `langgraph dev --n-jobs-per-worker 10`. Too few slots means launches queue.
- The start tool's description already says: report the id and stop, don't check just to see if it's done (a notification usually arrives), and use `check_async_task` when the user asks or a notification says to. The check and list descriptions say that "statuses shown earlier in the conversation are always stale". If a model still polls, truncates ids or reports stale status, add explicit rules to your `system_prompt`.
- Tracing: since 0.7.26, launches and updates of subagents on the same deployment (no `url`) send the parent's LangSmith trace headers, so the subagent run can nest under the parent's trace (beta). Subagents with a `url` get no trace headers; correlate those by thread id, which is the same as the task id.
- Subagents on the same deployment run with the parent's run context.

## Gotchas

- **ASGI transport (no `url`) only works on the async path (`ainvoke`/`astream`).** The sync tools call `get_sync()`, which raises "ASGI transport (url=None) requires async invocation". `start` catches this and returns "Failed to launch async subagent ...", while `check`, `cancel` and `list` return or log errors.
- `AsyncSubAgentMiddleware(system_prompt=None)` is the default since 0.7, so **no** system-prompt prose is injected. The docs' "the middleware injects system prompt rules" really means the guidance lives in the tool descriptions. Pass `system_prompt=` to `AsyncSubAgentMiddleware` directly if you want prose. The available-agent list is then appended to it.
- Duplicate async names raise `ValueError`, and so does an empty `async_subagents`.
- Async subagents do **not** inherit `interrupt_on`, `tools`, `model`, `permissions` or `state_schema`. Configure the remote graph itself ([[human-in-the-loop]]).
- `check_async_task` returns the raw last message `content`. Unlike the sync `task` tool it does not walk back past empty AI messages or serialize `structured_response`.
- In the default `isolated` mode the start input is a single user message with the `description`, so put all context in it. The remote agent shares nothing with the supervisor unless you use `mode="fork"`.
- Notifications are user-role messages in the supervisor's history. Code that treats every `HumanMessage` as the user's words should skip ones with `additional_kwargs["deepagents_notification"]`.

## Sources

- `../sources/docs/oss/python/deepagents/async-subagents.md`
- `../sources/docs/github/deepagents-CHANGELOG.md`
- `../sources/package/deepagents/middleware/async_subagents.py`
- `../sources/package/deepagents/middleware/_parent_notifier.py`
- `../sources/package/deepagents/graph.py`

## See also

- [[index]]
- [[subagents]]
- [[create-deep-agent]]
- [[middleware]]
- [[summarization]]
- [[human-in-the-loop]]
- [[protocols]]
- [[production]]
- [[managed]]
