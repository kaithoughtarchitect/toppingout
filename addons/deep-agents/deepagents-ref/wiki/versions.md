---
title: Versions, dependencies and public API map
id: versions
type: reference
status: code
product: sdk
keywords: deepagents version, changelog, breaking changes, 0.7.0, upgrade, migration, dependencies, extras, public API, __all__, deprecated, BASE_AGENT_PROMPT, virtual_mode, write_file overwrite, TodoListMiddleware removed, what changed
read_when: Read when upgrading deepagents, code behaves differently after 0.7.x, or you need to know which module exports a class or what a dependency is.
updated: 2026-10-21
sources_hash: 088d151edb83
---

# Versions, dependencies and public API map

This repo targets `deepagents==0.7.29` (released 2026-10-20; `deepagents.__version__ == "0.7.29"`). Upgraded from 0.7.19 on 2026-09-30, then from 0.7.20 on 2026-10-21. Use this page to check what changed between versions, which deps you get, and where each public class lives.

## Quick reference

- Target is `deepagents==0.7.29` (2026-10-20); Python `>=3.11,<4.0`.
- **0.7.20** (2026-09-29): one fix: `StateBackend.upload_files` now tags binary content `base64` (it was stored as base64 but tagged `utf-8`). Code diff vs 0.7.19: only `backends/state.py` and `_version.py`. Minimum versions raised: `langchain>=1.4.3`, `langchain-core>=1.6.6`, `langchain-anthropic>=1.7.5`, `langsmith>=0.14.1`, quickjs extra `>=0.3.8`.
- **0.7.21 to 0.7.29** (2026-09-30 to 2026-10-20): `SkillsMiddleware` moved to the tail of the stack, skill tools (`metadata.include_tools`, `SkillsMiddleware(tools=...)`) and `pinned_skills`, async subagents gained `mode="fork"`, a `waiting` status and push notifications to the parent (`TaskEvent`, `_ParentNotifierMiddleware`), permissions also check symlink targets on `FilesystemBackend`, `edit_file` refuses binary files, `SummarizationMiddleware(summarizer=...)`, `FilesystemMiddleware(offload_binary_content=...)`. Details in the 0.7.20 to 0.7.29 table below. Minimum versions raised: `langchain>=1.4.6`, `langchain-core>=1.6.12`, `langchain-anthropic>=1.7.6`, `langchain-google-genai>=4.4.2`, `langsmith>=0.14.11`, aws extra `langchain-aws>=1.9.0`, quickjs extra `>=0.3.9`.
- Extras: `aws` (Bedrock caching), `quickjs` (`CodeInterpreterMiddleware`), `video` (frames in `read_file`); `langchain-openai` is not included.
- 0.7.0 removed `TodoListMiddleware` from defaults; restore with `middleware=[TodoListMiddleware()]`.
- 0.7.0 lean prompts: empty base prompt; `BASE_AGENT_PROMPT` deprecated (removal 0.9.0).
- 0.7.0: `FilesystemBackend`/`LocalShellBackend` default `virtual_mode=True`; `StoreBackend` needs explicit `namespace`; backends must be instances.
- 0.7.0: `write_file` overwrites existing files; new recursive `delete` tool.
- 0.7.0: `SummarizationMiddleware(history_path_prefix=...)` raises `TypeError`; use `CompositeBackend(artifacts_root=...)`.
- 0.7.9: `excluded_tools` also blocks execution; 0.7.13: subagent mode `handoff` renamed `isolated`.
- Pending removals: `model=None` (1.0.0), `BASE_AGENT_PROMPT` (0.9.0).
- `deepagents.profiles` is beta and may change in minor releases.

## Package metadata (0.7.29)

- License MIT; "Development Status :: 4 - Beta"; Python `>=3.11,<4.0` (3.11 to 3.14).
- Required: `langchain>=1.4.6,<2`, `langchain-core>=1.6.12,<2`, `langchain-anthropic>=1.7.6,<2`, `langchain-google-genai>=4.4.2,<5`, `langsmith>=0.14.11`, `packaging>=23.2`, `wcmatch>=11.0`. (LangGraph comes transitively via `langchain`.)
- Extras: `aws` -> `langchain-aws>=1.9.0,<2` (Bedrock prompt caching); `quickjs` -> `langchain-quickjs>=0.3.9` (`CodeInterpreterMiddleware`); `video` -> `av>=18,<19`, `pillow>=12.3,<13` (video frames in `read_file`).
- Not included: `langchain-openai`, `langchain-openrouter` (need `>=0.2.0`), `langchain-fireworks`, sandbox partner packages.
- Traces carry metadata `lc_versions.deepagents` (`"0.7.29"`, or `"0.7.29+editable"` for editable installs).

