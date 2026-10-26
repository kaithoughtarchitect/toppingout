# LangChain · LangGraph · Deep Agents: learning reference

*Written 2026-09-30 from two real agent builds, and shipped with Topping Out's Deep Agents add-on. Versions then: `deepagents` 0.7.20, `langgraph` 1.2.12, `langchain` 1.4.3. Rechecked on 2026-10-21 against `deepagents` 0.7.29, `langgraph` 1.2.16, `langchain` 1.4.6 (recipes and the SQLite restart re-run; Postgres not re-run on 0.7.29).*

---

## 1. The big picture: four layers

Think of it as a car:

```
 LangSmith        the garage & dashboard  -> tracing, Studio (visual debugger), hosted deployment
 Deep Agents      the finished car        -> create_deep_agent(): planning, files, memory, subagents built in
 LangGraph        the engine              -> runs steps as a graph; saves state; threads; pause/resume
 LangChain        the parts               -> models, tools, messages, middleware, create_agent()
```

- **LangChain** gives you the parts: one way to call any model (`"openrouter:openai/gpt-6-luna"`), tools (`@tool`), messages, and **middleware** (code that runs before and after each model or tool call).
- **LangGraph** is the engine that runs an agent as a graph of steps (call model → run tools → repeat). Its two key pieces:
  - **checkpointer:** saves the conversation after every step, keyed by a `thread_id`.
  - **store:** long-term memory that outlives any single conversation.
- **Deep Agents** is LangChain's ready-made agent on top. One call to `create_deep_agent()` gives you file tools, memory files (`AGENTS.md`), subagents and automatic summarization. The package is `deepagents`.
- **LangSmith** is LangChain's hosted service: traces (a recording of every step), Studio, and paid hosting.

Deep Agents comes in **three products** that share the name:

| Product | What it is | Command |
|---|---|---|
| Deep Agents **SDK** | The Python library you build with | `pip install deepagents` |
| Deep Agents **Code** | A ready-made coding agent for your terminal | `dcode` |
| **Managed** Deep Agents | LangSmith runs your agent for you from a folder of files | `mda` |

---

## 2. Glossary

| Term | What it is | Do we use it? |
|---|---|---|
| `deepagents-cli` | An old command-line tool that deployed Deep Agents (`deepagents deploy`, `deepagents.toml`). **Deprecated** in August 2026; PyPI says use Managed Deep Agents instead | No. Some upstream `examples/deploy-*` still show it, and they're stale |
| **mda** (Managed Deep Agents) | The replacement. You write a folder (instructions, tools, skills), and LangSmith runs it. `mda init` → `mda dev` → `mda deploy` | Not covered by the skeleton. See `deepagents-ref/wiki/managed.md` |
| `langgraph-cli` | Command-line tool for LangGraph apps. `langgraph dev` starts a local server running your agent. It reads `langgraph.json` to find it | Optional dev tool: `pip install "langgraph-cli[inmem]"` |
| **LangGraph server / Agent Server** | What `langgraph dev` starts: a web API around your agent. It manages threads and runs, and supplies its **own** checkpointer and store. The same server powers hosted deployments | Tested locally; optional |
| **LangGraph Studio** | A browser-based visual debugger connected to that server. You see each step as a diagram, messages, tool calls and state, and can replay from any step. Needs a free LangSmith account and API key. With `LANGSMITH_TRACING=false`, no data leaves your machine | Recommended for debugging (free) |
| **LangSmith Deployment** | Paid hosting of the same server in LangChain's cloud (formerly "LangGraph Platform") | Not now (cost in §6) |
| **Topping Out test adapter** | Not LangChain. It's part of the Topping Out method: three Bash functions in `foreman/test-adapter.sh` (`run_tests`, `failed_ids`, `ran_ok`). Topping Out compares tests **before and after** a change to find anything newly broken. It strips API keys, so tests can never spend money | Yes, in every Topping Out job |
| **checkpointer** | Saves each conversation (thread) step by step. `InMemorySaver` is lost on restart; `AsyncSqliteSaver` / `AsyncPostgresSaver` survive | Yes (`src/agent/persistence.py`) |
| **store** | Long-term key/value memory across threads. `InMemoryStore` (lost on restart), `AsyncSqliteStore`, `AsyncPostgresStore` | Yes |
| **thread_id** | Which conversation. Same id = same history | `"<workspace>:<conversation>"` |
| **context** | Per-run data the model can't change (e.g. whose memory this is) | `Ctx(workspace_id)` |
| **backend** | Where the agent's file tools read and write. `StateBackend` (inside the thread), `StoreBackend` (in the store), `CompositeBackend` (routes paths to backends) | `/memories/` → store, everything else → thread |
| **middleware** | Code wrapped around model and tool calls (retries, memory loading, summarization, permissions…) | `ModelRetryMiddleware`, `FreshMemory` |
| **MCP** | A standard for plugging tools and servers into agents. LangChain's docs server is an MCP server | `docs-langchain` in `.mcp.json` (layer 2) |

