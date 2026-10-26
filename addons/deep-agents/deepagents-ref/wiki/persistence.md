---
title: Persistence (checkpointers and stores)
id: persistence
type: concept
status: code
product: sdk
keywords: persistence, checkpointer, store, remember across sessions, long-term memory, InMemorySaver, SqliteSaver, PostgresSaver, PostgresStore, StoreBackend, thread_id, survive restart, durable state
read_when: Read when state or memory is lost after a restart, when thread_id seems ignored, or when choosing a durable checkpointer and store.
updated: 2026-10-21
sources_hash: 8bef6ee98cf3
---

# Persistence (checkpointers and stores)

One-line truth: a deep agent persists through two independent LangGraph objects: the **checkpointer** (per-`thread_id` state: messages, `StateBackend` files, interrupts) and the **store** (cross-thread key-value data that `StoreBackend` reads/writes); both default to nothing, the in-memory versions die with the process, so survival across a restart must be proven with durable implementations.

## Quick reference

- Two layers: checkpointer (per `thread_id`, messages + StateBackend files + interrupts) and store (cross-thread, used by `StoreBackend`).
- `create_deep_agent(checkpointer=None, store=None)`; no defaults are created, so nothing persists unless you pass them.
- Durable options: `SqliteSaver`/`PostgresSaver` and `SqliteStore`/`PostgresStore`; call `.setup()` once on each.
- In-memory savers and stores die with the process; on LangSmith Deployment do not pass either.
- `thread_id` without a checkpointer does nothing; HITL and `thread_limit` need one.
- `StoreBackend(*, namespace, store=None)`: `namespace` is required and keyword-only.
- `CompositeBackend` strips the route prefix: `/memories/AGENTS.md` is stored under key `/AGENTS.md`, so seed that key.
- `MemoryMiddleware` loads `memory=` files once per thread (`memory_contents` is checkpointed).
- Concurrent writes to one store key are last-write-wins; scope namespaces per user.
- Prove durability with a two-process restart test, not by assumption.

## The two layers

| | Checkpointer | Store |
| - | - | - |
| Passed as | `create_deep_agent(checkpointer=...)` | `create_deep_agent(store=...)` (or `StoreBackend(store=...)`) |
| Keyed by | `config["configurable"]["thread_id"]` | namespace tuple + key |
| Holds | full graph state per step: `messages`, `files` (StateBackend), `memory_contents`, summarization state, pending interrupts | whatever `StoreBackend` writes (one item per file) plus anything your app `put`s |
| Deep Agents consumer | `StateBackend` (default backend), HITL, `thread_limit` call limits | `StoreBackend` (usually routed via `CompositeBackend`) |
| In-memory impl | `langgraph.checkpoint.memory.InMemorySaver` (alias `MemorySaver`) | `langgraph.store.memory.InMemoryStore` |
| Durable impl | `SqliteSaver` / `AsyncSqliteSaver` (`langgraph-checkpoint-sqlite`), `PostgresSaver` / `AsyncPostgresSaver` (`langgraph-checkpoint-postgres`) | `SqliteStore` (`langgraph-checkpoint-sqlite`), `PostgresStore` (`langgraph-checkpoint-postgres`) |
| On LangSmith Deployment | provisioned; do not pass one | provisioned; do not pass one |

`create_deep_agent(..., checkpointer: Checkpointer | None = None, store: BaseStore | None = None)` passes both straight to `langchain.agents.create_agent` (graph.py). No defaults are created.

Durable savers/stores are standard LangGraph packages, not part of `deepagents` and not documented in the deepagents sources; the API below is from LangGraph.

## What survives what