## Breaking changes in 0.7.0 (2026-07-29)

1. `TodoListMiddleware` removed from defaults: no `write_todos`, `todos` channel, or planning prompt. Restore with `middleware=[TodoListMiddleware()]` (and in each `SubAgent`'s `middleware`) ([[planning]]).
2. Lean prompts: authored base prompt is empty; tool prose trimmed. `BASE_AGENT_PROMPT` deprecated (removal 0.9.0) but importable from `deepagents.graph`; `create_deep_agent(system_prompt=BASE_AGENT_PROMPT)` restores it.
3. Removed constants `TASK_SYSTEM_PROMPT`, `ASYNC_TASK_SYSTEM_PROMPT`, `SUMMARIZATION_SYSTEM_PROMPT`, `FILESYSTEM_SYSTEM_PROMPT`, `EXECUTION_SYSTEM_PROMPT`; `system_prompt` default is `None` on `SubAgentMiddleware`, `AsyncSubAgentMiddleware`, `SummarizationToolMiddleware`, `create_summarization_tool_middleware`.
4. `FilesystemBackend` / `LocalShellBackend` default `virtual_mode=True` (paths anchored under `root_dir`, `..` rejected) ([[backends]]).
5. New recursive `delete` tool whenever backend supports it; permissions treat `delete` as a write ([[permissions]]).
6. `write_file` overwrites existing files (no file-exists error, no read-first requirement).
7. Removed backend shims: backends must be instances (not factories); `StoreBackend` needs explicit `namespace`; removed `ls_info`/`als_info`/`glob_info`/`aglob_info`/`grep_raw`/`agrep_raw`; removed `files_update` from `WriteResult`/`EditResult`.
8. `SummarizationMiddleware(history_path_prefix=...)` raises `TypeError`; use `CompositeBackend(artifacts_root=...)`.
9. Tool output: empty `ls`/`glob` render `No files found`; `read_file` no longer uses `cat -n` gutter; `LINE_NUMBER_WIDTH` removed.

0.7.0 features: middleware override by `.name`; `FilesystemMiddleware(tools=[...])` allowlist + exported `FsToolName`; `grep_max_count` (default 1000) and per-call `max_count`; paginated `read_file` metadata; `truncated` flag on `GrepResult`/`GlobResult`; Fireworks prompt-cache affinity; Nemotron 3 Ultra profile; `RubricMiddleware` accepts any positive `max_iterations`.

## Notable changes 0.7.1 to 0.7.19

| Version | Change |
| - | - |
| 0.7.2 | scrub multimodal blocks unsupported by the model profile |
| 0.7.4 | `execute` exit code exposed in artifacts |
| 0.7.6 | summarization offloads history under a distinct session ID |
| 0.7.8 | `files` state channel only added for state backends |
| 0.7.9 | `excluded_tools` also blocks execution, not just visibility; middleware tracing inputs disabled |
| 0.7.11 | rubric grader integration hooks ([[rubric]]) |
| 0.7.12 | subagent conversation forking (`mode="fork"`, experimental) ([[subagents]]) |
| 0.7.13 | subagent mode renamed `handoff` -> `isolated` |
| 0.7.14 | new `read_file` formatting; `edit_file` rejects empty `old_string` |
| 0.7.15 | colons allowed in model profile keys (e.g. `ollama:glm-5.2:cloud`) |
| 0.7.16 | skills reload when `skills_metadata` reset to `None`; parallel edits to the same file rejected |
| 0.7.18 | `task` rejects unknown argument keys; `FileInfo.size` is bytes; clearer truncation previews |
| 0.7.19 | recover when `read_file` media is rejected; unsupported multimodal filtering moved into `UnsupportedContentMiddleware`; bounded tool-offload paths |

## Changes 0.7.20 to 0.7.29

Code files changed between the 0.7.20 and 0.7.29 wheels: `graph.py`; `backends/composite.py`, `context_hub.py`, `filesystem.py`, `sandbox.py`, `state.py`, `store.py`, `utils.py`; `middleware/__init__.py`, `_fs_interrupt.py`, `_message_eviction.py`, `async_subagents.py`, `filesystem.py`, `rubric.py`, `skills.py`, `subagents.py`, `summarization.py`; new `middleware/_blob_offload.py`, `_parent_notifier.py`, `_skill_tools.py`.

| Version | Change |
| - | - |
| 0.7.21 | `FilesystemMiddleware(offload_binary_content=True)` keeps binary `read_file` results and inline media out of history: payloads go to `blobs/` under the artifacts root and are rehydrated per model call (no effect when `blobs/` routes to a `StateBackend`) |
| 0.7.22 | a skill's tools load only when the skill is read (`metadata.include_tools` + `SkillsMiddleware(tools=...)`, or a `SkillToolResolver`); overwriting a file resets a stale encoding to `utf-8` |
| 0.7.23 | `pinned_skills` state key: named skills' `SKILL.md` is appended as a `HumanMessage` before the next model call; each subagent gets its own `SkillsMiddleware` |
| 0.7.24 | async subagents accept `mode="fork"` (experimental); summary calls recover from context overflow; parallel `task` calls keep the parent's rubric |
| 0.7.25 | permission rules and permission-built interrupts check both the requested and the symlink-resolved path (`FilesystemBackend`, also behind `CompositeBackend`); sandbox `grep` prefers ripgrep and skips `.git` (`BaseSandbox.grep_exclude_dirs`) |
| 0.7.26 | async subagents report `waiting` (paused for a human); their runs nest under the parent's trace; `SummarizationMiddleware(summarizer=...)` |
| 0.7.27 | async subagent status updates reach the main agent as notification messages (`TaskEvent`, `_ParentNotifierMiddleware`, always in the main stack); subagent names are passed to subagents |
| 0.7.28 | `ContextHubBackend.glob` honors `path` |
| 0.7.29 | `CompositeBackend` routes without a trailing slash work; `edit_file` on a binary (base64) file errors; in-memory `grep` skips binary files |

Also in this range: `SkillsMiddleware` now sits after your middleware and profile extras, just before prompt caching, in the main agent, the general-purpose subagent and declarative subagents ([[middleware]]); a `SkillsMiddleware` you pass in `middleware=` replaces the default in place and supplies `skills` when `skills=` is unset; subagents no longer return state keys they did not change, and `rubric`, `pinned_skills` and `_skill_tools_disclosed` are never passed to or from them ([[subagents]]). New exports from `deepagents.middleware`: `SkillToolResolver`, `TaskEvent`.

## Earlier milestones

- 0.5.2: filesystem permissions; `StateBackend.upload_files`.
- 0.5.3: `model=None` deprecated (removal 1.0.0); structured output for subagents.
- 0.5.4: harness + provider profiles API (beta); built-ins for OpenAI Codex and Anthropic; `MemoryMiddleware` cache breakpoint.
- 0.5.7: OpenRouter ignores Azure upstream by default; GP subagent inherits parent permissions.
- 0.6.0: experimental `CodeInterpreterMiddleware` (QuickJS) ([[interpreters]]); `stream_events(version="v3")` ([[streaming]]).
- 0.6.2: `system_prompt` override slot on memory, skills, summarization.
- 0.6.5: `RubricMiddleware`. 0.6.6: `state_schema=` param. 0.6.7: `DeepAgentState` exported.
- 0.6.8: `mode="interrupt"` permissions; dropped public `SubagentRunStream`, `AsyncSubagentRunStream`, `SubagentTransformer`.
- 0.6.9: configurable subagent `response_format`.
- 0.6.12: Bedrock prompt caching (`deepagents[aws]`).

## Deprecations pending

- `model=None` / `get_default_model()` -> removal 1.0.0.
- `deepagents.graph.BASE_AGENT_PROMPT` -> removal 0.9.0.
- Legacy large-result preview templates (0.7.18) on a deprecation path.

## Public API map

Top-level `from deepagents import ...` (`__all__`): `create_deep_agent`, `DeepAgentState`, `SubAgent`, `CompiledSubAgent`, `SubAgentMiddleware`, `AsyncSubAgent`, `AsyncSubAgentMiddleware`, `FilesystemMiddleware`, `FilesystemPermission`, `FsToolName`, `MemoryMiddleware`, `RubricMiddleware`, `HarnessProfile`, `HarnessProfileConfig`, `GeneralPurposeSubagentProfile`, `register_harness_profile`, `ProviderProfile`, `register_provider_profile`, `__version__`.

| Module | Key symbols | Page |
| - | - | - |
| `deepagents.graph` | `create_deep_agent`, `DeepAgentState`, `get_default_model` (deprecated), `BASE_AGENT_PROMPT` (deprecated) | [[create-deep-agent]] |
| `deepagents.middleware` | `FilesystemMiddleware`, `SubAgentMiddleware`, `AsyncSubAgentMiddleware`, `TaskEvent`, `SkillsMiddleware`, `SkillToolResolver`, `MemoryMiddleware`, `SummarizationMiddleware`, `SummarizationToolMiddleware`, `create_summarization_tool_middleware`, `UnsupportedContentMiddleware`, `RubricMiddleware` (+ rubric types), `SkillMetadata`, `DEEPAGENTS_DEFAULT_SUMMARY_PROMPT` | [[middleware]] |
| `deepagents.middleware.summarization` | `create_summarization_middleware`, `compute_summarization_defaults`, `TruncateArgsSettings`, `TriggerClause` | [[summarization]] |
| `deepagents.middleware.patch_tool_calls` | `PatchToolCallsMiddleware` (not re-exported) | [[middleware]] |
| `deepagents.middleware.filesystem` | tool schemas (`ReadFileSchema`, `GrepSchema`, ...), `FilesystemState` | [[filesystem-tools]] |
| `deepagents.middleware.subagents` / `async_subagents` | `SubAgent`, `CompiledSubAgent`, `TaskToolSchema`, `AsyncTask`, async tool schemas | [[subagents]], [[async-subagents]] |
| `deepagents.middleware.skills` / `memory` | `SkillsState`, `MemoryState` | [[skills]], [[memory]] |
| `deepagents.backends` | `StateBackend`, `FilesystemBackend`, `LocalShellBackend`, `StoreBackend`, `CompositeBackend`, `ContextHubBackend`, `LangSmithSandbox`, `BackendProtocol`, `NamespaceFactory` | [[backends]] |
| `deepagents.backends.protocol` / `sandbox` | `SandboxBackendProtocol`, `BaseSandbox`, `ExecuteResponse`, result types (`ReadResult`, `WriteResult`, `EditResult`, `DeleteResult`, `LsResult`, `GrepResult`, `GlobResult`, `FileInfo`) | [[backends]] |
| `deepagents.backends.utils` | `create_file_data`, `file_data_to_string`, path helpers | [[backends]] |
| `deepagents.profiles` (beta) | profile classes, `apply_provider_profile`, `get_provider_profile` | [[models]] |
| `deepagents._models` | `resolve_model`, `get_model_identifier`, `get_model_provider`, `model_matches_spec`, `is_bedrock_model` | [[models]] |

Also documented in the reference: the Nemotron middleware classes (`NemotronToolCallShim`, `FinalAnswerGuardMiddleware`, ...) and video helpers (`extract_video_frames`, `VideoExtractionError`) ([[multimodal]]).

## Gotchas

- Code written for <0.7 that relied on `write_todos`, the base prompt, `write_file` refusing overwrites, or `virtual_mode=False` default silently changes behaviour on 0.7.x.
- README/METADATA quickstart uses `model="openai:gpt-6-astra"`; any tool-calling model works but check the provider package is installed (`langchain-openai` is not a dependency).
- `deepagents.profiles` is explicitly beta: minor changes possible in minor releases.
- The changelog's 0.5.4 note mentions Codex `apply_patch`/`shell_command` conventions; the Codex profile (unchanged through 0.7.29) only has a prompt suffix + `TodoListMiddleware`.

## Sources

- `../sources/package/deepagents-0.7.29.dist-info/METADATA`
- `../sources/docs/github/deepagents-CHANGELOG.md`
- `../sources/docs/oss/python/reference/deepagents-python.md`
- `../sources/package/deepagents/__init__.py`
- `../sources/package/deepagents/_version.py`
- `../sources/package/deepagents/middleware/__init__.py`
- `../sources/package/deepagents/backends/__init__.py`
- `../sources/package/deepagents/graph.py`

## See also

- [[index]]
- [[harness]]
- [[create-deep-agent]]
- [[middleware]]
- [[models]]