---

## 3. What happens when you type a message (the core mental model)

```
you> "Remember: I prefer short answers"
  │   thread_id = "demo:main" (which conversation)   context = workspace "demo" (whose memory)
  ▼
checkpointer loads this thread's history ──────────────────────────── LangGraph
  ▼
middleware before the model: FreshMemory reads /memories/AGENTS.md into the prompt ── Deep Agents
  ▼
model call (GPT-6 Luna via OpenRouter) → decides to call edit_file ─────────── LangChain
  ▼
permissions: /memories/** allowed (ok)   (any other path → "permission denied")
  ▼
CompositeBackend routes /memories/… → StoreBackend → store key "/AGENTS.md"
  in namespace ("app","mem","demo")   ← the "/memories" prefix is stripped
  ▼
model replies "Remembered." → checkpointer saves the thread
```

**Three ideas carry most of the expertise:**
1. **Thread vs. store.** A thread is one conversation. The store is memory that survives across all of them.
2. **Context vs. model arguments.** The workspace comes from `context`, so the model can't choose to read someone else's memory.
3. **Nothing persists unless you make it.** In-memory defaults vanish on restart. That's why `persistence.py` and the restart test exist.

**Gotchas that bite everyone** (full list: `deepagents-ref/wiki/anti.md`):
- `backend=lambda rt: …` raises `TypeError` in 0.7. Pass backend *instances*.
- Memory files load once per thread; edits made elsewhere only appear in a new thread (unless you use `FreshMemory`).
- The store key has no `/memories` prefix. UI code must read `/AGENTS.md`.
- `write_todos` (planning) only exists if you add `TodoListMiddleware()`.
- Subagents don't inherit your middleware or memory.
- Workspace ids must be slugs. `"My Workspace 1"` raises `ValueError`.
- On Windows, async Postgres needs `WindowsSelectorEventLoopPolicy`.

---

## 4. What the add-on gives you

```
your-repo/
├─ AGENTS.md          entry for agents (the skeleton writes one; otherwise add the Deep Agents section yourself)
├─ .mcp.json          layer 2: LangChain's live docs server
├─ deepagents-ref/    layer 1
│   ├─ wiki/          the checked reference pages
│   ├─ sources/       the docs and the deepagents package, fetched at install (scripts/setup_sources.py)
│   ├─ scripts/       setup · lint · lookup · check_imports · check_recipes · check_persistence
│   └─ LEARN.md       this page
├─ .claude/skills/deep/   /deep, next to Topping Out's skills
├─ src/agent/, tests/, langgraph.json, requirements.txt   the running skeleton (only for a new agent project)
└─ foreman/           Topping Out's method and records
```

- **Layer 1:** `deepagents-ref/`, a wiki checked against the real `deepagents` code. The code wins over the docs.
- **Layer 2:** LangChain's live docs server (MCP), for everything layer 1 doesn't cover.
- **`/deep`:** the skill that makes any agent use the two layers instead of memory. Topping Out's ground investigation runs it as the framework check at every end game that has a next job.
- **Topping Out:** the working method (the foreman plans and reviews, a builder builds, you approve).

### How the running skeleton was made

```
 wiki recipe (agent-setup.md, checked earlier)
        │  turn code snippets into real files
        ▼
 src/agent/  agent.py · persistence.py · memory.py · tools.py · chat.py · graph.py
        │
        ├─► pytest via Topping Out's test adapter ─► 6 passed (fake model, no cost)
        │        memory in right workspace · outside writes denied · no shell
        │        display names rejected · seeding · REAL restart (2 processes)
        │
        ├─► real chat turn (a real model) ─► agent edited its memory file itself (ok)
        │
        └─► langgraph dev (local Agent Server)
                 ├─ 1st try (failed) graph.py relative imports failed to load
                 ├─ fix: absolute imports + "dependencies": ["./src"]
                 └─ 2nd try (ok) graph loaded; real run wrote memory into
                               the SERVER's own store (app/mem/<workspace>)
        ▼
 docs updated · all checks pass · committed
```

