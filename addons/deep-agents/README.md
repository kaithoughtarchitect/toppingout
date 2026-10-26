# Deep Agents add-on

For a product that is an AI agent built on LangChain, LangGraph or the Deep Agents SDK. Not installed by default: `/f-setup` asks whether the product is one, and installs this only on yes.

| Part | Installed to | What it does |
|---|---|---|
| `skill/deep/` | `.claude/skills/deep/` | `/deep`: sends any agent to the reference before it plans, builds or reviews agent code. The repo profile's **framework check** is set to `/deep`, so the ground investigation runs it at every end game that has a next job |
| `deepagents-ref/` | `deepagents-ref/` | the reference: a wiki checked against the real `deepagents` code (constitution, decisions, anti-patterns, a symptom to cause table, topic pages, checked recipes), its scripts, and `LEARN.md`, a beginner's guide to LangChain, LangGraph and Deep Agents |
| `mcp.json` | `.mcp.json` (only if the repo has none) | LangChain's live docs server, layer 2, for what the reference doesn't cover. A repo with its own `.mcp.json` gets the `docs-langchain` entry added by hand |
| `starter/` | the repo root, **only for a new agent project** | a running agent skeleton: `src/agent/` (memory per workspace, no shell, persistence on SQLite or Postgres), 6 tests on a fake model including a real two-process restart, `langgraph.json`, `requirements.txt`, a CI workflow, and an `AGENTS.md` to fill in. Never copied over existing files |

**Needs** Python 3.11 or later (deepagents requires it; the skeleton and its CI use 3.12), pip and network access for the sources.

**What isn't shipped:** the LangChain docs and the `deepagents` package source the wiki cites. `python deepagents-ref/scripts/setup_sources.py` fetches them into `deepagents-ref/sources/` at install (the package at the pinned version, the docs live). Commit them with the rest, so CI and the import check work on a fresh clone; the CI workflow also fetches them if they're missing.

**Install:** `/f-setup` does it. By hand: `node <package>/skills/f-setup/install.mjs --repo <repo> --addon deep-agents` (add `--starter` for the skeleton), then `python deepagents-ref/scripts/setup_sources.py`.

**Keeping it current:** the wiki was last checked against `deepagents` 0.7.29 and the docs of 2026-10-21. Docs move faster than that: after a fresh install the lint may report STALE pages or missing sources. That's drift to re-check, not breakage; `deepagents-ref/MAINTAINING.md` has the monthly refresh routine, and a refresh is done when `wiki_lint.py --strict` passes.

**Licences:** `deepagents` is MIT (its licence arrives with the fetched wheel). The docs are fetched from docs.langchain.com under LangChain's terms; the wiki pages are original notes that cite them.
