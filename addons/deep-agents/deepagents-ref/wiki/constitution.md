---
title: Constitution (one screen)
id: constitution
type: rule
status: code
product: sdk
keywords: rules, must know, mental model, core rules, gotchas, deepagents basics
read_when: Read first, every time — before planning, building or reviewing anything that uses deepagents.
updated: 2026-10-21
---

# Constitution (one screen)

**Mental model:** `create_deep_agent` returns a compiled LangGraph graph built by LangChain's `create_agent` plus a fixed middleware stack ([[create-deep-agent]], [[middleware]]). Everything the harness does is middleware. Rules are ordered by the cost of getting them wrong. All checked against 0.7.29 source ([[versions]]).

1. **Backends are instances, never factories.** `backend=lambda rt: …` and `StateBackend(rt)` raise `TypeError` in 0.7. `StoreBackend(namespace=…)` is keyword-required; the namespace *callable* is fine. File tools see virtual POSIX paths — [[backends]].
2. **Nothing persists by default.** No checkpointer, no store. `StateBackend` files live in the checkpoint → one thread only. Cross-thread memory = `CompositeBackend` route → `StoreBackend` **and** a durable store. In-memory savers die with the process. Prove restarts — [[persistence]].
3. **`CompositeBackend` strips the route prefix.** `/memories/AGENTS.md` is store key `/AGENTS.md`. Any UI or seed code must use the stripped key — [[memory]].
4. **`memory=` loads once per thread, then freezes in state.** Edits reach the prompt on a new thread; no reload knob — [[memory]].
5. **Planning is opt-in since 0.7.0.** No `write_todos` unless you add `TodoListMiddleware()` (Codex profiles excepted). README and tutorials still say otherwise — [[planning]].
6. **Subagents are isolated.** One `ToolMessage` comes back. Declarative subagents inherit model, tools, permissions, `interrupt_on` — not system prompt, middleware, or memory. Repeat retries/limits per subagent — [[subagents]].
7. **Permissions guard file tools only.** First match wins, default allow; on `FilesystemBackend` the symlink target is checked too. Not `execute`, custom or MCP tools; with an execute-capable backend they raise `NotImplementedError` unless route-scoped — [[permissions]].
8. **HITL needs a checkpointer and the same `thread_id`.** Resume with `Command(resume={"decisions": […]})` — [[human-in-the-loop]].
9. **`tools=` only adds.** Hide built-ins with `HarnessProfile(excluded_tools=…)` or a `FilesystemMiddleware(tools=[…])` allowlist. Middleware with a built-in's `.name` replaces it in place — [[tools]], [[middleware]].
10. **Use `provider:model` strings.** Harness profiles key on the string; instances skip provider profiles — [[models]].
11. **The default system prompt is empty.** Final prompt = your `system_prompt` + profile base + suffix; tool guidance lives in tool schemas — [[customization]].
12. **Context is managed, not lost.** Summarization at 85% of `max_input_tokens` (fallback 170k); evicted turns → `/conversation_history/`; tool results over 20 000 tokens (≈80 000 chars) → `/large_tool_results/` — [[summarization]], [[filesystem-tools]].
13. **Three products share the name.** SDK `deepagents` · Deep Agents Code `dcode` · Managed `mda`. Say which — [[products]].

Before recommending: [[decisions]]. Before trusting a doc example: [[anti]]. Not in this folder: [[gaps]].
