---
title: Deep Agents vs LangChain, LangGraph and Claude Agent SDK
id: products
type: decision
status: sourced
product: all
keywords: Deep Agents vs LangChain, Deep Agents vs LangGraph, Claude Agent SDK comparison, create_agent, harness vs framework vs runtime, which one to use, when to use deep agents, build harness yourself, CrewAI, Temporal, Manus, agent framework choice
read_when: Read when choosing between Deep Agents, LangChain, LangGraph or Claude Agent SDK, or deciding whether to build the harness yourself.
updated: 2026-10-21
sources_hash: 7d538fd5d280
---

# Deep Agents vs LangChain, LangGraph and Claude Agent SDK

Where Deep Agents sits: LangGraph is the **runtime**, LangChain (`create_agent`) is the **framework**, Deep Agents is the **harness** built on both. Pick the lowest layer that still gives you what you need; the layers compose.

## The three layers

| | Runtime (LangGraph) | Framework (LangChain) | Harness (Deep Agents) |
| - | - | - | - |
| Adds | durable execution, streaming, HITL interrupts, persistence | abstractions (content blocks, agent loop, middleware), integrations | predefined tools, prompts, subagents, filesystem, context management |
| Use when | low-level control; long-running stateful workflows; mixed deterministic + agentic graphs | getting started fast; standardizing how a team builds; straightforward agents | autonomous, long-horizon, complex multi-step tasks |
| Peers | Temporal, Inngest | Vercel AI SDK, CrewAI, OpenAI Agents SDK, Google ADK, LlamaIndex | Claude Agent SDK, Manus, coding CLIs |

Stack: `deepagents.create_deep_agent` -> `langchain.agents.create_agent` + middleware -> LangGraph `CompiledStateGraph` (verified: `graph.py` returns `create_agent(...).with_config(...)`).

Feature mapping:

| Feature | LangGraph | LangChain | Deep Agents |
| - | - | - | - |
| Short-term memory | checkpointer state | short-term memory | `StateBackend` |
| Long-term memory | store | long-term memory | `StoreBackend` / `memory=` |
| Skills | - | multi-agent skills | `skills=` |
| Subagents | subgraphs | multi-agent subagents | `task` tool / `subagents=` |
| HITL | interrupts | HITL middleware | `interrupt_on=` |
| Streaming | streaming | agent streaming | event streaming + `stream.subagents` |

Decision rule (README FAQ): use Deep Agents for the full harness out of the box; use `create_agent` for a lighter harness without bundled middleware; drop to LangGraph when the loop itself is the wrong shape. Any LangGraph `CompiledStateGraph` can be plugged in as a `CompiledSubAgent`, so custom orchestration composes with the harness ([[subagents]]).

## Deep Agents vs Claude Agent SDK (docs drafted 2026-04-16)

| | Deep Agents | Claude Agent SDK |
| - | - | - |
| Where agent runs | inside a sandbox, or outside using the sandbox as a tool | inside a sandbox |
| Execution backend | pluggable: state, disk, store, composite, remote sandbox, custom ([[backends]], [[sandboxes]]) | the sandbox's local filesystem |
| Models | any tool-calling LangChain model | Claude (Anthropic, Bedrock, Vertex, Azure) |
| Per-model tuning | harness profiles (beta) ([[models]]) | per call site |
| Deployment | Managed Deep Agents in LangSmith, or self-host `langgraph build` image ([[managed]], [[production]]) | self-host; build server/auth/streaming yourself; Claude managed agents is a separate product |
| Multi-tenancy | built in (scoped threads, per-user sandboxes, RBAC) | build it yourself |
| License | MIT | MIT (Claude Code proprietary) |

Claims from the comparison page (LangChain-authored, treat as vendor positioning): Deep Agents deployments include an agent server (streaming endpoints, threads, run history, webhooks, auth); the same tools/middleware/subagents carry over between managed and self-hosted; LangSmith Sandbox provides an auth proxy for third-party API calls. Used in production by OpenSWE and LangSmith Fleet. Deep Agents itself was "inspired by Claude Code" (README acknowledgements); Deep Agents Code is the analogous terminal product ([[dcode]]).

## Build the harness yourself (from `create_agent`)

