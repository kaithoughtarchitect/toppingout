---
title: Agent setup — the checked reference setup
id: agent-setup
type: how-to
status: code
product: sdk
keywords: agent setup, reference setup, workspace, workspace_id, per-workspace memory, Memory tab, MemoryService, UI reads memory, read-only except memory, allow then deny, thread per workspace, workspace switch, leakage test, FreshMemory, GPT-6 Luna
read_when: Read when building, reviewing or debugging your agent, its per-workspace memory, its Memory tab, or workspace switching.
updated: 2026-10-21
sources_hash: 8a9fe5e89fb5
---

# Agent setup — the checked reference setup

The whole agent wiring in one place: per-workspace Markdown memory, a durable store and checkpointer, no shell, writes only under `/memories/`, read-only data tools, and a UI that reads the exact files.

**In code:** this page is implemented in `../../src/agent/` and tested in `../../tests/` (6 tests, including a real restart).

**Adapt:** a *workspace* is whatever your agent keeps memory separate by: a user, a project, a customer, a save file. Rename `"app"` in the namespaces to your product name, and `workspace_id` to your unit if you like. The model is the starter default; any `provider:model` string works ([[models]]).

Everything below marked **ran** was executed against `deepagents` 0.7.29, `langgraph` 1.2.16 and `langchain` 1.4.6 on 2026-10-21 (`../scripts/check_recipes.py`, PASS 10/10).

## Quick reference

- Model (starter default): `"openrouter:openai/gpt-6-luna"` + `OPENROUTER_API_KEY` ([[models]]).
- Backend: `CompositeBackend(default=StateBackend(), routes={"/memories/": StoreBackend(namespace=ns, store=store)})`. With no sandbox default there's no `execute` tool (**ran**).
- Permissions, in order: allow write `/memories/**`, then deny write `/**`. Memory writes succeed; other writes return `permission denied` (**ran**). Large-result offload still works (**ran**).
- Namespace: `("app", "mem", workspace_id)`. `workspace_id` must be a slug or UUID. `"My Workspace 1"` raises `ValueError` on the first turn, even for "hi" (**ran**).
- The UI reads store key `/AGENTS.md`, not `/memories/AGENTS.md` (**ran**).
- Durable persistence: `AsyncSqliteSaver` + `AsyncSqliteStore` locally, `AsyncPostgres*` in production. Both ran through a restart on 0.7.20 (2026-09-30); SQLite ran again on 0.7.29 (2026-10-21), Postgres not re-run on 0.7.29. On Windows, async Postgres needs `WindowsSelectorEventLoopPolicy` ([[persistence]]).
- One thread per (workspace, conversation). The framework never binds a thread to a workspace, so the app must.
- Memory-tab edits don't reach an open thread (**ran**). Use `FreshMemory` or start a new thread (below).

## The agent

```python
import re
from dataclasses import dataclass
from langchain.tools import ToolRuntime, tool
from langchain.agents.middleware import ModelRetryMiddleware
from deepagents import create_deep_agent, FilesystemPermission, MemoryMiddleware
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

MODEL = "openrouter:openai/gpt-6-luna"          # needs OPENROUTER_API_KEY, langchain-openrouter>=0.2.0
SLUG = re.compile(r"^[A-Za-z0-9\-_.@+:~]+$")

@dataclass(frozen=True)
class Ctx:
    workspace_id: str                              # internal slug/UUID, never the display name
    def __post_init__(self):
        if not SLUG.match(self.workspace_id):
            raise ValueError(f"workspace_id not store-safe: {self.workspace_id!r}")

def ns(rt) -> tuple[str, ...]:                  # fails closed: no context -> AttributeError, never a shared namespace
    return ("app", "mem", rt.context.workspace_id)

@tool
def get_record(runtime: ToolRuntime[Ctx]) -> str:
    """Read-only. Return the current workspace's record."""
    return data.get_record(runtime.context.workspace_id)   # workspace comes from runtime, never from model args

class FreshMemory(MemoryMiddleware):            # optional: re-read memory at the start of every run
    @property
    def name(self) -> str:
        return "MemoryMiddleware"               # same name -> replaces the built-in slot
    def before_agent(self, state, runtime, config):
        return super().before_agent({k: v for k, v in state.items() if k != "memory_contents"}, runtime, config)
    async def abefore_agent(self, state, runtime, config):
        return await super().abefore_agent({k: v for k, v in state.items() if k != "memory_contents"}, runtime, config)

def build_agent(store, checkpointer, tools):
    backend = CompositeBackend(
        default=StateBackend(),                 # scratch + offloads; not a sandbox -> no execute tool
        routes={"/memories/": StoreBackend(namespace=ns, store=store)},
    )
    sources = ["/memories/AGENTS.md"]
    return create_deep_agent(
        model=MODEL,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        memory=sources,
        backend=backend,
        store=store,
        checkpointer=checkpointer,
        context_schema=Ctx,
        permissions=[                           # first match wins, default allow; file tools only
            FilesystemPermission(operations=["write"], paths=["/memories/**"], mode="allow"),
            FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
        ],
        middleware=[ModelRetryMiddleware(max_retries=3), FreshMemory(backend=backend, sources=sources)],
        # a custom subagent needs its own middleware=[...]; nothing is inherited ([[subagents]])
    )
```

