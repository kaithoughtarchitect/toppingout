---
title: Decisions — which piece to reach for
id: decisions
type: decision
status: code
product: all
keywords: decision, which to use, choose, SDK vs dcode vs managed, StateBackend vs StoreBackend, sandbox vs interpreter, subagent vs skill, tradeoff, recommendation, default choice, when to use
read_when: Read when choosing between products, backends, subagent kinds or memory options before recommending a design.
updated: 2026-09-29
---

# Decisions — which piece to reach for

Yes/no tests before recommending a design. Each row names the default and when to leave it.

## Product

| Need | Reach for |
|---|---|
| Embed an agent in your own Python app, own the runtime | SDK `create_deep_agent` — [[products]] |
| LangSmith hosts it, deploy from a folder of files | Managed Deep Agents — [[managed]] |
| A coding agent in your terminal | Deep Agents Code — [[dcode]] |
| A fixed, simple tool loop with no files/subagents | plain LangChain `create_agent` — [[products]] |

## Files and state

| Question | Answer |
|---|---|
| Scratch files for one conversation? | Default `StateBackend` — [[backends]] |
| Files that outlive the thread (memory, notes)? | `CompositeBackend` route (e.g. `/memories/`) → `StoreBackend(namespace=…)` + durable store — [[memory]] |
| Agent edits real files on disk? | `FilesystemBackend(root_dir=…)` (virtual_mode on) — local/dev only, never deployed — [[backends]] |
| Must run code / shell? | Sandbox backend; `LocalShellBackend` only for trusted local dev — [[sandboxes]] |
| Light computation / orchestrating tools from code, no shell? | Interpreter (QuickJS `eval`) — [[interpreters]] |
| Survive a process restart? | Durable checkpointer (Sqlite/Postgres) **and** durable store; demonstrate it — [[persistence]] |
| Per-user / per-tenant isolation? | Namespace from `rt.context` (not `server_info` when self-hosting) — [[backends]] |
| Restrict paths the agent can touch? | `permissions=` (file tools only) or don't mount it — [[permissions]] |

## Instructions and knowledge

| Question | Answer |
|---|---|
| Always-on instructions / learned preferences? | `memory=` AGENTS.md files — [[memory]] |
| Procedures needed only sometimes? | `skills=` (progressive disclosure) — [[skills]] |
| Large corpus? | Retrieval tool + offload chunks to files + delegate — [[retrieval]] |
| External API? | Custom `@tool` first; MCP when the server already exists — [[tools]], [[mcp]] |

## Work shape

| Question | Answer |
|---|---|
| Multi-step task that benefits from a visible plan? | Add `TodoListMiddleware()` — [[planning]] |
| Isolate a context-heavy subtask? | Declarative subagent via `task` — [[subagents]] |
| Fan out N similar subtasks from code? | Dynamic subagents in the interpreter — [[dynamic-subagents]] |
| Long-running background work while chatting? | Async subagents on an Agent Protocol server — [[async-subagents]] |
| Iterate until a quality bar is met? | `RubricMiddleware` (needs a deterministic-ish rubric) — [[rubric]] |
| Human approves sensitive actions? | `interrupt_on` + checkpointer — [[human-in-the-loop]] |
| Going live? | [[production]] checklist |

## Worked case: your agent

The full checked setup (model, backend, the allow-then-deny permissions, the Memory tab service, workspaces and threads, the leakage test plan) is on [[agent-setup]]. Edit history for memory: [[memory-history]]. Tests: [[testing]].

## See also

- [[index]]
- [[constitution]]
