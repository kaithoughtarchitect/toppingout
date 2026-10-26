---
title: Backends (pluggable filesystem storage)
id: backends
type: api
status: code
product: sdk
keywords: backend, backends, offload_binary_content, blobs, StateBackend, StoreBackend, CompositeBackend, FilesystemBackend, LocalShellBackend, ContextHubBackend, BackendProtocol, namespace, virtual_mode, long-term memory storage, persistent storage, where do files live, custom backend, route prefix, virtual filesystem
read_when: Read when choosing where agent files are stored, persisting files across threads, routing /memories/ to a store, writing a custom backend, or hitting a backend factory TypeError or StoreBackend namespace error.
updated: 2026-10-21
sources_hash: b3aa041a1624
---

# Backends (pluggable filesystem storage)

A backend is the storage (and optionally shell) behind the agent's built-in file tools; pick one with `create_deep_agent(backend=...)`, default `StateBackend()` (thread-scoped, in graph state).

## Quick reference

- Pass `create_deep_agent(backend=<instance>)`; default `StateBackend()` (thread-scoped, no args); factories/callables raise `TypeError` in 0.7.
- `StoreBackend(*, namespace: NamespaceFactory, store=None)`: `namespace` is required and keyword-only; parts must match `^[A-Za-z0-9\-_.@+:~]+$`.
- `FilesystemBackend(root_dir=None, virtual_mode=True, max_file_size_mb=10)`; code default is `virtual_mode=True` (docs say False). Pass it explicitly.
- `LocalShellBackend` with no `env` and `inherit_env=False` has an empty environment (no `PATH`); it is not isolated.
- `CompositeBackend(default, routes, *, artifacts_root="/")`: longest prefix wins; route prefix is stripped (`/memories/x` is key `/x`).
- `execute` always runs on the composite `default` and is exposed only if `default` is a sandbox backend.
- `StateBackend` only works inside a graph run; seed files via `invoke({"files": {...}})`.
- `FilesystemBackend` alone writes `/large_tool_results/` and `/conversation_history/` onto real disk; use a Composite with a `StateBackend` default.
- Custom `BackendProtocol`: return result objects with `error=`, `grep` is literal, `glob` must return absolute paths (relative bypasses permissions deny).
- Multi-tenant servers: never `FilesystemBackend`/`LocalShellBackend`; use `StateBackend` + per-user `StoreBackend` or a sandbox.
- Binary files: on `StateBackend`/`StoreBackend`, `edit_file` on a binary (`encoding: "base64"`) file returns `Error: Cannot edit binary files with text replacements.`; the in-memory `grep` skips binary files. Large media in history: `FilesystemMiddleware(offload_binary_content=True)` (below).

## Mental model

- `FilesystemMiddleware` owns the tools (see [[filesystem-tools]]); the backend only implements `ls/read/write/edit/delete/glob/grep` (+ `execute` for sandboxes). Paths the agent sees are always virtual, absolute, POSIX (`/notes.md`).
- Same backend instance is shared by the main agent, subagents ([[subagents]]), `SkillsMiddleware`, `MemoryMiddleware` ([[memory]]) and summarization ([[summarization]]). Files a subagent writes remain visible to the parent.
- Internal artifacts are written to the backend too: `/large_tool_results/<tool_call_id>` (evicted tool output) and `/conversation_history/` (summarization offload). See [[context-engineering]].
- Pass an **instance**, not a factory (removal history in [[versions]]). In 0.7.29, `FilesystemMiddleware.__init__` raises `TypeError("... Backend factories were removed in deepagents 0.7 ...")` if `backend` is a callable that is not a `BackendProtocol`.

## Built-in backends (all importable from `deepagents.backends`)

`__all__`: `BackendProtocol, CompositeBackend, ContextHubBackend, FilesystemBackend, LangSmithSandbox, LocalShellBackend, NamespaceFactory, StateBackend, StoreBackend, DEFAULT_EXECUTE_TIMEOUT` (=120). `SandboxBackendProtocol` lives in `deepagents.backends.protocol`, `BaseSandbox` in `deepagents.backends.sandbox`.

