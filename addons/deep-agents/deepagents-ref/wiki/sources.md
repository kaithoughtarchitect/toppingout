---
title: Sources
id: sources
type: reference
status: sourced
product: all
keywords: sources, raw docs, ground truth, package source, deepagents 0.7.29, wheel, docs mirror, changelog, fetch_docs, where to look, citations, refresh docs
read_when: Read when you need the raw doc or code path to cite, or to know which source wins when docs and code disagree.
updated: 2026-10-21
---

# Sources

What this graph is distilled from. Raw is immutable between refreshes: read it, cite it, never hand-edit it. `sourced` 2026-09-29, docs re-fetched 2026-10-21.

## Ground truth order

1. `../sources/package/deepagents/` — the `deepagents` 0.7.29 wheel, extracted ([[versions]]). Signatures, defaults, behaviour.
2. `../sources/docs/oss/python/deepagents/` — official Python SDK docs.
3. Everything else below.

Docs and code disagree → code wins, and the page's `## Gotchas` says so.

## Raw docs (`../sources/docs/`, path mirrors the URL)

| Folder | What | Pages |
|---|---|---|
| `oss/python/deepagents/` | SDK: overview, quickstart, customization, models, profiles, tools, backends, permissions, sandboxes, interpreters, subagents (sync/dynamic/async), HITL, rubric, memory, skills, context engineering, retrieval, RAG, streaming, event streaming, multimodal, protocols (ACP, AG-UI), production, fault tolerance, tutorials, comparison | 31 |
| `oss/python/deepagents/frontend/` | UI patterns (JS side) over a Python agent | 4 |
| `oss/deepagents/code/` | Deep Agents Code (`dcode`) | 16 |
| `langsmith/python/managed-deep-agents*` | Managed Deep Agents | 28 |
| `github/deepagents-CHANGELOG.md`, `github/deepagents-code-CHANGELOG.md`, `github/managed-deepagents-CHANGELOG.md` | Changelogs for the SDK, `dcode` and Managed (the docs pages now redirect to these GitHub files) | 3 |
| `oss/python/langchain/mcp/` (`index.md`, `tools.md`) | LangChain's MCP docs; the old Deep Agents MCP page redirects here | 2 |
| `langsmith/server-a2a.md` | A2A on Agent Server; the old Deep Agents A2A page redirects here | 1 |
| `oss/openwiki/overview.md` | OpenWiki, now its own docs section; the old Deep Agents page redirects here | 1 |
| `oss/python/integrations/{backends,sandboxes}/` | Integration indexes | 2 |
| `oss/python/concepts/products.md`, `oss/python/langchain/deep-agent-from-scratch.md` | Where Deep Agents sits vs LangChain/LangGraph | 2 |
| `oss/python/reference/deepagents-python.md` | API reference index (reference.langchain.com) | 1 |
| `github/deepagents-README.md` | Upstream repo README | 1 |
| `blog/agent-builder-memory.md` | LangChain blog: how Agent Builder memory works → [[agent-builder-memory]] | 1 |

Full URL list with byte counts and fetch date: `../sources/docs/MANIFEST.md`.

## Live (fetch to check; do not paste whole pages)

- Docs index for LLMs: https://docs.langchain.com/llms.txt
- SDK overview: https://docs.langchain.com/oss/python/deepagents/overview
- API reference: https://reference.langchain.com/python/deepagents
- Repo: https://github.com/langchain-ai/deepagents
- PyPI: https://pypi.org/project/deepagents/

## Refresh rule

`python scripts/fetch_docs.py` → diff `../sources/` → update the pages that cite changed files. New package version → re-vendor, update [[versions]], re-check every `status: code` page that cites a changed file. A constitution rule that no longer holds is replaced, not appended.

## Not a source

Training memory. Blog recaps and tweets. TypeScript examples (unless noting a JS-only feature).

## See also

- [[index]]
- [[versions]]
- [[agent-builder-memory]]