Why three kinds of test?
- **Tests:** the rules hold, for free and repeatably.
- **Real chat:** the real model actually uses the memory tools.
- **Server run:** the same code works when a server supplies the storage.

### The skeleton files

| File | What it does |
|---|---|
| `src/agent/agent.py` | `build_agent()`: model, backend (memory per workspace), permissions (write only to `/memories/`), `FreshMemory`, retries, `Ctx` |
| `src/agent/persistence.py` | `open_persistence()`: SQLite locally, Postgres if `AGENT_DB_URL` is set |
| `src/agent/memory.py` | `MemoryService`: app/UI code reads and writes memory files by the correct key |
| `src/agent/tools.py` | Example read-only tool that gets the workspace from context |
| `src/agent/chat.py` | `PYTHONPATH=src .venv/Scripts/python (macOS/Linux: .venv/bin/python) -m agent.chat` to talk to it |
| `src/agent/graph.py` + `langgraph.json` | Entry point for `langgraph dev` / Studio / hosting |

---

## 5. Everyday commands

```bash
# talk to the agent (needs OPENROUTER_API_KEY in .env)
PYTHONPATH=src .venv/Scripts/python (macOS/Linux: .venv/bin/python) -m agent.chat --workspace demo

# run the tests the Topping Out way
source foreman/test-adapter.sh && run_tests /tmp/t.txt /tmp/t.exit && tail -3 /tmp/t.txt

# check agent code against the real package (catches invented APIs)
python deepagents-ref/scripts/check_imports.py src/agent/*.py

# keep the reference healthy
python deepagents-ref/scripts/wiki_lint.py          # PASS; STALE pages or missing sources are drift (MAINTAINING.md)
python deepagents-ref/scripts/fetch_docs.py         # refresh the docs

# visual debugging in LangGraph Studio (free LangSmith account + key)
pip install "langgraph-cli[inmem]" && langgraph dev
```

---

## 6. Hosting: should we use LangSmith Deployment, and what does it cost?

**How it's billed** (from LangChain's billing docs, 2026-09-30):
- **Compute:** billed while your agent's server is provisioned. "Serverless" deployments can scale to zero when idle; "Dedicated" ones are always on.
- **Storage:** the database that keeps your agent's state.
- **Traces:** billed separately.
- **Transition:** this usage-based model replaces the old per-run/uptime pricing, and existing customers switch on 1 October 2026.
- **Exact rates:** use the calculator at https://www.langchain.com/pricing (not checked here).

**Locally or hosted?**
- Run it locally while it has one user: local SQLite is free and proven, and Studio (free) via `langgraph dev` covers debugging.
- An agent that reads data only your machine can reach stays local.
- Hosting makes sense once other people use it. The same code deploys unchanged.

---

## 7. How to become the expert

1. **Read in this order** (20 min each, in `deepagents-ref/wiki/`): `constitution` → `create-deep-agent` → `middleware` → `backends` → `memory` → `persistence` → `streaming`. Then skim `anti.md` and `decisions.md`.
2. **Read `src/agent/agent.py` with `agent-setup.md` beside it.** Every line maps to a paragraph.
3. **Play:** run the chat, tell it preferences, quit, restart, ask it to recall. Then look at what's stored with `MemoryService`.
4. **Watch it think:** run `langgraph dev`, open Studio, and step through one turn.
5. **Break things on purpose** and match each failure to a row in `anti.md`:
   - swap in `InMemorySaver` and restart;
   - delete the "allow `/memories/**`" rule;
   - give `Ctx` a name with a space;
   - make a tool raise an exception while streaming.
6. **Go further:** `subagents.md` (delegation), `human-in-the-loop.md` (approvals), `skills.md` (on-demand instructions), `streaming.md` (live UI).

---

Deeper references: `deepagents-ref/AGENTS.md` (the route), `wiki/index.md` (every page), `wiki/lookup.md` (term → page).