The built-in tools the model then sees (**ran**): `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`, `task`, plus your tools. There's no `execute` and no `write_todos` (add `TodoListMiddleware()` if you want planning: [[planning]]). `task` is the general-purpose subagent. It inherits your tools and permissions.

Invoke:

```python
await agent.ainvoke({"messages": [{"role": "user", "content": text}]},
                    config={"configurable": {"thread_id": thread_id}},
                    context=Ctx(workspace_id=workspace_id))
```

## Memory tab: read the exact files

The UI talks to the **store**, never to `StoreBackend`, because the namespace callable needs a graph `Runtime` and fails outside a run.

```python
from deepagents.backends.utils import create_file_data

class MemoryService:
    def __init__(self, store): self.store = store
    def ns(self, workspace_id): return ("app", "mem", Ctx(workspace_id).workspace_id)   # validates the slug

    def list(self, workspace_id):            # full namespace only: search() is prefix-matching
        return [("/memories" + it.key, it.value["modified_at"])
                for it in self.store.search(self.ns(workspace_id), limit=1000)]

    def read(self, workspace_id, path):      # "/memories/AGENTS.md" -> key "/AGENTS.md"
        it = self.store.get(self.ns(workspace_id), path.removeprefix("/memories"))
        return it.value["content"] if it else None

    def write(self, workspace_id, path, text):
        self.store.put(self.ns(workspace_id), path.removeprefix("/memories"), create_file_data(text))
```

- Store value shape: `{"content", "encoding", "created_at", "modified_at"}` ([[memory]]).
- `search` results past `limit` are silently dropped. Set `limit` above your file count.
- The store keeps no edit history; writes overwrite. For history, use `HistoryStoreBackend` (`../examples/history_backend.py`, sync + async, ran through a restart) in place of `StoreBackend`: [[memory-history]].

### When the owner edits a file in the Memory tab

`memory=` is loaded once per thread and frozen in the checkpoint. The open thread keeps the old text (**ran**). Pick one:

| Option | Effect | Cost |
|---|---|---|
| `FreshMemory` (above) | Re-reads memory at the start of every run (**ran**: the edit shows on the next message) | The memory block changes, which breaks prompt caching for it |
| Start a new thread after a save | Clean, fully supported | Splits the chat |
| Hidden nudge: "preferences changed, read `/memories/AGENTS.md`" | `read_file` reads the live store | Relies on the model following it |
| Keep the file out of `memory=` | Always current, read on demand | Not always in the prompt |

## Workspaces and threads

- **One thread per (workspace, conversation).** Use a deterministic id such as `f"{workspace_id}:{conversation_id}"`, and persist it so the chat reloads after a restart.
- **A workspace switch** means a new `thread_id` and a new `context=Ctx(new_id)` on every call. The agent, store and checkpointer stay. The new thread loads the new workspace's memory on its first turn.
- **The framework does not stop the thread/context mismatch** (thread of workspace A with context of workspace B). Guard it in the app: keep a `thread_id → workspace_id` table, check it before every run, and refuse on mismatch.

## Proving no leakage (test plan)

1. Seed workspaces A and B with different sentinel strings through `MemoryService.write`.
2. Run A and then B, with a fake model scripted to `read_file`, `ls` and `grep` `/memories/` ([[testing]]). Assert neither run's tool results contain the other workspace's sentinel.
3. Assert `store.search(("app","mem",A))` holds only A's keys (**ran**: B's namespace doesn't see A's write).
4. Adversarial paths: `/memories/../x`, `~`, `/app/mem/B`. Expect errors ([[filesystem-tools]]).
5. Interleave A, B, A in one process, then repeat after a restart ([[persistence]]).
6. Call thread A with context B, and assert your guard refuses it.

## Gotchas

- A plain `deny write /**` with no `allow /memories/**` before it also blocks memory writes.
- Permissions don't cover your custom tools. Keep the data tools read-only in code.
- Don't use `FilesystemBackend` or `LocalShellBackend`. They give the model real disk and a shell, and combining them with permissions raises `NotImplementedError` ([[permissions]]).
- GPT-6 Luna on OpenRouter doesn't list `temperature` among its supported parameters (OpenRouter models API, 2026-09-29). Don't rely on it.
- `ModelRetryMiddleware` comes from `langchain.agents.middleware` (not vendored; [[fault-tolerance]]).

## Sources

- `../sources/package/deepagents/middleware/filesystem.py`
- `../sources/package/deepagents/middleware/memory.py`
- `../sources/package/deepagents/backends/store.py`
- `../sources/package/deepagents/backends/composite.py`
- `../sources/package/deepagents/backends/utils.py`

## See also

- [[index]]
- [[memory]]
- [[persistence]]
- [[permissions]]
- [[testing]]
- [[decisions]]
