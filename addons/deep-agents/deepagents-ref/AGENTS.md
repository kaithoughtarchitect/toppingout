# Deep Agents reference

A reference for LangChain **Deep Agents**, checked against the real package code. Use it before you plan, while you build, and when you review. Version: `deepagents` **0.7.29** (Python SDK).

## Map

```
Layer 1: this folder (deepagents-ref/). Read first. Checked against 0.7.29 code. Wins every conflict.
  wiki/constitution.md     13 rules, read every time
  wiki/agent-setup.md         the full agent setup: model, backend, permissions, Memory tab, workspaces (run on 0.7.29)
  wiki/index.md            one line per page (SDK first, dcode/Managed optional)
  wiki/lookup.md           term, class, function or parameter -> page
  wiki/decisions.md        which piece to use
  wiki/anti.md             what breaks in 0.7.29 + symptom -> cause table for debugging
  wiki/gaps.md             what layer 1 doesn't cover -> go to layer 2
  wiki/<topic>.md          topic pages: Quick reference, Gotchas, Sources
  scripts/check_imports.py static check of your file against the vendored package (no install needed)
  sources/package/         deepagents 0.7.29 source (ground truth; open by explicit path)
  sources/docs/            raw Deep Agents docs (contain stale examples; open by explicit path)

Layer 2: LangChain docs server, MCP "docs-langchain" (registered in the repo-root .mcp.json)
  search_docs_by_lang_chain                 semantic search over ALL LangChain docs
  query_docs_filesystem_docs_by_lang_chain  rg / cat / head over every doc page (.mdx paths)
  Live and always the latest docs. Docs only: never checked against 0.7.29.
```

## Find it

1. Read `wiki/constitution.md` first, every time. It's one screen.
2. **your agent work: read `wiki/agent-setup.md`.** It's the checked setup to copy from.
3. Pick the page on `wiki/index.md`. SDK pages come first; `dcode-*` and `managed-*` pages are other products, so skip them for SDK code.
4. If you have a term, class, function or parameter name, search `wiki/lookup.md` for it.
5. If neither has it, check `wiki/gaps.md`, then use **layer 2**:
   - Search with `search_docs_by_lang_chain` and put **"python"** in the query, or you'll get JavaScript pages too.
   - Read the result with `query_docs_filesystem_docs_by_lang_chain`, command `head -200 /<path>.mdx`, using **exactly** the path the search returned. Guessed paths fail silently. `rg -il "term" /oss/python` finds pages by keyword.
   - Label the answer "LangChain docs, not checked against 0.7.29". If it contradicts layer 1, layer 1 wins. Layer-2 examples can still be wrong for Deep Agents (e.g. the fake-model example in `wiki/testing.md`).
6. If neither layer has it, **say so. Don't answer from memory.**
7. Only open `sources/` by explicit path, from a page's `## Sources`. Default searches skip it (`.ignore`).

## Before you plan

Read the constitution, then `wiki/agent-setup.md` (for agent work), then `wiki/decisions.md`, then `wiki/anti.md`, then the topic page.

## While you build

Read the topic page's `## Quick reference` and `## Gotchas` before writing code. Quote the gotcha that applies. Tests: `wiki/testing.md`.

## When you debug

Start at the **Symptom → cause** table in `wiki/anti.md`. Check the store and the tool messages, not the model's words.

## After you write code: verify (mandatory)

1. Run `python deepagents-ref/scripts/check_imports.py <your files>`. It flags nonexistent `deepagents` imports, bad keyword arguments, backend factories and other 0.7 breakers. Fix every error, and justify every warning.
2. Version: `pip show deepagents`. If it isn't installed, the reference version is in `sources/package/deepagents/_version.py` (0.7.29); say the code is unverified against an install. If the installed version differs, say so before trusting any detail.
3. Go through the review checklist below.

## Review checklist

- [ ] `check_imports.py` passes.
- [ ] Backends are instances. `backend=lambda rt: …` or `StateBackend(rt)` raises `TypeError`.
- [ ] The default backend isn't `LocalShellBackend` or `FilesystemBackend` (real shell/disk) unless you mean it.
- [ ] Anything that must survive a restart uses a durable checkpointer **and** a durable store (`Async*` classes with `ainvoke`).
- [ ] UI, seed or migration code uses the store key without the route prefix (`/memories/AGENTS.md` is stored as `/AGENTS.md`).
- [ ] Nothing expects a memory edit to show up in the prompt mid-thread (unless `FreshMemory` is used).
- [ ] Namespace ids are slugs, not display names: parts match `^[A-Za-z0-9\-_.@+:~]+$`.
- [ ] A write deny on `/**` comes **after** an allow on `/memories/**`, or memory writes fail.
- [ ] `permissions=` isn't relied on as a sandbox. It covers file tools only.
- [ ] `write_todos` is only expected if `TodoListMiddleware()` was added.
- [ ] Every middleware class used is imported (`ModelRetryMiddleware`, `TodoListMiddleware` come from `langchain.agents.middleware`).
- [ ] Each subagent gets its own middleware, retries and limits.
- [ ] Tools that can raise are covered by a `wrap_tool_call` catcher, or a failure kills the stream (`wiki/streaming.md`).
- [ ] HITL has a checkpointer and a stable `thread_id`. Each thread is bound to one workspace.
- [ ] Models are given as `provider:model` strings (agent: `openrouter:openai/gpt-6-luna`).

## Rules

- **Never invent an API.** Cite the wiki page or source path behind each claim.
- **The code beats the docs.** Where they disagree, `sources/package/` is right.
- **Name the product:** SDK, `dcode` or Managed.

The four mistakes that cost the most: backend factories, assuming persistence, route-prefixed store keys, and expecting memory to reload mid-thread (constitution rules 1–4).

Updating this folder: see `MAINTAINING.md`.