| Data | No checkpointer | InMemorySaver / InMemoryStore | SqliteSaver+SqliteStore / Postgres |
| - | - | - | - |
| Messages across turns of one thread (same process) | lost: each `invoke` starts empty, `thread_id` ignored | kept | kept |
| Messages after process restart | lost | lost | kept |
| `StateBackend` files (`/workspace/...`, offloaded `/large_tool_results/`, `/conversation_history/`) | lost after the run | kept per thread until exit | kept per thread |
| `StoreBackend` files (`/memories/...`) across threads | needs a store, else `RuntimeError` | kept until exit | kept |
| Pending HITL interrupt | cannot resume | resumable until exit | resumable after restart |
| Sandbox files | live in the sandbox, independent of both (see [[sandboxes]]) | | |
| `FilesystemBackend` files | on host disk regardless | | |

## How backends map onto the layers

- `StateBackend()` (the default when `backend=None`): files live in the `files` state channel; reads/writes go through LangGraph `CONFIG_KEY_READ`/`CONFIG_KEY_SEND`. Persisted only by the checkpointer, scoped to one thread. Calling it outside a graph raises `RuntimeError`; to pre-seed, pass `{"messages": [...], "files": {...}}` on invoke. Every step is checkpointed, so large files bloat checkpoints.
- `StoreBackend(*, namespace, store=None)`: `namespace` is required and keyword-only (`NamespaceFactory = Callable[[Runtime], tuple[str, ...]]`). Store resolution: explicit `store=` wins, else `langgraph.config.get_store()`, i.e. the store passed to `create_deep_agent`. Components must match `^[A-Za-z0-9\-_.@+:~]+$` (no `*`, `?`, empty strings).
- `CompositeBackend(default, routes, *, artifacts_root="/")`: longest prefix wins, and the route prefix is **stripped** before calling the routed backend. `/memories/AGENTS.md` routed to a `StoreBackend` is stored under key `/AGENTS.md`.
- Store item value format: `{"content": str, "encoding": "utf-8", "created_at": iso, "modified_at": iso}`. Build it with `deepagents.backends.utils.create_file_data(content)`.

## Self-hosted durable setup

```python
from dataclasses import dataclass
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.checkpoint.sqlite import SqliteSaver      # pip install langgraph-checkpoint-sqlite
from langgraph.store.sqlite import SqliteStore

@dataclass
class Ctx:
    user_id: str

def build(checkpointer, store):
    return create_deep_agent(
        model="anthropic:claude-sonnet-5",
        context_schema=Ctx,
        memory=["/memories/AGENTS.md"],
        backend=CompositeBackend(
            default=StateBackend(),
            routes={"/memories/": StoreBackend(namespace=lambda rt: ("memories", rt.context.user_id))},
        ),
        checkpointer=checkpointer,
        store=store,
        system_prompt="Persistent memory lives in /memories/AGENTS.md. Record durable user facts there with edit_file/write_file.",
    )

with SqliteSaver.from_conn_string("checkpoints.db") as cp, SqliteStore.from_conn_string("store.db") as st:
    st.setup()                      # creates tables / runs migrations
    agent = build(cp, st)
```

Postgres: `from langgraph.checkpoint.postgres import PostgresSaver` / `from langgraph.store.postgres import PostgresStore`, both via `.from_conn_string(DB_URI)` context managers, and **call `.setup()` once** on each. If you build the psycopg connection yourself it needs `autocommit=True, row_factory=dict_row`. Use the `Async*` variants with `ainvoke`/`astream`.

## SQLite locally, Postgres in production (async app)

Imports were checked against the installed `langgraph-checkpoint-sqlite` 3.1.1 and `langgraph-checkpoint-postgres` 3.1.2. **Both branches ran** on 2026-09-29 (SQLite, and Postgres 17 in Docker), each through a real two-process restart with memory, history and the conversation surviving: `../scripts/check_persistence.py`. The SQLite branch ran again on `deepagents` 0.7.29 / `langgraph` 1.2.16 on 2026-10-21 with the same result; the Postgres branch was not re-run on 0.7.29.

| Package (`pip install`) | Provides |
|---|---|
| `langgraph-checkpoint-sqlite` | `SqliteSaver`, `AsyncSqliteSaver`, **and** `SqliteStore`, `AsyncSqliteStore` |
| `langgraph-checkpoint-postgres` + `"psycopg[binary,pool]"` | `PostgresSaver`, `AsyncPostgresSaver`, `PostgresStore`, `AsyncPostgresStore` |