| Backend | Constructor (0.7.29) | Scope / notes |
| - | - | - |
| `StateBackend` | `StateBackend()` (no args) | Files in the `files` state channel; persists per thread via checkpointer; not shared across threads. Only works inside a graph run (uses `CONFIG_KEY_READ/SEND`); outside raises `RuntimeError`. Pre-seed with `agent.invoke({"messages": [...], "files": {...}})`. |
| `StoreBackend` | `StoreBackend(*, namespace: NamespaceFactory, store: BaseStore \| None = None)` | Cross-thread durable storage in a LangGraph `BaseStore`. `namespace` is **required**. If `store` is None, uses `get_store()` (the `store=` passed to `create_deep_agent`, or platform-provisioned on LangSmith Deployment). |
| `FilesystemBackend` | `FilesystemBackend(root_dir=None, virtual_mode=True, max_file_size_mb=10)` | Real disk. `root_dir` defaults to cwd, resolved. Uses ripgrep for `grep` if `rg` on PATH, else Python fallback (skips files > `max_file_size_mb`). Writes use `O_NOFOLLOW`. |
| `LocalShellBackend` | `LocalShellBackend(root_dir=None, *, virtual_mode=True, timeout=120, max_output_bytes=100_000, env=None, inherit_env=False)` | `FilesystemBackend` + `execute` via `subprocess.run(shell=True, cwd=root_dir)`. No isolation. |
| `ContextHubBackend` | `ContextHubBackend(identifier: str, *, client: langsmith.Client \| None = None)` | Files in a LangSmith Context Hub agent repo; `identifier` is `"owner/name"` or `"-/name"`. Needs `LANGSMITH_API_KEY`. |
| `CompositeBackend` | `CompositeBackend(default, routes: dict[str, BackendProtocol], *, artifacts_root="/")` | Prefix router. |
| `LangSmithSandbox` | `LangSmithSandbox(sandbox: langsmith.sandbox.Sandbox)` | A `BaseSandbox`; see [[sandboxes]]. |

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend, FilesystemBackend
from langgraph.store.memory import InMemoryStore

