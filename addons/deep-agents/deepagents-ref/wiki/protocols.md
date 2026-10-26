---
title: Protocols (ACP, AG-UI, A2A)
id: protocols
type: reference
status: sourced
product: sdk
keywords: ACP, Agent Client Protocol, deepagents-acp, AG-UI, @ag-ui/langgraph, A2A, Agent2Agent, editor integration, Zed, agent to agent, agent protocol, JSON-RPC, a2a assistant_id, IDE
read_when: Read when exposing an agent to an editor (ACP), a frontend (AG-UI) or other agents (A2A), or asking which protocol does what.
updated: 2026-10-21
sources_hash: 1086e359ab45
---

# Protocols (ACP, AG-UI, A2A)

One-line truth: none of these live in the `deepagents` package. ACP = separate `deepagents-acp` package (agent ↔ editor over stdio); AG-UI = TypeScript `@ag-ui/langgraph` adapter in front of a LangGraph server (agent ↔ frontend); A2A = built into LangSmith Agent Server at `/a2a/{assistant_id}` (agent ↔ agent). MCP (agent → external tools) is separate — see [[mcp]].

| Protocol | Direction | What you install / run | Transport |
| - | - | - | - |
| MCP | agent calls tools | `langchain[mcp]` | HTTP / stdio |
| ACP | editor/IDE drives agent | `pip install deepagents-acp` | stdio JSON-RPC |
| AG-UI | frontend drives agent | `langgraph dev` + TS `@ag-ui/langgraph` | HTTP events |
| A2A | other agents call agent | Agent Server (`langgraph-api>=0.4.21`) | JSON-RPC over HTTP / SSE |

## ACP (Agent Client Protocol)

```python
import asyncio
from acp import run_agent
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver
from deepagents_acp.server import AgentServerACP

async def main() -> None:
    agent = create_deep_agent(
        model="anthropic:claude-sonnet-4-6",
        system_prompt="You are a helpful coding assistant",
        checkpointer=MemorySaver(),        # ACP sessions need thread state
    )
    await run_agent(AgentServerACP(agent))  # stdio server: reads stdin, writes stdout

if __name__ == "__main__":
    asyncio.run(main())
```

- Launched *by the client*, not run as a daemon. Clients: Zed, JetBrains, VS Code (`vscode-acp`), Neovim plugins; Toad for local dev: `toad acp "uv run python path/to/your_server.py" .`
- Zed `settings.json`: `{"agent_servers": {"DeepAgents": {"type": "custom", "command": "/abs/path/run_demo_agent.sh"}}}`. Demo lives in `deepagents` repo `libs/acp` (`uv sync --all-groups`, set `ANTHROPIC_API_KEY` in `.env`).
- Because stdout is the protocol channel, never `print()` to stdout in tools/middleware of an ACP-served agent (log to stderr).
- Deep Agents Code (`dcode`) is the productized coding agent; ACP is how you put your *own* deep agent in an editor — see [[dcode]].

## AG-UI (Agent-User Interaction)

1. `pip install deepagents "langgraph-cli[inmem]"`; export `agent = create_deep_agent(...)` in `agent.py`.
2. `langgraph.json`: `{"dependencies": ["."], "graphs": {"deep_agent": "./agent.py:agent"}, "env": ".env"}`; run `langgraph dev` (`http://localhost:2024`).
3. TS: `new LangGraphAgent({ graphId: "deep_agent", deploymentUrl: "http://localhost:2024" })`.

Event mapping: run lifecycle `RUN_STARTED/RUN_FINISHED/RUN_ERROR`; node progress `STEP_STARTED/STEP_FINISHED`; text `TEXT_MESSAGE_START/CONTENT/END`; tools `TOOL_CALL_START/ARGS/END/RESULT`; reasoning `REASONING_START/REASONING_MESSAGE_CONTENT/REASONING_END`; state (todos, subagents, custom keys) `STATE_SNAPSHOT` + `STATE_DELTA` (JSON Patch RFC 6902); history `MESSAGES_SNAPSHOT`.

Interrupts ([[human-in-the-loop]]): default emits a legacy `on_interrupt` custom event with `RUN_FINISHED`; set `emitInterruptOutcome: true` to get `RUN_FINISHED.outcome.type === "interrupt"`; resume with input `resume: [{interruptId, status: "resolved", payload}]`. API: `runAgent(params?, subscriber?)`, `subscribe(subscriber)`, `abortRun()`, seed via `initialMessages` / `addMessage` / `setMessages`. Python-side bridge alternative: CopilotKit FastAPI integration. See [[frontend]], [[streaming]].

## A2A (Agent2Agent) in Agent Server

Endpoint `POST /a2a/{assistant_id}` on any Agent Server deployment ([[production]]). Speaks A2A **v1.0** JSON-RPC and accepts four v0.3 names.

