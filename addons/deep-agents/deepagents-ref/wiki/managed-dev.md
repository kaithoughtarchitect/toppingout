---
title: MDA local development, evals and tutorial
id: managed-dev
type: how-to
status: sourced
product: managed
keywords: mda dev, local development, LangSmith Studio, hot reload, mda evals, Harbor, evals, eval-engineering, tutorial, Tavily tool, .mda/build, langgraph dev, test schedule locally, memory not persisting, MDA_DEV, harbor-job.json
read_when: Read when running or debugging a Managed Deep Agent locally, writing Harbor evals, or working through the tool plus memory plus schedule tutorial.
updated: 2026-11-25
sources_hash: dfc87182b868
---

# MDA local development, evals and tutorial

The inner loop for a Managed Deep Agent: `mda dev` runs it locally in LangSmith Studio, `mda evals init` sets up Harbor evals driven by a coding agent, and the daily digest pattern (the docs' former tutorial) shows memory + schedule on the quickstart agent. Overview: [[managed]].

## `mda dev`

```bash
uv sync
uv run mda dev            # --port, --hostname, --no-browser, --no-reload, --no-schedules
```

What it does:
1. Validates and compiles into `.mda/build`.
2. Copies project `.env` to `.mda/build/.env` (only `.env` is staged for the server; a value exported in your shell is not, per migrate page) and adds local-only identity config. For the CLI's own settings, 0.10.0 (changelog, breaking) reads `LANGSMITH_API_KEY`, `LANGSMITH_ENDPOINT`, `LANGSMITH_WORKSPACE_ID` and, in `mda dev`, `LANGSMITH_PROJECT` from the shell first and the project `.env` second, and warns once when the two differ.
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
| Tracing | The agent's **Local** environment, project `{name}-local` (from `define_deep_agent(name=...)`) | Deployment project |

- Hot reload watches sources (0.5.3), but the docs still say to stop and rerun after changing project files; rerun after adding new managed files (e.g. `memory.py`) so they are discovered.
- Doc contradiction: the local-development page still says schedules never run under `mda dev`; the schedules and CLI pages and the 0.9.3 changelog say they fire locally. On >=0.9.3, trust the schedules page.
- `mda chat [path]` is a terminal client for the local agent (now on the CLI page). It reuses a running dev server or starts one (since 0.8.6; log in `.mda/dev-server.log`). Flags: `--url URL` (must be a local dev server or a tunnel to one, because `mda chat` sends no credentials), `--assistant ID` (defaults to the one `mda dev` staged, then the agent `name`), `-t/--thread ID` (continue a thread), `--env-file PATH` (>=0.10.0; env file used when it starts a dev server). Per-call HITL (`interrupt_mode="per_call"`) needs `langgraph-api` 0.16 or later under `mda dev` (0.9.3).
- Local traces are rejected until the agent record exists (the 2026-11-25 local-development and quickstart pages dropped the old "in an agent-based workspace" qualifier, so expect this in any workspace). `mda deploy` creates it, `mda dev` does not: create the agent once (UI or API, same identifier) or deploy once. Studio chat still works meanwhile.
- Test identity, sandbox and user-owned OAuth on a deployment, not locally. `mda deploy --agent-server-type serverless|dedicated` (default `serverless`). The 2026-11-18 docs renamed the flag; `--deployment-type` stays a hidden alias, and an older CLI may only know the old spelling (0.10.4 changelog: "Agent Server naming and flags with hidden deployment aliases"). The 0.10.0 changelog says `dev` and `prod` still work as values; the docs list only `serverless|dedicated`. Serverless is available in every LangSmith Cloud region and can scale to zero; use `dedicated` for always-on capacity (deploy page). BYOC data planes do not support Serverless and get Dedicated by default.
- `mda pull [path]` (>=0.10.2) copies `instructions.md` and `skills/` from the deployed agent's Context Hub entry into the local project, so edits made in LangSmith come back to your files. It lists every add, overwrite and delete and asks first; `--dry-run` only shows them, `-y/--yes` is required without a terminal. It never changes agent code or memories and writes nothing remote. Other flags: `-n/--name`, `--workspace-id`, `--agent-environment`, `--env-file`.
- `mda init` scaffolds an `AGENTS.md` for coding agents working in the project (0.10.2; 0.10.4 changelog). It lists the project commands and tells the agent not to run `mda deploy` unless the user asks. Build and deploy leave the root `AGENTS.md` out.

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
- Async subagents: `mda eval` starts a local Agent Server for an agent that declares async subagents (needs `managed-deepagents>=0.10.2` and the matching `mda` CLI; subagents page, 2026-11-25). The earlier docs said such agents could not be evaluated. Evaluated agents without declared async subagents still get neither the async `general-purpose` subagent nor the async task tools.

## Daily digest pattern (was the tutorial)

The 2026-11-25 docs replaced the tutorial ("Add a custom search tool, memory, and a schedule") with a shorter pattern, "Build a daily digest agent". It needs `managed-deepagents>=0.10.4` and the matching `mda` CLI. It keeps the quickstart's built-in web search and drops the authored Tavily tool and its `research-tavily` connection (for an authored search tool with a connection, see [[managed-capabilities]]).

1. `memory.py` turns on shared agent memory:

```python
from managed_deepagents import MemoryLayer, define_memory

memory = define_memory(agent=MemoryLayer())
```

2. Replace `instructions.md`:

```markdown
# Digest agent

You are a research assistant. When someone asks you to follow or stop
following a topic, update /memories/agent/topics.md and confirm the change.

When asked for a digest, read that file, search for news from the last day on
each topic, and write a short digest with one or two cited items per topic.
```

3. `schedules/daily_digest.py`, every weekday at 8:00 AM Pacific. Schedule name = module stem (`daily_digest` in Python, `daily-digest` in TS):

```python
from managed_deepagents import define_schedule

schedule = define_schedule(
    cron="0 8 * * 1-5",
    timezone="America/Los_Angeles",
    prompt="Write today's digest.",
)
```

4. Try it under `mda dev`: say "Follow LangChain releases", then in a new thread ask for today's digest; the agent reads the topics from memory with no thread history. Deploy to run the schedule; each scheduled run starts a new thread.

Extensions the page lists: post the digest to Slack with schedule delivery (`deliver_to`), let people set their own time with runtime schedules ([[managed-channels]]), or use built-in web search so no separate API key is needed.

Details for each piece: [[managed-capabilities]] (memory), [[managed-channels]] (schedules), [[managed-project]] (instructions). The other patterns are listed in [[managed]].

## Gotchas

- Local and deployed memory never mix; facts taught under `mda dev` are absent after deploy.
- A memory layer that "does nothing" in Studio is usually undeclared; check `memory.py` first.
- User-owned connections cannot be exercised end-to-end locally in general; deploy to test the authorization interrupt (though 0.7.0 made user grants resolve in `mda dev` via your personal key).
- `mda dev` requires a personal LangSmith API key for user memory / user connections (0.8.2 clarifies PAT requirement).
- Harbor needs Docker; eval runs pin `harbor[langsmith]==0.21.0` and Python 3.12.
- Before 0.10.5, `mda dev` restarted the server on every save when LangSmith settings were exported in the shell (changelog fix). Since 0.10.5 `mda deploy` prints the agent identity when it finishes, and `mda prepare` lets build runners compile without credentials.

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