agent = create_deep_agent(
    model="anthropic:claude-sonnet-5",
    backend=CompositeBackend(
        default=StateBackend(),  # keeps /large_tool_results/ and /conversation_history/ ephemeral
        routes={
            "/memories/": StoreBackend(namespace=lambda rt: (rt.server_info.user.identity,)),
            "/workspace/": FilesystemBackend(root_dir="/abs/path/project", virtual_mode=True),
        },
    ),
    store=InMemoryStore(),  # store goes to create_deep_agent, not the backend; omit on LangSmith Deployment
)
```

### StoreBackend namespaces

`NamespaceFactory = Callable[[Runtime], tuple[str, ...]]`. The factory gets a LangGraph `Runtime`: `rt.context` (your context schema), `rt.server_info` (assistant_id, graph_id, `user.identity` on LangGraph Server), `rt.execution_info` (thread_id, run_id, checkpoint_id).

```python
StoreBackend(namespace=lambda rt: (rt.server_info.user.identity,))      # per user
StoreBackend(namespace=lambda rt: (rt.server_info.assistant_id,))       # per assistant
StoreBackend(namespace=lambda rt: (rt.execution_info.thread_id,))       # per thread
StoreBackend(namespace=lambda _rt: ("memories",))                       # global
```

Validation (`_validate_namespace`): non-empty tuple of non-empty `str`, each matching `^[A-Za-z0-9\-_.@+:~]+$` (no `*`, `?`, `/`, spaces). Outside a graph `runtime` is `None`; a factory that reads it raises `RuntimeError` (use `lambda _rt: (...)` plus `store=` for direct use). `rt.server_info` only carries user/assistant data on LangGraph Server; for plain local `invoke`, derive the namespace from `rt.context` instead.

### FilesystemBackend: virtual_mode and root_dir

- `virtual_mode=True` (code default): every path is treated as `/`-rooted under `root_dir`; `..` and leading `~` raise `ValueError("Path traversal not allowed")`; resolved path must stay inside `root_dir` (symlinks resolved; escapes rejected).
- `virtual_mode=False`: absolute paths used as-is (`/etc/passwd` bypasses `root_dir`), relative paths resolve under `root_dir`. No security.
- Needed for `CompositeBackend` routes: the composite strips the route prefix and passes `/rest/of/path`, which only maps under `root_dir` in virtual mode.
- Neither mode is isolation: with `LocalShellBackend`, `execute` can touch any host path regardless.

### LocalShellBackend specifics

- `env=None, inherit_env=False` gives the shell an **empty environment** (no `PATH`); pass `env={"PATH": "/usr/bin:/bin"}` or `inherit_env=True`.
- stderr lines are prefixed `[stderr] `; output over `max_output_bytes` is cut with `... Output truncated at N bytes.`; non-zero exit appends `Exit code: N`; timeout returns exit code 124. `timeout <= 0` raises `ValueError`. `id` is `local-<8 hex>`.

### CompositeBackend routing rules (from `_route_for_path`)

- Routes sorted longest-first; `"/memories/projects/"` beats `"/memories/"`.
- A route key without a trailing slash (`"/memories"`) routes the same way. Before 0.7.29, `glob`/`grep`/`ls` results from such a route came back with a wrong prefix; write route keys with the trailing slash anyway.
- `/memories/notes.txt` goes to the route backend as `/notes.txt`; `/memories` (no slash) maps to `/` of the route.
- Unmatched paths go to `default` unchanged.
- `ls("/")` merges default entries plus one `is_dir=True` entry per route prefix. `glob`/`grep` fan out and re-prefix result paths.
- `execute` is not routable: always runs on `default`. The `execute` tool is exposed only if `default` is a `SandboxBackendProtocol`.
- `delete` is always advertised; a route whose backend lacks `delete` returns `"Error: deletion is not supported for '<path>'."`.
- `artifacts_root` relocates `/large_tool_results` and `/conversation_history` (e.g. `artifacts_root="/scratch/"`).
- With a `LocalShellBackend` default, the model gets a system-prompt section mapping virtual route prefixes to host paths (virtual `FilesystemBackend` route -> its `cwd`); other routes are marked file-tool-only.

### ContextHubBackend behaviour (code)

- Lazily pulls the repo tree once into an in-memory cache; missing repo = empty (first write creates it). Linked skill repos appear as entries under `/skills/`.
- Writes/edits/deletes are batched (~50 ms window) and pushed as Hub commits with `parent_commit`. On `LangSmithConflictError` it re-pulls, re-applies edits, and retries up to 3 times before raising.
- `glob` honors `path` since 0.7.28 (before, it searched the whole repo); a pattern written from the repo root still matches. `upload_files` accepts UTF-8 only; others get `error="invalid_path"`. Hub failures surface as `"Hub unavailable: ..."`.

## BackendProtocol (write a custom backend)

`class BackendProtocol(abc.ABC)` in `deepagents.backends.protocol`. Nothing is `@abstractmethod`; unimplemented methods raise `NotImplementedError`. Async `a*` variants default to `asyncio.to_thread` of the sync method (override for real async I/O).

| Method | Signature | Contract |
| - | - | - |
| `ls` | `(path) -> LsResult(error, entries: list[FileInfo])` | Non-recursive. |
| `read` | `(file_path, offset=0, limit=2000) -> ReadResult` | Return **raw** text for the window; set `start_line/end_line` (1-indexed), `total_lines`, `next_offset == end_line`. Negative offset -> clamp to 0; `limit <= 0` -> empty content with `no_lines_requested=True`. `__post_init__` raises on inconsistent pagination fields. Binary -> `encoding="base64"`. |
| `write` | `(file_path, content) -> WriteResult(error, path)` | Create **or overwrite** (all built-ins overwrite). |
| `edit` | `(file_path, old_string, new_string, replace_all=False) -> EditResult(error, path, occurrences)` | `old_string` must be unique unless `replace_all`. `StateBackend` and `StoreBackend` refuse binary files. |
| `grep` | `(pattern, path=None, glob=None, *, max_count=None) -> GrepResult(error, matches, truncated)` | **Literal** substring, not regex. Accept `max_count` (else results are trimmed after the fact). |
| `glob` | `(pattern, path=None) -> GlobResult(error, matches, truncated, truncation_reason)` | Files only, `FileInfo.path` must be **absolute** (relative paths silently bypass deny rules). |
| `delete` | `(file_path) -> DeleteResult(error, path)` | Optional; recursive. If not overridden, the `delete` tool is hidden from the model. |
| `upload_files` / `download_files` | `(list[tuple[str, bytes]]) -> list[FileUploadResponse]` / `(list[str]) -> list[FileDownloadResponse]` | App-side transfer; per-item `error` in `file_not_found`, `permission_denied`, `is_directory`, `invalid_path`. |

`FileInfo = {path, is_dir?, size?, modified_at?}`, `GrepMatch = {path, line, text, context_before?, context_after?}`, `FileData = {content: str, encoding: "utf-8"|"base64", created_at?, modified_at?}`.

Rules: return result objects with `error=...`, never raise for expected failures. For `execute`, subclass `SandboxBackendProtocol` (adds `id` property and `execute(command, *, timeout=None) -> ExecuteResponse`) or better `BaseSandbox` ([[sandboxes]]).

```python
from deepagents.backends.protocol import BackendProtocol, WriteResult, EditResult