The "deep agent from scratch" guide assembles a data-analysis agent one piece at a time with `create_agent` + `deepagents.middleware`:

| Step | Adds | Code |
| - | - | - |
| 1 Minimal | model + loop | `create_agent(model="google_genai:gemini-3.6-flash", tools=[])` |
| 2 Sandbox + fs | file tools + `execute` | `FilesystemMiddleware(backend=LangSmithSandbox(sandbox=sb))` |
| 3 Context | history compression | `SummarizationMiddleware(model=model, backend=backend)` |
| 4 Skills | on-demand knowledge | `SkillsMiddleware(backend=backend, sources=["/skills/"])` |
| 5 Subagent | isolated worker + planning | `TodoListMiddleware()`, `SubAgentMiddleware(backend=backend, subagents=[visualizer])` |

```python
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from langsmith.sandbox import SandboxClient
from deepagents import SubAgent
from deepagents.backends.langsmith import LangSmithSandbox
from deepagents.middleware import (FilesystemMiddleware, SkillsMiddleware,
                                   SubAgentMiddleware, SummarizationMiddleware)

client = SandboxClient()                      # needs LANGSMITH_API_KEY
sandbox = client.create_sandbox()
backend = LangSmithSandbox(sandbox=sandbox)
backend.upload_files([("/sales.csv", csv_bytes)])   # absolute POSIX paths only

model = "google_genai:gemini-3.6-flash"
visualizer: SubAgent = {
    "name": "visualizer",
    "description": "Generates charts and visualizations from data files in the sandbox.",
    "system_prompt": "You are a data visualization specialist...",
    "tools": [],
    "model": model,
}
agent = create_agent(
    model=model,
    tools=[],
    middleware=[
        FilesystemMiddleware(backend=backend),
        SummarizationMiddleware(model=model, backend=backend),
        SkillsMiddleware(backend=backend, sources=["/skills/"]),
        TodoListMiddleware(),
        SubAgentMiddleware(backend=backend, subagents=[visualizer]),
    ],
)
stream = agent.stream_events({"messages": [{"role": "user", "content": "Read /sales.csv ..."}]},
                             version="v3", config={"recursion_limit": 8})
```

What `create_deep_agent` adds beyond this hand-built stack: `PatchToolCallsMiddleware`, `_ParentNotifierMiddleware` (reports back when the agent runs as an async subagent), auto `general-purpose` subagent with its own fs/summarization stack, prompt caching, `UnsupportedContentMiddleware`, model-aware summarization thresholds, harness profiles, permissions/HITL wiring, `DeepAgentState`, `recursion_limit=9999` ([[middleware]]). It does **not** add `TodoListMiddleware` any more ([[planning]]).

## Gotchas

- The from-scratch guide says the final stack "mirrors what `create_deep_agent` assembles by default"; it does not (it includes `TodoListMiddleware`, lacks Patch/caching/UnsupportedContent/GP subagent, and puts Skills ahead of `TodoListMiddleware` and `SubAgentMiddleware`, while `create_deep_agent` now puts Skills after all of those, just before caching). The `SkillsMiddleware` docstring asks hand-built stacks to place it after summarization and any fallback or routing middleware, before caching.
- Its `visualizer` subagent gets no file or `execute` tools when used through raw `SubAgentMiddleware` (only what its spec lists), so it cannot actually write/run plotting scripts as described; pass `FilesystemMiddleware` in the spec's `middleware` or use `create_deep_agent`.
- `SummarizationMiddleware(model=..., backend=...)` built directly uses non-model-aware defaults (`trigger=None`); `create_deep_agent` uses `create_summarization_middleware`.
- products.md still lists "planning capabilities" as a harness feature; in 0.7.x it is opt-in.
- Comparison claims about Claude Agent SDK are dated 2026-04-16 and vendor-authored; verify before relying on them.

## Sources

- `../sources/docs/oss/python/concepts/products.md`
- `../sources/docs/oss/python/deepagents/comparison.md`
- `../sources/docs/oss/python/langchain/deep-agent-from-scratch.md`
- `../sources/docs/github/deepagents-README.md`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/middleware/subagents.py`

## See also

- [[index]]
- [[harness]]
- [[create-deep-agent]]
- [[middleware]]
- [[managed]]