```python
import os
from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.sqlite.aio import AsyncSqliteStore
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore

@asynccontextmanager
async def persistence(data_dir: str):
    uri = os.environ.get("AGENT_DB_URL")                     # postgresql://... in production
    if uri:
        async with AsyncPostgresSaver.from_conn_string(uri) as cp, \
                   AsyncPostgresStore.from_conn_string(uri) as st:
            await cp.setup(); await st.setup()
            yield cp, st
    else:                                                       # absolute paths: cwd must not matter
        async with AsyncSqliteSaver.from_conn_string(f"{data_dir}/checkpoints.db") as cp, \
                   AsyncSqliteStore.from_conn_string(f"{data_dir}/store.db") as st:
            await cp.setup(); await st.setup()
            yield cp, st

# FastAPI: enter persistence() in the app lifespan and build the agent inside it; keep it open for the app's life.
```

- **`from_conn_string` is a context manager.** The connection closes when the block exits. An agent built inside and used outside has a dead connection.
- **Sync savers don't do async.** `SqliteSaver` with `ainvoke` raises `NotImplementedError: The SqliteSaver does not support async methods. Consider using AsyncSqliteSaver instead.` (**ran**). Match `Async*` with `ainvoke`/`astream`.
- **`setup()`:** Postgres must have it on first use (it runs migrations and is safe to repeat). SQLite worked without it in testing, but call it anyway. The saver and the store each need their own call.
- `from_conn_string` already sets `autocommit=True, prepare_threshold=0, row_factory=dict_row` for Postgres. A hand-built connection or pool must set them too, or store writes silently don't commit. Use `pool_config=` on the store for concurrency.
- **Windows + async Postgres needs a selector event loop** (**ran**). The default loop fails with `psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop' to run in async mode`. Fix it before `asyncio.run`: `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())`, or pass `loop_factory=asyncio.SelectorEventLoop` to `asyncio.run`. For uvicorn on Windows, check which loop it uses. SQLite doesn't care.
- Switching SQLite to Postgres doesn't migrate data. The schemas match, but the rows aren't copied.

Namespace uses `rt.context.user_id` on purpose: `rt.server_info` is only populated on LangGraph server, so `rt.server_info.user.identity` fails in a plain Python process.

## Demonstrating a restart (do this, do not assume)

Run the same script twice as two separate processes. Pass 1 writes; pass 2 is a fresh interpreter.

```python
# restart_demo.py  -- usage: python restart_demo.py write | python restart_demo.py check
import sys
THREAD = {"configurable": {"thread_id": "demo-thread-1"}}
with SqliteSaver.from_conn_string("checkpoints.db") as cp, SqliteStore.from_conn_string("store.db") as st:
    st.setup()
    agent = build(cp, st)
    ctx = Ctx(user_id="alice")
    if sys.argv[1] == "write":
        agent.invoke({"messages": [{"role": "user", "content":
            "My favourite colour is teal. Save that to memory. Also, the codeword for this chat is PELICAN."}]},
            config=THREAD, context=ctx)
    else:
        # 1) conversation survived: same thread_id, fresh process
        msgs = agent.get_state(THREAD).values["messages"]
        assert any("PELICAN" in str(m.content) for m in msgs), "checkpoint lost"
        r = agent.invoke({"messages": [{"role": "user", "content": "What was the codeword?"}]},
                         config=THREAD, context=ctx)
        print(r["messages"][-1].text)
        # 2) long-term memory survived: raw store read, key has the route prefix stripped
        item = st.get(("memories", "alice"), "/AGENTS.md")
        assert item and "teal" in item.value["content"].lower(), "store lost"
        # 3) memory reaches a NEW thread
        r = agent.invoke({"messages": [{"role": "user", "content": "What is my favourite colour?"}]},
                         config={"configurable": {"thread_id": "demo-thread-2"}}, context=ctx)
        print(r["messages"][-1].text)
```