class PolicyWrapper(BackendProtocol):
    def __init__(self, inner: BackendProtocol, deny_prefixes: list[str]):
        self.inner, self.deny = inner, [p.rstrip("/") + "/" for p in deny_prefixes]
    def ls(self, path): return self.inner.ls(path)
    def read(self, file_path, offset=0, limit=2000): return self.inner.read(file_path, offset, limit)
    def grep(self, pattern, path=None, glob=None, *, max_count=None):
        return self.inner.grep(pattern, path, glob, max_count=max_count)
    def glob(self, pattern, path=None): return self.inner.glob(pattern, path)
    def write(self, file_path, content):
        if any(file_path.startswith(p) for p in self.deny):
            return WriteResult(error=f"Writes are not allowed under {file_path}")
        return self.inner.write(file_path, content)
    def edit(self, file_path, old_string, new_string, replace_all=False):
        if any(file_path.startswith(p) for p in self.deny):
            return EditResult(error=f"Edits are not allowed under {file_path}")
        return self.inner.edit(file_path, old_string, new_string, replace_all)
```

Prefer declarative [[permissions]] for path allow/deny; use wrappers for audit logging, rate limits, content inspection. Community backends: Azure Blob (`langchain-azure-storage`), MongoDB VFS (`langchain-mongodb-deepagents-vfs`).

## Offload binary content (0.7.21+)

`FilesystemMiddleware(offload_binary_content=True)` keeps binary `read_file` results and inline `HumanMessage` media out of message history. Payloads go to `<artifacts_root>/blobs/<sha256>` on the backend, state keeps a content-addressed reference, and each model request is rehydrated from the backend. Off by default.

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.middleware import FilesystemMiddleware

backend = CompositeBackend(
    default=StateBackend(),
    routes={"/blobs/": FilesystemBackend(root_dir="/abs/blob-store", virtual_mode=True)},
)
agent = create_deep_agent(
    model="anthropic:claude-sonnet-5",
    backend=backend,
    middleware=[FilesystemMiddleware(backend=backend, offload_binary_content=True)],  # replaces the default by name
)
```

