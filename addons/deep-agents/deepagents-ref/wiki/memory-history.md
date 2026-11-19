---
title: Memory edit history
id: memory-history
type: how-to
status: code
product: sdk
keywords: memory history, edit history, audit trail, revision, versioning, undo, diff, original wording, correction, superseded preference, HistoryStoreBackend
read_when: Read when memory edits must keep the prior wording, e.g. an owner corrects a preference and the original must stay visible.
updated: 2026-11-19
sources_hash: 5cca998d88cb
---

# Memory edit history

**Deep Agents keeps no history of memory files.** `StoreBackend.write` and `edit` read the item and `store.put` the new value under the same key, so the old text is gone. Only `created_at` and `modified_at` survive. To keep prior wording, wrap the backend so every change is logged to a separate namespace. The subclass below **ran** on 0.7.20 on 2026-09-30: sync with an in-memory store, and async through a real two-process restart on SQLite and on Postgres 17 (`../scripts/check_persistence.py`). On 0.7.29 (2026-10-21) the sync run and the SQLite restart were re-run with the same result; Postgres was not re-run on 0.7.29. On 0.7.34 (2026-11-09) the async restart was re-run on SQLite and on Postgres 17 (`check_persistence.py`) with the same result; the sync run was not re-run (`backends/store.py` is unchanged from 0.7.29). On 0.7.39 (2026-11-18) the async restart was re-run again on SQLite and Postgres 17 with the same result; the sync run was not (in 0.7.39 only `upload_files` changed in `store.py`).

## Quick reference

- Framework: none. There's no version field, no lock and no write hook (`backends/store.py`, `write` and `edit`).
- The checkpointer's history (`get_state_history`) covers thread state, **not** store-backed memory files.
- Pattern: subclass `StoreBackend`, capture the content before and after, and `store.put` a log entry in a sibling namespace the agent can't reach.
- Result (**ran**): owner says "I prefer detailed answers", then corrects it. The live file holds the correction; history holds `write` (before `None`) and `edit` (before = the original sentence).

## The subclass (ran, sync and async)

The file is `../examples/history_backend.py`; copy it rather than retyping.

```python
import datetime as dt
import uuid
from deepagents.backends import StoreBackend


class HistoryStoreBackend(StoreBackend):
    """StoreBackend that logs every memory change to a sibling "hist" namespace.

    Live files: ("app", "mem", workspace_id). History: ("app", "hist", workspace_id).
    The history namespace is never routed, so the agent cannot read or alter it.
    """

    def _log(self, path: str, **entry) -> None:
        store, ns = self._get_store(), self._get_namespace()
        now = dt.datetime.now(dt.timezone.utc)
        key = f"{path}@{now.strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:6]}"
        store.put((*ns[:-2], "hist", ns[-1]), key, {"path": path, "ts": now.isoformat(), **entry})

    def _current(self, path: str) -> str | None:
        item = self._get_store().get(self._get_namespace(), path)
        return item.value["content"] if item else None

    def write(self, file_path, content):
        before = self._current(file_path)
        res = super().write(file_path, content)
        if res.error is None:
            self._log(file_path, op="write", before=before, after=content)
        return res

    def edit(self, file_path, old_string, new_string, replace_all=False):
        before = self._current(file_path)
        res = super().edit(file_path, old_string, new_string, replace_all)
        if res.error is None:
            self._log(file_path, op="edit", before=before, after=self._current(file_path),
                      old_string=old_string, new_string=new_string)
        return res

    @staticmethod
    def _under(items, file_path: str) -> dict:
        # StoreBackend.delete is recursive: it removes the key and every key under "<key>/".
        base = file_path.rstrip("/")
        return {str(i.key): i.value.get("content") for i in items
                if str(i.key) == base or str(i.key).startswith(base + "/")}

    def delete(self, file_path):
        befores = self._under(self._search_store_paginated(self._get_store(), self._get_namespace()), file_path)
        res = super().delete(file_path)
        if res.error is None:
            for path, before in befores.items():
                self._log(path, op="delete", before=before, after=None)
        return res

    # --- async (used by ainvoke / astream) ---

    async def _alog(self, path: str, **entry) -> None:
        store, ns = self._get_store(), self._get_namespace()
        now = dt.datetime.now(dt.timezone.utc)
        key = f"{path}@{now.strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:6]}"
        await store.aput((*ns[:-2], "hist", ns[-1]), key, {"path": path, "ts": now.isoformat(), **entry})

    async def _acurrent(self, path: str) -> str | None:
        item = await self._get_store().aget(self._get_namespace(), path)
        return item.value["content"] if item else None

    async def awrite(self, file_path, content):
        before = await self._acurrent(file_path)
        res = await super().awrite(file_path, content)
        if res.error is None:
            await self._alog(file_path, op="write", before=before, after=content)
        return res

    async def aedit(self, file_path, old_string, new_string, replace_all=False):
        before = await self._acurrent(file_path)
        res = await super().aedit(file_path, old_string, new_string, replace_all)
        if res.error is None:
            await self._alog(file_path, op="edit", before=before, after=await self._acurrent(file_path),
                             old_string=old_string, new_string=new_string)
        return res

    async def adelete(self, file_path):
        items = await self._asearch_store_paginated(self._get_store(), self._get_namespace())
        befores = self._under(items, file_path)
        res = await super().adelete(file_path)
        if res.error is None:
            for path, before in befores.items():
                await self._alog(path, op="delete", before=before, after=None)
        return res
```

