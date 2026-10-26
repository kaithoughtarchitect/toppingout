---
title: Filesystem tools (ls, read_file, write_file, edit_file, delete, glob, grep, execute)
id: filesystem-tools
type: reference
status: code
product: sdk
keywords: filesystem tools, file tools, grep_exclude_dirs, offload_binary_content, ls, read_file, write_file, edit_file, delete, glob, grep, execute, FilesystemMiddleware, tool_token_limit_before_evict, large_tool_results, grep regex, read file limit, tool eviction, big tool output
read_when: Read when the agent's file tools behave unexpectedly, grep regex finds nothing, read_file truncates, a large tool result is evicted, or execute is missing or reports success on failure.
updated: 2026-10-21
sources_hash: d9c3a1f83b45
---

# Filesystem tools (ls, read_file, write_file, edit_file, delete, glob, grep, execute)

The exact tools `FilesystemMiddleware` gives every deep agent, their arguments, output shapes and limits; read this before writing prompts, custom backends or tool-output assumptions.

## Quick reference

- Tools: `ls`, `read_file(file_path, offset=0, limit=100)`, `write_file`, `edit_file(..., replace_all=False)`, `delete`, `glob`, `grep`, `execute(command, timeout=None)`.
- `read_file` default window is 100 lines (not 2000); output has a `@@ lines ... @@` header then verbatim lines, no line numbers.
- `grep` is literal substring, never regex; `output_mode` is `files_with_matches` (default), `content` or `count`; cap `grep_max_count=1000`.
- `write_file` overwrites silently; `edit_file` needs exact unique `old_string` unless `replace_all=True`; read-before-edit is prompt text only.
- `execute` is hidden unless the backend (or Composite `default`) is a sandbox; `status` stays `success`, check `artifact["exit_code"]`.
- Tool results over `4 * tool_token_limit_before_evict` chars (80,000 default) go to `/large_tool_results/<tool_call_id>` with a head/tail preview.
- Eviction skips `ls, glob, grep, read_file, edit_file, write_file, delete`; latest HumanMessage over 200,000 chars is offloaded too.
- `**/*.ext` skips dot-directories; bare `*.ext` matches at any depth.
- `tools=[...]` without `"read_file"` raises `ValueError`; paths with `..`, leading `~` or drive letters are rejected.
- Sandbox `grep` skips `.git` by default (`BaseSandbox.grep_exclude_dirs`) and prefers `rg` when the sandbox has it.

## Where they come from

`create_deep_agent` always adds `FilesystemMiddleware(backend=backend, custom_tool_descriptions=<profile overrides>, _permissions=permissions)` to the main agent, the general-purpose subagent and each declarative subagent (see [[harness]], [[middleware]]). Tools act on the [[backends]] instance. Standalone use with `langchain.agents.create_agent`:

```python
from deepagents import FilesystemMiddleware  # also: deepagents.middleware.filesystem
FilesystemMiddleware(
    backend=None,                                  # -> StateBackend()
    system_prompt=None,                            # no built-in tool prose is added by default
    custom_tool_descriptions=None,                 # {"read_file": "...", ...}
    tool_token_limit_before_evict=20000,           # tokens (x4 chars); None disables eviction
    human_message_token_limit_before_evict=50000,
    max_execute_timeout=3600,                      # cap for per-call execute timeout
    grep_max_count=1000,                           # default match cap; None = unlimited
    tools=None,                                    # None/"all" or list[FsToolName]; must include "read_file"
    offload_binary_content=False,                  # 0.7.21+: keep binary payloads out of history (see backends)
)
```

`FsToolName = Literal["ls","read_file","write_file","edit_file","delete","glob","grep","execute"]` (exported from `deepagents`). Tools not in `tools=` are not created at all. Via `create_deep_agent`, hide tools with a `HarnessProfile(excluded_tools=frozenset({...}))` and rename/re-describe them with `tool_description_overrides` (see [[customization]]).

## Tool reference

All paths go through `validate_path`: normalized to leading `/`, forward slashes; `..` components, leading `~`, and Windows drive paths (`C:\...`) are rejected with `Error: ...`.

