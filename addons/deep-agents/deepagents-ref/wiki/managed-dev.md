---
title: MDA local development, evals and tutorial
id: managed-dev
type: how-to
status: sourced
product: managed
keywords: mda dev, local development, LangSmith Studio, hot reload, mda evals, Harbor, evals, eval-engineering, tutorial, Tavily tool, .mda/build, langgraph dev, test schedule locally, memory not persisting, MDA_DEV, harbor-job.json
read_when: Read when running or debugging a Managed Deep Agent locally, writing Harbor evals, or working through the tool plus memory plus schedule tutorial.
updated: 2026-10-21
sources_hash: ac111fb1418e
---

# MDA local development, evals and tutorial

The inner loop for a Managed Deep Agent: `mda dev` runs it locally in LangSmith Studio, `mda evals init` sets up Harbor evals driven by a coding agent, and the tutorial shows the canonical tool + memory + schedule build-out. Overview: [[managed]].

## `mda dev`

```bash
uv sync
uv run mda dev            # --port, --hostname, --no-browser, --no-reload, --no-schedules
```

What it does:
1. Validates and compiles into `.mda/build`.
2. Copies project `.env` to `.mda/build/.env` (only `.env` is read; a value exported in your shell is not, per migrate page) and adds local-only identity config.
3. Creates a local Context Hub mock for instructions, skills, memory (`.mda/__contexthub__`).
4. Starts `uv run --with langgraph-cli[inmem]>=0.4.36 langgraph dev` from the build dir (needs `uv`; you do not install langgraph-cli).
5. Opens Studio (unless `--no-browser`).

Local behavior that differs from a deployment:

| Area | `mda dev` | Deployed |
| - | - | - |
| Identity | Studio gives a local test user; `/mcp` and all routes need no credential (unscoped local service principal) | Enforced per `identity.py` |
| User principal | `langsmith-dev` Agent Auth principal from your **personal** LangSmith API key (prompts browser sign-in otherwise) | Logged-in LangSmith user (Studio) / resolved caller |
| Sandbox | Tries provider; falls back to a temp dir and prints its path | LangSmith sandbox per thread |
| Memory | On disk in `.mda/__contexthub__`, separate from deployed memory | Context Hub |
| Schedules | >=0.9.3: local crons that fire, recreated when `schedules/` changes (`--no-schedules` turns them off); older versions list them but never fire | Crons after deploy |
| Agent-owned connections | Read `MDA_DEV_<SLUG>` env var | Workspace credential |
| Tracing | Separate tracing project for local runs (0.7.2) | Deployment project |

- Hot reload watches sources (0.5.3), but the docs still say to stop and rerun after changing project files; rerun after adding new managed files (e.g. `memory.py`) so they are discovered.
- Doc contradiction: the local-development page still says schedules never run under `mda dev`; the schedules and CLI pages and the 0.9.3 changelog say they fire locally. On >=0.9.3, trust the schedules page.
- `mda chat` (changelog only) is a terminal client for the local agent; since 0.8.6 it starts its own dev server if none is running (log in `.mda/dev-server.log`). Per-call HITL (`interrupt_mode="per_call"`) needs `langgraph-api` 0.16 or later under `mda dev` (0.9.3).
- Test identity, sandbox and user-owned OAuth on a **dev deployment** (`mda deploy`, default `--deployment-type dev`), not locally.

## Evals (Harbor)