Use it where the plain `StoreBackend` was ([[agent-setup]]):

```python
routes={"/memories/": HistoryStoreBackend(namespace=ns, store=store)}
```

Read the history in the UI straight from the store, like [[agent-setup]]'s `MemoryService`:

```python
entries = sorted(store.search(("app", "hist", workspace_id), limit=10_000), key=lambda i: i.key)
for it in entries:            # it.value: path, ts, op, before, after (+ old_string/new_string for edits)
    ...
```

## Design notes

- **Separate namespace**, never routed under `/memories/`. The agent's file tools can't see or rewrite history, and a `search` on the live namespace doesn't return it (**ran**).
- **The owner's exact words.** The log holds what the *agent* wrote. The owner's original sentence is in the conversation (checkpointer), per thread. To store it with the entry, add a `wrap_tool_call` middleware that, on `write_file`/`edit_file` under `/memories/`, reads the latest human message and passes it along (e.g. via a context var). That's a design, not run.
- **UI edits** should go through the same logging: call the same `_log` shape from your `MemoryService.write`, with `op="ui-write"`.
- **Async:** `ainvoke`/`astream` go through `awrite`, `aedit` and `adelete`, which are overridden above using `store.aget`/`store.aput` (**ran**). If you add a method, add both versions.
- **Not atomic.** The live write and its log entry are two `put`s. A crash in between loses one log entry. Acceptable for an audit trail; use a DB transaction if it must be exact.
- `upload_files` (app-side bulk writes) isn't logged. Override it if you use it. Since 0.7.39 it stores content with a NUL byte as base64 (`_encode_upload`), so `_current` returns base64 text for such a file; log `encoding` too if you keep uploads.
- **Deletes are recursive.** `StoreBackend.delete` removes the key and every key under `<key>/` (`backends/store.py`, `delete`), so `delete` and `adelete` above search the namespace first and log one `delete` entry per removed key, each with its own `before`. On 2026-11-19 (0.7.39, `InMemoryStore`, sync and async) deleting `/notes` logged `/notes/a.md` and `/notes/b.md` and left `/notesX.md` alone; `check_persistence.py` was not re-run for this change.
- `_get_store()`, `_get_namespace()`, `_search_store_paginated()` and `_asearch_store_paginated()` are private helpers of `StoreBackend` (still there in 0.7.39). In 0.7.39 `write`, `edit`, `delete` and their async versions are unchanged from 0.7.34; only `upload_files` changed (`backends/store.py`). On upgrade, re-run `../scripts/check_persistence.py`, which exercises this class.

## Gotchas

- `ContextHubBackend` (LangSmith) has commit history, but it's a different product. It isn't a drop-in for a local store.
- Permission `mode="interrupt"` gives approval before writes, not history ([[permissions]]).

## Sources

- `../sources/package/deepagents/backends/store.py`
- `../sources/package/deepagents/backends/protocol.py`
- `../examples/history_backend.py`
- `../scripts/check_persistence.py`

## See also

- [[index]]
- [[memory]]
- [[agent-setup]]