| Tool | Args (defaults) | Perm op | Result |
| - | - | - | - |
| `ls` | `path: str` | read | Newline list of entries (dirs end with `/`), denied paths filtered out. |
| `read_file` | `file_path: str`, `offset: int = 0`, `limit: int = 100` | read | Header + verbatim lines, or multimodal block. |
| `write_file` | `file_path: str`, `content: str` | write | `Updated file /x`. Creates or fully overwrites. |
| `edit_file` | `file_path`, `old_string`, `new_string`, `replace_all: bool = False` | write | `Successfully replaced N instance(s) of the string in '/x'`. |
| `delete` | `file_path: str` | write | `Deleted /x`. Recursive for directories. |
| `glob` | `pattern: str`, `path: str \| None = None` | read | Absolute file paths. |
| `grep` | `pattern`, `path=None`, `glob=None`, `output_mode="files_with_matches"`, `max_count: int \| None = None` (>0) | read | See below. |
| `execute` | `command: str`, `timeout: int \| None = None` | (none) | Output + `[Command succeeded/failed with exit code N]`. |

### read_file

- Default window is **100 lines** (tool schema); the backend protocol default of 2000 only applies to direct backend calls.
- Text output: optional notices, then a status header `@@ lines 1-100 of 350 | next offset 100 @@`, then the source lines **verbatim** (no line-number gutter in 0.7.29). The model must not copy the header into `edit_file`.
- Empty file returns `System reminder: File exists but has empty contents`. `limit <= 0` returns a distinct "no lines were read" reminder. Negative `offset` reads from line 1 with a notice.
- Size cap: if the page exceeds `4 * tool_token_limit_before_evict` chars (80,000 by default) it is truncated with a message suggesting e.g. `execute(command='jq . /file')`. `read_file` results are never evicted to a file.
- Images (`.png .jpg .jpeg .gif .webp`), audio, PDFs return multimodal content blocks (base64); `offset/limit` ignored. Video is supported when the `deepagents[video]` extra (`av`, `pillow`) is installed: `offset/limit` become seconds, frames sampled every 0.5 s. Any `encoding == "base64"` result is sent as a file block, never as text. See [[multimodal]].
- If the provider rejects the media, the middleware retries with the file content replaced by a notice.
- With `offload_binary_content=True`, binary results are stored as blobs on the backend and only a reference stays in history ([[backends]]).

### write_file / edit_file / delete

- `write_file` overwrites silently (description tells the model it need not read first).
- `edit_file` requires exact match; non-unique `old_string` without `replace_all=True` is an error; `new_string` must differ. The description says "You must read the file before editing; this tool errors otherwise" - that read-before-edit check is **not enforced** in the 0.7.29 middleware.
- `edit_file` on a binary file in `StateBackend`/`StoreBackend` returns `Error: Cannot edit binary files with text replacements.` (0.7.29).
- Two mutations (`write_file`/`edit_file`/`delete`) of the same path in one model response: the later ones return `Error: parallel file mutations to the same path are not allowed.`
- `delete` is hidden from the model when the backend does not override `BackendProtocol.delete`.

### glob

- Supports `*`, `**`, `?`, `[abc]`, `[!abc]`, `{a,b}`. A pattern without `/` matches the basename at any depth (`*.py` finds `src/app/main.py`); with `/` it matches the root-relative path; a leading `/` anchors to the search root.
- Dot names match only if the pattern segment starts with `.`; `**` does not descend into dot-dirs, so `*.yml` finds `.github/workflows/ci.yml` but `**/*.yml` does not.
- Timeout: 10 s at the middleware (`GLOB_TIMEOUT`), 5 s walk budget in `FilesystemBackend`, 5 s / 10,000 matches in sandbox scripts. Partial results come with a truncation note. At most 4 concurrent sync globs, then `Error: too many glob calls...`.
- With no `path`, permission is checked against `/`.

### grep

