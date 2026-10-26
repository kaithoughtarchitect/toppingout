---
title: Gaps — what this folder does not cover
id: gaps
type: reference
status: sourced
product: all
keywords: not found, missing, not covered, evals, integration test, token usage, cost tracking, tracing, observability, MCP auth, OAuth, checkpointer classes, PostgresSaver, SqliteSaver, TodoListMiddleware params, LangGraph, create_agent
read_when: Read when the index and lookup have no page for your question, before answering from memory.
updated: 2026-10-21
---

# Gaps — what this folder does not cover

If the answer is not in the wiki, `lookup.md`, or `../sources/`, it is not known in layer 1. **Go to layer 2**, the LangChain docs MCP server `docs-langchain` (see `../AGENTS.md`): `search_docs_by_lang_chain` with "python" in the query, then read the page with `query_docs_filesystem_docs_by_lang_chain`. The live URLs below are where each gap is covered. Label layer-2 answers "not checked against 0.7.29". Never fill a gap from memory. Checked by grep across `wiki/`, `sources/docs/`, and `sources/package/` on 2026-09-29.

| Topic | Status here | Live source |
|---|---|---|
| Integration tests against a real model, trajectory checks | Unit tests with fake models **are** covered: [[testing]] | https://docs.langchain.com/oss/python/langchain/test/integration-testing.md |
| Evals for a self-hosted SDK agent | Not covered (only Managed Harbor evals: [[managed-dev]]; grader loop: [[rubric]]) | https://docs.langchain.com/oss/python/langchain/test/evals.md |
| Token usage / cost tracking per run | Not covered in the SDK (only `dcode` `/cost`: [[dcode]]) | https://docs.langchain.com/oss/python/langchain/observability.md |
| Tracing / observability (LangSmith) setup | Mentioned only in passing ([[production]]) | https://docs.langchain.com/oss/python/langchain/observability.md · https://docs.langchain.com/oss/python/langgraph/observability.md |
| MCP authentication (bearer, OAuth, per-user), connection options | Not in Deep Agents docs ([[mcp]] covers loading tools only) | https://docs.langchain.com/oss/python/langchain/mcp/auth.md · https://docs.langchain.com/oss/python/langchain/mcp/connections.md |
| Durable checkpointer / store internals beyond setup | Imports, packages, async setup and gotchas **are** covered: [[persistence]]. The code isn't vendored | https://docs.langchain.com/oss/python/langgraph/persistence.md |
| LangChain built-in middleware params (`TodoListMiddleware`, retry, fallback, call limits) | Docs-only on [[planning]] / [[fault-tolerance]]; code lives in `langchain`, not vendored | https://docs.langchain.com/oss/python/langchain/middleware/built-in.md |
| Writing custom middleware (hooks, state) | Summary on [[middleware]]; full guide not vendored | https://docs.langchain.com/oss/python/langchain/middleware/custom.md |
| `interrupt()` / `Command` semantics beyond HITL | Summary on [[human-in-the-loop]] | https://docs.langchain.com/oss/python/langgraph/interrupts.md |
| `langchain_quickjs` interpreter internals | Docs-only on [[interpreters]]; package not vendored | https://docs.langchain.com/oss/python/deepagents/interpreters.md |
| TypeScript / JS SDK (`deepagentsjs`) | Out of scope (Python only) | https://docs.langchain.com/_llms/agent-development-lifecycle/build/type-script.md |

## Found a new gap?

Add a row here with the live URL. If you then answer it from a fetched page, say which page, and note that the claim is not checked against `../sources/package/`.

## See also

- [[index]]
- [[lookup]]