- If `blobs/` routes to a `StateBackend` (directly or through a `CompositeBackend`), the constructor warns and turns offloading off: state is checkpointed anyway.
- The blob root follows the `CompositeBackend`'s `artifacts_root`. The docs say "set `artifacts_root` on the middleware"; `FilesystemMiddleware` has no such argument. Code wins.
- The original input still sits in earlier checkpoints. Keep the blob store available when resuming a thread; a missing blob becomes a "no longer available, re-read the file" note.
- Your `FilesystemMiddleware` replaces the default one by name, so `create_deep_agent(permissions=...)` does not reach it (permissions travel through the private `_permissions` argument). Don't combine the two without checking.

## Choosing

- Web server / multi-tenant: `StateBackend` default + `StoreBackend` routes with per-user namespace, or a sandbox. Never `FilesystemBackend`/`LocalShellBackend`. See [[production]], [[persistence]].
- Local coding CLI: `CompositeBackend(default=StateBackend(), routes={"/workspace/": FilesystemBackend(..., virtual_mode=True)})`, or `LocalShellBackend` with [[human-in-the-loop]] (this is roughly what [[dcode]] does).
- Durable repo docs the agent reads: see [[openwiki]].

## Gotchas

- Docs say `FilesystemBackend` defaults to `virtual_mode=False`; code (0.7.29) defaults to `virtual_mode=True` for both `FilesystemBackend` and `LocalShellBackend`. Code wins; still pass it explicitly.
- Docs say factories (`backend=lambda rt: StateBackend(rt)`) still work with a deprecation warning; code raises `TypeError` (factories removed in 0.7) and `StateBackend.__init__` takes no args.
- Docs say omitting `StoreBackend(namespace=...)` falls back to `assistant_id`; code makes `namespace` a required keyword argument.
- Docs protocol reference says `write` is create-only and mentions `files_update`; code: every built-in `write` overwrites, and `WriteResult`/`EditResult` have no `files_update` field.
- `FilesystemBackend` alone writes `/large_tool_results/...` and `/conversation_history/...` onto real disk under `root_dir`. Use a `CompositeBackend` with a `StateBackend` default.
- `StateBackend` methods called outside a graph run raise `RuntimeError`; seed files via the `files` input key.
- `LocalShellBackend` with no `env` gives an empty environment: commands like `python` fail with "not found".
- Store namespace components reject `/`, spaces, `*`; email-like ids with `@`/`.` are fine.
- A custom `glob` returning relative paths silently bypasses [[permissions]] deny rules.
- On `StateBackend`/`StoreBackend`, `edit_file` on an uploaded image or PDF fails with `Cannot edit binary files with text replacements.` (0.7.29). Overwrite it with `write_file` or upload a new file.

## Sources

- `../sources/docs/oss/python/deepagents/backends.md`
- `../sources/docs/oss/python/integrations/backends/index.md`
- `../sources/package/deepagents/backends/__init__.py`
- `../sources/package/deepagents/backends/protocol.py`
- `../sources/package/deepagents/backends/state.py`
- `../sources/package/deepagents/backends/store.py`
- `../sources/package/deepagents/backends/filesystem.py`
- `../sources/package/deepagents/backends/local_shell.py`
- `../sources/package/deepagents/backends/composite.py`
- `../sources/package/deepagents/backends/context_hub.py`
- `../sources/package/deepagents/middleware/filesystem.py`
- `../sources/package/deepagents/middleware/_blob_offload.py`

## See also

- [[index]]
- [[filesystem-tools]]
- [[permissions]]
- [[sandboxes]]
- [[create-deep-agent]]
- [[memory]]
- [[persistence]]
- [[production]]
- [[human-in-the-loop]]
- [[subagents]]
- [[summarization]]
- [[context-engineering]]
- [[openwiki]]
- [[versions]]
- [[dcode]]