Pass criteria: all three checks succeed in the `check` process. Swap `SqliteSaver`/`SqliteStore` for `InMemorySaver`/`InMemoryStore` and the `check` run fails: that is the control. The agent may choose not to write memory; assert on the store item, not on the model's words.

## Seeding and reading the store from app code

```python
from deepagents.backends.utils import create_file_data
store.put(("memories", "alice"), "/AGENTS.md", create_file_data("## Prefs\n- concise\n"))
[i.key for i in store.search(("memories", "alice"))]
```

Deployed: `await client.store.put_item((org_id,), "/compliance.md", create_file_data("..."))` via `langgraph_sdk`.

## Gotchas

- `MemoryMiddleware` loads `memory=` files **once per thread**: `before_agent` returns early `if "memory_contents" in state`, and that key is checkpointed. Edits to memory made later in the same thread (or by other threads) are not re-read into the system prompt for that thread; a new `thread_id` picks them up. Missing memory files are skipped silently (`file_not_found`).
- `thread_id` without a checkpointer does nothing. Every "multi-turn" example that omits `checkpointer=` (e.g. the content-builder tutorial) is single-turn.
- Docs seed agent-scoped memory as `store.put(("my-agent",), "/memories/AGENTS.md", ...)` while routing `/memories/` to that StoreBackend. Because `CompositeBackend` strips the prefix, the agent reads key `/AGENTS.md`; the seeded item is never found. The org example (`"/compliance.md"` under `/policies/`) is correct. Code wins.
- Docs show `StoreBackend()` with no args and a "legacy default namespace from assistant_id". Removed in 0.7: `namespace` is required.
- Docs (memory.md full examples, backends.md "factory pattern still works") use `backend=lambda rt: CompositeBackend(default=StateBackend(rt), ...)`. In 0.7.29 factories raise `TypeError("backend must be an initialized backend instance. Backend factories were removed in deepagents 0.7 ...")` and `StateBackend()` takes no arguments.
- HITL and `ToolCallLimitMiddleware/ModelCallLimitMiddleware(thread_limit=...)` require a checkpointer; resume must reuse the same `thread_id`.
- Concurrent writes to the same store key are last-write-wins. Prefer user-scoped namespaces or per-topic files.
- `InMemoryStore` and `InMemoryVectorStore` in tutorials are demo-only; they vanish on restart.
- Subagents share the parent's `files` channel (only `messages`, `todos`, `structured_response`, `skills_metadata`, `pinned_skills`, `rubric` and private keys are excluded), so `StateBackend` files written by the parent are visible to [[subagents]] and vice versa.
- In 0.7.29 a subagent's returned state drops keys it gave back unchanged (not in 0.7.20). A custom state key that parallel `task` calls may each change still needs a reducer, or the step fails with `InvalidUpdateError`.

## Sources

- `../scripts/check_persistence.py`

- `../sources/docs/oss/python/deepagents/going-to-production.md`
- `../sources/docs/oss/python/deepagents/memory.md`
- `../sources/docs/oss/python/deepagents/backends.md`
- `../sources/docs/oss/python/deepagents/human-in-the-loop.md`
- `../sources/docs/github/deepagents-CHANGELOG.md`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/backends/state.py`
- `../sources/package/deepagents/backends/store.py`
- `../sources/package/deepagents/backends/composite.py`
- `../sources/package/deepagents/backends/utils.py`
- `../sources/package/deepagents/middleware/memory.py`
- `../sources/package/deepagents/middleware/filesystem.py`
- `../sources/package/deepagents/middleware/subagents.py`

## See also

- [[index]]
- [[backends]]
- [[memory]]
- [[human-in-the-loop]]
- [[production]]
- [[fault-tolerance]]
- [[create-deep-agent]]
- [[summarization]]
- [[subagents]]
- [[context-engineering]]
