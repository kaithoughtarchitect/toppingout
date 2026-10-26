---
title: Anti — wrong mental models and stale doc examples
id: anti
type: rule
status: code
product: all
keywords: anti-patterns, wrong mental model, stale docs, doesn't work, TypeError, StoreBackend namespace, backend lambda, write_todos missing, virtual_mode, task args, pre-0.7 docs, common mistakes, breaking changes
read_when: Read when a doc example raises an error or an answer feels off, before recommending any 0.7 API from memory.
updated: 2026-10-21
---

# Anti — wrong mental models and stale doc examples

If an answer does one of these, it has gone wrong. Most come from pre-0.7 docs, the README, or training memory. Checked against 0.7.29 source; code wins.

## Things the docs still show that break in 0.7.29

| Doc shows | Reality | Page |
|---|---|---|
| `backend=lambda rt: CompositeBackend(default=StateBackend(rt), …)` | `TypeError` — factories removed; `StateBackend()` takes no args | [[backends]] |
| `StoreBackend()` with no args, namespace falls back to `assistant_id` | `namespace=` is keyword-required | [[backends]] |
| Seeding `store.put(ns, "/memories/AGENTS.md", …)` | Agent reads key `/AGENTS.md` (route prefix stripped) → seed never found | [[memory]] |
| `FilesystemBackend` `virtual_mode=False` default | Default is `True` (also `LocalShellBackend`) | [[backends]] |
| Prompts that say "use write_todos" with no `TodoListMiddleware` | The tool does not exist | [[planning]] |
| `task(name=…, task=…)` | Args are `description`, `subagent_type` | [[subagents]] |
| `create_deep_agent(model_provider=…, temperature=…)` | No such params — configure via `init_chat_model` | [[models]] |
| "`execute` returns an error on non-sandbox backends" | It is removed from the tool list | [[filesystem-tools]] |
| Prompt order: memory then skills | Your prompt, then your middleware's text, then the skills index, then memory (Skills sits after your middleware since 0.7.29) | [[middleware]] |
| `LangSmithSandbox.create()` | Does not exist; wrap an existing sandbox | [[sandboxes]] |
| Blob offload: "set `artifacts_root` on the middleware" | `FilesystemMiddleware` has no such argument; the `blobs/` root follows `CompositeBackend(artifacts_root=...)` | [[backends]] |
| Content-builder pin `deepagents>=0.3.5,<0.4.0` | Stale | [[tutorials]] |
| `deepagents deploy`, `deepagents.toml`, `agent.json` (upstream `examples/deploy-*`) | **Deprecated.** They come from `deepagents-cli` (last release 0.3.0, 2026-08-24; PyPI: "DEPRECATED … Use Managed Deep Agents"). Use `mda` ([[managed]]) or self-host ([[production]]). Checked 2026-09-30 | [[managed]] |

## Wrong mental models

- **"It remembers across restarts."** Only with a durable checkpointer and store. `InMemorySaver` / `InMemoryStore` / nothing = gone — [[persistence]].
- **"Memory edits apply immediately."** `memory=` loads once per thread; setting `memory_contents=None` shows `(No memory loaded)` — [[memory]].
- **"Subagents get my middleware / memory / system prompt."** They don't; only `mode="fork"` gets memory; GP subagent inherits skills, custom ones don't — [[subagents]], [[middleware]].
- **"Omit `tools` on a subagent → it gets none."** It gets all parent custom tools; `"tools": []` for none — [[subagents]].
- **"Permissions sandbox the agent."** File tools only; not `execute`, custom or MCP tools — [[permissions]].
- **"`read_file` reads 2000 lines."** Tool default 100 — [[filesystem-tools]].
- **"`grep` takes a regex."** Literal substring, 1000-match cap — [[filesystem-tools]].
- **"`execute` status success = exit 0."** Check `artifact["exit_code"]` — [[sandboxes]].
- **"`LocalShellBackend` inherits my env."** Empty env, no `PATH` — [[sandboxes]].
- **"`skills=` points at a skill folder."** Point at its parent; otherwise zero skills load silently — [[skills]].
- **"My middleware sees the skills."** Since 0.7.29 `SkillsMiddleware` runs after your middleware and profile extras, so your `before_model` / `wrap_model_call` doesn't see freshly loaded `skills_metadata` or the skills prompt section. Replace `SkillsMiddleware` by name instead. See [[middleware]], [[skills]].
- **"`include_tools: [a, b]` works."** It must be a space-separated string; a YAML list matches no tool. See [[skills]].
- **"Swap in my own `SummarizationMiddleware()`." Loses model-aware defaults (trigger `None`) — [[summarization]].
- **"A replacement `FilesystemMiddleware` keeps my `backend=` / `permissions=`."** Overrides replace, not merge — [[middleware]].
- **"`interrupt_on={'task': True}` gates all delegation."** Interpreter `task()` bypasses it; gate `eval` — [[dynamic-subagents]].
- **"Stream shows subagents."** Only with `subgraphs=True` — [[streaming]].
- **"Use `langchain-mcp-adapters`."** Docs now use `langchain.mcp.MCPAdapter` — [[mcp]].
- **"Model name without provider is fine."** Works, but no harness profile applies — [[models]].
- **"Sync `invoke` with a URL-less `AsyncSubAgent`."** ASGI transport needs `ainvoke`/`astream` — [[async-subagents]].
- **"Rubric `model` is optional."** Required keyword — [[rubric]].
- **Namespace ids with spaces or `/`.** `ValueError`; allowed `^[A-Za-z0-9\-_.@+:~]+$` — [[backends]].