MDA evals are [Harbor](https://www.harborframework.com/docs/tasks) tasks authored by a coding agent using the `eval-engineering` skill. Prereqs: `uv`, Docker, a coding agent (e.g. [[dcode]] or another coding agent the init command detects).

```bash
uvx --from npx-skills skills add langchain-ai/langchain-skills --skill eval-engineering --yes
uv run mda evals init -i      # -i: pick a detected coding agent or copy the prompt
```

Creates `evals/harbor-job.json` (user-owned, written only if missing) and generated `.mda/evals/runtime.json` + `.mda/evals/harbor-adapter/`. `mda init` no longer creates evals.

Task layout (each direct child of `evals/` with an instruction and tests):

```text
evals/<task>/
├── Task.md            # human-reviewed spec
├── instruction.md     # what the agent is asked to do
├── task.toml
├── environment/Dockerfile
└── tests/test.sh      # writes /logs/verifier/reward.txt (number) or reward.json (metrics)
```

Run (the handoff prints the exact command; PowerShell form on Windows):

```bash
HARBOR_LANGSMITH_DATASET=mda-my-agent-evals \
PYTHONPATH=.mda/evals/harbor-adapter \
uv run --env-file .env --python 3.12 --with 'harbor[langsmith]==0.21.0' harbor run \
  --config evals/harbor-job.json --yes \
  --plugin mda_harbor.job_plugin:MDAJobPlugin \
  --plugin mda_harbor.langsmith_plugin:LangSmithPlugin

uv run --python 3.12 --with 'harbor[langsmith]==0.21.0' harbor view .mda/evals/jobs
```

- `mda evals compile` is internal (run by the job plugin at job start).
- With `LANGSMITH_API_KEY` set, runs are recorded in the `HARBOR_LANGSMITH_DATASET` dataset.
- Trials have no Context Hub: the compiled project is copied in, so `/skills/` is the project's own `skills/` (fixed in 0.7.2). Memory is off and the authored sandbox is not instantiated in eval mode. All shell-exportable `.env` keys are forwarded to trials.
- Edit `harbor-job.json` for datasets, attempts, concurrency, env vars.

## Tutorial: quickstart -> tool + memory + schedule

Starting from the quickstart `research-assistant` ([[tutorials]] for OSS equivalents):

1. Authored Tavily tool replaces provider search:

```python
# tools/search.py
import os
from typing import Literal
from langchain.tools import tool
from tavily import TavilyClient

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])   # TAVILY_API_KEY in .env; uv add tavily-python

@tool
def internet_search(query: str, max_results: int = 5,
                    topic: Literal["general", "news", "finance"] = "general") -> dict:
    """Search the internet for relevant sources."""
    return tavily_client.search(query, max_results=max_results, topic=topic)
```

```python
# agent.py
from managed_deepagents import define_deep_agent
from tools.search import internet_search

agent = define_deep_agent(name="research-assistant", model="openai:gpt-5.5", tools=[internet_search])
```

2. Add a `## Memory` policy section to `instructions.md` (what to keep, no personal data/secrets).
3. `memory.py`: `memory = define_memory(agent=MemoryLayer())`; restart `mda dev`; teach a rule in one thread, verify in a new thread.
4. `schedules/daily_digest.py` with `define_schedule(cron="0 8 * * 1-5", timezone="America/Los_Angeles", prompt=...)`. Schedule name = module stem (`daily_digest` in Python, `daily-digest` in TS).
5. `uv run mda deploy` (no `--no-wait`), then confirm deployment ready, cron present, traces show `internet_search` and memory reads/writes.

Details for each piece: [[managed-capabilities]] (tools, memory), [[managed-channels]] (schedules), [[managed-project]] (instructions).

## Gotchas

- Local and deployed memory never mix; facts taught under `mda dev` are absent after deploy.
- A memory layer that "does nothing" in Studio is usually undeclared; check `memory.py` first.
- User-owned connections cannot be exercised end-to-end locally in general; deploy to test the authorization interrupt (though 0.7.0 made user grants resolve in `mda dev` via your personal key).
- `mda dev` requires a personal LangSmith API key for user memory / user connections (0.8.2 clarifies PAT requirement).
- Harbor needs Docker; eval runs pin `harbor[langsmith]==0.21.0` and Python 3.12.

## Sources

- `../sources/docs/langsmith/python/managed-deep-agents-local-development.md`
- `../sources/docs/langsmith/python/managed-deep-agents-evals.md`
- `../sources/docs/langsmith/python/managed-deep-agents-tutorial.md`
- `../sources/docs/langsmith/python/managed-deep-agents-cli.md`
- `../sources/docs/langsmith/python/managed-deep-agents-memory.md`
- `../sources/docs/langsmith/python/managed-deep-agents-connections.md`
- `../sources/docs/langsmith/python/managed-deep-agents-schedules.md`
- `../sources/docs/github/managed-deepagents-CHANGELOG.md`

## See also

- [[index]]
- [[managed]]
- [[managed-project]]
- [[managed-capabilities]]
- [[managed-channels]]