- **Literal** substring search, never regex (`"foo|bar"` searches that exact text). When `execute` is active the description tells the model to use `execute` with `rg '<regex>'` for regex.
- `glob` arg filters files (same rules as the glob tool; brace expansion not reliable on all backends).
- `output_mode`: `files_with_matches` (paths), `content` (grouped under `<path>:` header, `<line>: <text>`), `count` (`<path>: <n>`).
- Effective cap = `max_count` or `grep_max_count` (1000). On truncation a note says so. Backend sync grep timeout 15 s; async wrapper 35 s.
- `FilesystemBackend.grep` also has `context_lines`, but it is backend-only (not exposed to the model).
- The in-memory grep (`StateBackend`, `StoreBackend`) skips binary files (0.7.29).
- `BaseSandbox.grep` (0.7.25+) runs `rg` when it is installed in the sandbox and the search root is a directory, else GNU `grep`; patterns or globs that `rg` would read differently (newlines, `[`, `\`, `**`) stay on GNU `grep`. Directories named in the class attribute `grep_exclude_dirs` (default `(".git",)`) are skipped at any depth; subclass to add `node_modules` or set `()` to search everything. A search rooted at an excluded directory still searches it.

### execute

- Created always; **filtered out of the model request** unless the backend (or a `CompositeBackend`'s `default`) is a `SandboxBackendProtocol`. Called anyway, it returns an error.
- `timeout < 0` or `> max_execute_timeout` returns an error; a backend whose `execute` lacks a `timeout` kwarg rejects per-call timeouts.
- Output: combined stdout/stderr + `\n[Command succeeded with exit code 0]` / `failed with exit code N`, + `[Output was truncated due to size limits]` if the backend truncated. `ToolMessage.status` is `"success"` even for non-zero exit; `ToolMessage.artifact = {"exit_code": N}` (`ExecuteArtifact`) - use that to detect failure.
- Large output: for a `BaseSandbox` with `enable_capture_offload=True` (e.g. `LangSmithSandbox`), output over 80,000 chars is captured to `/large_tool_results/<id>` inside the sandbox and only a head/tail preview is returned (capture capped at 10 MiB). Otherwise generic eviction applies.
- Description steers the model away from shell `find`/`grep`/`cat` toward `glob`/`grep`/`read_file`.

## Large result eviction

- Any tool result (including `execute`, MCP and custom tools; see [[tools]]) whose text exceeds `4 * tool_token_limit_before_evict` chars (default 80,000) is written to `/large_tool_results/<sanitized tool_call_id>` (under `CompositeBackend.artifacts_root`) and replaced by a message with the path plus a head/tail preview. Excluded from eviction: `ls, glob, grep, read_file, edit_file, write_file, delete` (these self-truncate at ~80,000 chars).
- The latest `HumanMessage` over `4 * 50000` chars (200,000 by default) is saved to `/conversation_history/<uuid>.md` (under `artifacts_root`) and the model sees a preview (state keeps the full content). See [[context-engineering]], [[summarization]].

## Other behaviour

- No filesystem system prompt is injected unless you pass `system_prompt=`; the only automatic prompt addition is the host-path routing map for a `CompositeBackend` with a `LocalShellBackend` default.
- State schema adds `files` (with a delta channel) only when a `StateBackend` is present somewhere in the backend tree.
- [[permissions]] are checked before the backend call (for `FilesystemBackend`, on the symlink-resolved path too); denied results are also filtered from `ls/glob/grep` output. Interrupt-mode rules route through [[human-in-the-loop]].

## Gotchas

- Default `read_file` limit is 100 lines, not 2000.
- The "read before edit" rule is only prompt text.
- `grep` is literal; models trained on ripgrep often send regex and get zero matches.
- `**/*.ext` skips dot-directories; bare `*.ext` is broader.
- `execute` returns `status="success"` for failing commands; check `artifact["exit_code"]`.
- With `FilesystemBackend` alone, evicted results land on real disk under `root_dir/large_tool_results/`.
- `tools=[...]` without `"read_file"` raises `ValueError`.

## Sources

- `../sources/docs/oss/python/deepagents/backends.md`
- `../sources/docs/oss/python/deepagents/sandboxes.md`
- `../sources/package/deepagents/middleware/filesystem.py`
- `../sources/package/deepagents/middleware/_message_eviction.py`
- `../sources/package/deepagents/middleware/_blob_offload.py`
- `../sources/package/deepagents/middleware/_tool_exclusion.py`
- `../sources/package/deepagents/backends/protocol.py`
- `../sources/package/deepagents/backends/utils.py`
- `../sources/package/deepagents/backends/sandbox.py`
- `../sources/package/deepagents/graph.py`

## See also

- [[index]]
- [[backends]]
- [[permissions]]
- [[sandboxes]]
- [[middleware]]
- [[harness]]
- [[context-engineering]]
- [[summarization]]
- [[multimodal]]
- [[human-in-the-loop]]
- [[customization]]
- [[tools]]