| v1.0 | v0.3 | Status |
| - | - | - |
| `SendMessage` | `message/send` | yes (blocks until the run ends unless `returnImmediately`) |
| `SendStreamingMessage` | `message/stream` | yes (SSE, `Accept: text/event-stream`) |
| `GetTask` | `tasks/get` | yes |
| `CancelTask` | `tasks/cancel` | yes |
| `ListTasks` | — | yes |
| `GetExtendedAgentCard` | — | yes (v1.0 name only; not advertised) |
| `SubscribeToTask`, `*TaskPushNotificationConfig` | — | `-32601` |

Conversation model: `contextId` = LangGraph `thread_id` (must be a UUID — echo the server's; `session-42` → `-32602 Invalid thread ID`); `taskId` = one turn. First message: omit both. Later turns: send `message.contextId` only; never resend a terminal `taskId` (`-32004`); foreign `taskId` → `-32001`. `metadata.thread_id` on the payload is ignored.

```python
payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "message/send",
           "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": text}],
                                  "messageId": str(uuid.uuid4()), **({"contextId": ctx} if ctx else {})}}}
```

Rules and knobs:
- Method family picks enum casing in responses: v1.0 → `TASK_STATE_WORKING`, `ROLE_AGENT`; v0.3 → `working`, `agent`. Envelope: `SendMessage` → `result.task`; `GetTask` and all v0.3 → `result`; `ListTasks` → `result.tasks`.
- History defaults to whole **context**; set `historyScope: "task"` (`SendMessage`: in `configuration`; `GetTask`/`ListTasks`: in `params`; or header `LangGraph-A2A-History-Scope: task`). `historyLength` max 10. Streaming ignores both.
- Graph state must have a `messages` key (deep agents do).
- Per-assistant `metadata.a2a` (set via Assistants API; `langgraph.json` can't): `input_modes`/`output_modes` (advertisement only), `a2ui: true` (A2UI v0.9). A2UI can also be turned on for a whole deployment with env `A2A_A2UI_ENABLED=true`; the per-assistant value wins. The canonical MIME is `application/json+a2ui` (`application/a2ui+json` is accepted on input and echoed back). The client activates it per request with the `A2A-Extensions` header.
- Non-blocking send: `configuration.returnImmediately: true` (v0.3: `blocking: false`) returns the task as soon as the run is created; poll `GetTask` until it is terminal or `TASK_STATE_INPUT_REQUIRED`.
- Interrupts ([[human-in-the-loop]]): an `interrupt()` moves the task to `TASK_STATE_INPUT_REQUIRED` with an artifact named `Interrupt` (one `DataPart` per pending interrupt: `id`, `value`, optional `response_schema`). Resume by sending the same `taskId` and `contextId` with a `DataPart` `{"resume": <value>}` or a text part.
- `FilePart` in/out maps to LangChain content blocks ([[multimodal]]). Tool results published as `DataPart`s; allowlist with env `A2A_ALLOWED_TOOL_CALL_RESULTS=tool_a,tool_b`.
- Disable: `langgraph.json` `{"http": {"disable_a2a": true}}`.
- Tracing: `contextId`→`thread_id` groups multi-agent turns in one LangSmith thread; non-LangGraph agents set span attribute `langsmith.metadata.thread_id`.
- Min `langgraph-api`: endpoint 0.4.21; inbound FilePart 0.12.0; DataParts 0.12.2; allowlist 0.12.4; outbound FilePart + card modes 0.13.0; A2UI + `historyScope` 0.15.0; `response_schema` in interrupt artifacts 0.16.0; `returnImmediately` / `blocking` 0.18.0. The docs' install line is `langgraph-api>=0.16.0`.

A2A is not how Deep Agents' own async subagents talk to remote graphs; those use the LangGraph SDK against a deployment `graph_id` — see [[async-subagents]].

## Gotchas

- Known Agent Server A2A gaps: responses still v0.3 wire shape (`kind`, `mimeType`), flat SSE events with `final`, snake_case `tool_results`, `+00:00` timestamps, no error `data`, `A2A-Version` header ignored, no card caching headers, `GetExtendedAgentCard` served but not advertised.
- The A2A page moved out of the Deep Agents docs into the LangSmith Agent Server docs (`/langsmith/server-a2a`); it is generic Agent Server behavior, not Deep Agents code.
- Docs give two agent-card URLs: `GET /.well-known/agent-card.json?assistant_id={id}` and `GET /a2a/{assistant_id}/.well-known/agent-card.json`. The "test your integration" curl uses the latter; verify against your deployment.
- A mis-cased `historyscope` is silently ignored (you get full-context history).
- ACP's `MemorySaver` loses sessions on restart; use a persistent checkpointer for real use ([[persistence]]).
- AG-UI adapter is TypeScript only; a Python graph works fine behind it.

## Sources
- `../sources/docs/oss/python/deepagents/acp.md`
- `../sources/docs/oss/python/deepagents/ag-ui.md`
- `../sources/docs/langsmith/server-a2a.md` (the old Deep Agents A2A page redirects here)

## See also
- [[index]]
- [[mcp]]
- [[frontend]]
- [[streaming]]
- [[human-in-the-loop]]
- [[production]]
- [[dcode]]
- [[async-subagents]]
- [[persistence]]
- [[multimodal]]