## Symptom → cause (debugging)

| Symptom | Check first, in order | Page |
|---|---|---|
| Memory **and** conversation gone after restart | 1. `InMemorySaver` / `InMemoryStore` or none at all. 2. A new `thread_id` each launch (persist it per workspace). 3. Relative SQLite path + a different cwd means empty DBs. | [[persistence]] |
| Preference gone after restart, chat still there | 1. The agent never wrote it (`store.get(ns, "/AGENTS.md")`, not the model's words). 2. It wrote outside `/memories/`, i.e. to per-thread state. 3. The namespace changed (unstable `workspace_id`, `context=` not passed). | [[memory]] |
| Memory-tab edit ignored in the same chat | `memory=` frozen per thread. Use `FreshMemory`, a new thread, or a `read_file` nudge. | [[agent-setup]] |
| UI shows empty memory, agent sees it | UI reads `/memories/x.md`; the key is `/x.md` (prefix stripped). Or the UI namespace differs. | [[agent-setup]] |
| `(No memory loaded)` in the prompt | File missing at that key, or seeded with the prefixed key | [[memory]] |
| `TypeError` at build: backend factories removed | `backend=lambda rt: …` or `StateBackend(rt)`. Pass instances. | [[backends]] |
| `ValueError: Namespace component … disallowed characters` | A display name (spaces) used as an id. Slugify. | [[agent-setup]] |
| `NotImplementedError` at build with `permissions=` | Execute-capable backend with non-route-scoped permission paths | [[permissions]] |
| `permission denied for write on /memories/...` | A blanket `deny write /**` without `allow /memories/**` before it | [[agent-setup]] |
| Model never plans / "write_todos not found" | No `TodoListMiddleware()` | [[planning]] |
| Subagent ignores retries/limits | Middleware isn't inherited; add it to the subagent spec | [[subagents]] |
| Stream dies with the tool's exception; Trace shows nothing | Raising tools kill the stream; add a `wrap_tool_call` catcher | [[streaming]] |
| `psycopg.InterfaceError: … cannot use the 'ProactorEventLoop'` | Windows + async Postgres: set `WindowsSelectorEventLoopPolicy` | [[persistence]] |
| `NotImplementedError: The SqliteSaver does not support async` | Sync saver used with `ainvoke`; use `AsyncSqliteSaver` | [[persistence]] |
| Fake model: `NotImplementedError` in `bind_tools` / `StopIteration` | Subclass to return `self`; script one item per model call | [[testing]] |
| `edit_file` on an image or PDF: `Cannot edit binary files with text replacements.` | Binary (base64) file in State/Store backend (0.7.29). Overwrite it or upload a new file | [[backends]] |
| `permission denied ... (resolves to X)` or `Error: cannot resolve <path>` | A symlink target is denied, or the path loops or escapes the root (0.7.25, `FilesystemBackend`) | [[permissions]] |
| Sandbox `grep` finds nothing under `.git` | `BaseSandbox.grep_exclude_dirs` defaults to `(".git",)` (0.7.25) | [[sandboxes]] |
| `InvalidUpdateError` after parallel `task` calls | Subagents changed the same custom state key, which has no reducer | [[subagents]] |
| `permissions=` silently not applied | A custom `FilesystemMiddleware` replaced the default; it doesn't receive `create_deep_agent(permissions=...)` | [[backends]] |
| Main agent sees unexpected user-role messages | Async subagent task notifications (`additional_kwargs["deepagents_notification"]`, 0.7.27); they only arrive on the async path | [[async-subagents]] |
| Model string works but profile behaviour is missing | No `provider:` prefix, or a model instance was passed | [[models]] |

## Deep Agents Code

- `OPENAI_API_KEY=… dcode` does not beat a key stored via `/auth`; `DEEPAGENTS_CODE_`-prefixed does — [[dcode-config]].
- Subagent `AGENTS.md` frontmatter honours only `name`, `description`, `model` — [[dcode-extending]].

## Managed Deep Agents

- Passing `system_prompt`, `skills`, `memory`, `backend`, `store`, `checkpointer` to `define_deep_agent`: `mda build` passes, `mda dev` fails — [[managed-project]].
- Schedules fire under `mda dev` since 0.9.3 (`--no-schedules` turns them off); the local-development page still says they never do. See [[managed-channels]].
- Memory `allow` example reading `context.channel.get("raw_event")`: since 0.9.0 channel runs get `context = None`; use `runtime.channel`. See [[managed-capabilities]].
- Agent memory is shared by every caller: a prompt-injection path, not private storage — [[managed-capabilities]].

## See also

- [[index]]
- [[constitution]]
