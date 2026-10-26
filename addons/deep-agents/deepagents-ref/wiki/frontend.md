---
title: Frontend UIs over a Python deep agent
id: frontend
type: how-to
status: sourced
product: sdk
keywords: frontend, UI, useStream, @langchain/react, React, Vue, Svelte, Angular, langgraph dev, langgraph.json, Agent Server, subagent cards, todo list UI, sandbox IDE, chat UI, stream.values
read_when: Read when building a web UI over a deep agent, or deciding what state the frontend should render.
updated: 2026-10-21
sources_hash: 4525d11c66e0
---

# Frontend UIs over a Python deep agent

One-line truth: the "frontend" docs are JS/React (`useStream` from `@langchain/react`, plus Vue/Svelte/Angular); the Python side is only "serve `create_deep_agent(...)` as a LangGraph graph (`langgraph.json`, `langgraph dev` on `:2024`) and put in state what the UI should render". This page captures that Python contract.

## Architecture

```
useStream()  --submit/stream-->  LangGraph Agent Server  -->  create_deep_agent graph
     |                                                          |-- task -> subagent A/B
     '-- stream.messages / stream.subagents / stream.values <---'
```

Python side:

```python
# agent.py
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="google_genai:gemini-3.6-flash",
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
    subagents=[{"name": "researcher", "description": "Research assistant",
                "system_prompt": "You are a research assistant."}],
)
```

```json
{ "dependencies": ["."], "graphs": { "agent": "./agent.py:agent" }, "env": ".env" }
```

Frontend connects with `useStream({ apiUrl: "http://localhost:2024", assistantId: "agent" })`. Type inference for a Python backend is documented under LangChain frontend overview.

## What the UI reads (the contract)

| Projection (JS) | Backed by (Python) |
| - | - |
| `stream.messages` | coordinator `messages` only (subagent messages are not mixed in) |
| `stream.subagents` | `SubagentDiscoverySnapshot`s: one per `task` call; identity (`name` = `subagent_type`), namespace, status. No messages inside — pass the snapshot to `useMessages(stream, subagent)` / `useToolCalls(stream, subagent)` to lazily subscribe |
| `stream.values.todos` | `todos` state key — **only exists if you add `TodoListMiddleware`** |
| `stream.values.<key>` | any state key your agent writes (custom `state_schema`/middleware state) |
| tool-call state | tool calls/results on messages (render cards per tool) |
| interrupts | `interrupt_on` / interrupt permissions + checkpointer — see [[human-in-the-loop]] |

Status strings: the React progress example counts `status === "complete"`; Python event streaming documents `completed`. Check the SDK type you actually get.

## Pattern: subagent cards

- No extra server options needed. Index subagent cards by the coordinator tool-call id that spawned them so each card sits under the delegating turn; optionally also a sidebar over all `stream.subagents`.
- Submit via root stream: `stream.submit({messages:[...]}, {config:{recursion_limit: 100}})`. Deep Agents already sets a large default (`9_999` in 0.7.29 code; docs say 10,000) — only override if needed.
- Handle errors per card; collapse finished cards when there are many. See [[subagents]], [[streaming]].

## Pattern: todo list

```python
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware

agent = create_deep_agent(model="google_genai:gemini-3.6-flash", middleware=[TodoListMiddleware()])
```

`todos` items have `content` + `status` in `"pending" | "in_progress" | "completed"`; the UI reads `stream.values.todos` reactively (no polling). Without the middleware the key is absent. See [[planning]].

## Pattern: sandbox IDE (file tree + diff + chat)

Three parts: (1) deep agent with a sandbox backend (fs tools + `execute`), (2) custom FastAPI app mounted via `langgraph.json` `"http": {"app": "./src/api/server.py:app"}`, (3) three-panel UI. The agent backend and the HTTP routes must resolve the **same sandbox per thread**; store `sandbox_id` in thread metadata and share one `get_or_create_sandbox_for_thread(thread_id)` helper. See [[sandboxes]], [[backends]], [[production]].

```python
# src/api/server.py  (routes are served on the same host as the LangGraph API)
from fastapi import FastAPI, Query, Path
app = FastAPI()

@app.get("/sandbox/{thread_id}/tree")
async def list_tree(thread_id: str = Path(...), filePath: str = Query("/app")):
    sandbox = await get_or_create_sandbox_for_thread(thread_id)
    result = await sandbox.aexecute(f"find {filePath} -printf '%y\\t%s\\t%p\\n' 2>/dev/null | sort")
    ...
    return {"path": filePath, "entries": entries, "sandboxId": sandbox.id}

@app.get("/sandbox/{thread_id}/file")
async def read_file(thread_id: str = Path(...), filePath: str = Query(...)):
    sandbox = await get_or_create_sandbox_for_thread(thread_id)
    results = await sandbox.adownload_files([filePath])
    return {"path": filePath, "content": results[0].content.decode()}
```

`aexecute`, `adownload_files`, `id` exist on `BaseSandbox`/`LangSmithSandbox` in 0.7.29. Thread id inside the graph: `langgraph.config.get_config()["configurable"]["thread_id"]`.

UI rules from the docs: persist `threadId` in `sessionStorage` so reloads reconnect to the same sandbox; refresh one file when a `write_file`/`edit_file`/`delete` `ToolMessage` arrives and the whole tree after `execute`; snapshot files before each run and default to diff view for changed files; filter `node_modules`; seed files with `upload_files` before the first run; keep secrets out of the sandbox (auth proxy).

## Gotchas

- Docs' sandbox example passes `backend=lambda _runtime: get_or_create_sandbox_for_thread(...)`. **In 0.7.29 this raises `TypeError`**: `FilesystemMiddleware` rejects callables ("Backend factories were removed in deepagents 0.7; pass StateBackend(), CompositeBackend(...), or another BackendProtocol instance"). Code wins: resolve the sandbox in an async **graph factory** (the `langgraph.json` graph is a function that builds and returns `create_deep_agent(backend=<instance>)` per run) — see [[production]].
- The docs' sequence diagram calls `LangSmithSandbox.create()`; no such method in 0.7.29 — `LangSmithSandbox(sandbox)` wraps an existing `langsmith` `Sandbox`. The docs' agent-side helper is sync while the API routes `await` it; pick one.
- `http.app` routes take priority over built-in Agent Server routes; don't shadow `/threads` or `/runs`.
- `todos` in subagents is excluded from the state merged back into the parent (`_EXCLUDED_STATE_KEYS`), so `stream.values.todos` reflects only the coordinator's plan.
- Alternative wire protocol for non-LangChain frontends: AG-UI via `@ag-ui/langgraph` — see [[protocols]].
- Files in `StateBackend` live in `values.files` (thread state) and need a checkpointer to persist across runs — see [[persistence]], [[filesystem-tools]].

## Sources
- `../sources/docs/oss/python/deepagents/frontend/overview.md`
- `../sources/docs/oss/python/deepagents/frontend/subagent-streaming.md`
- `../sources/docs/oss/python/deepagents/frontend/todo-list.md`
- `../sources/docs/oss/python/deepagents/frontend/sandbox.md`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/middleware/filesystem.py` (backend factory TypeError)
- `../sources/package/deepagents/middleware/subagents.py` (`_EXCLUDED_STATE_KEYS`)
- `../sources/package/deepagents/backends/langsmith.py`

## See also
- [[index]]
- [[streaming]]
- [[subagents]]
- [[planning]]
- [[sandboxes]]
- [[backends]]
- [[production]]
- [[protocols]]
- [[human-in-the-loop]]
- [[persistence]]
- [[filesystem-tools]]
