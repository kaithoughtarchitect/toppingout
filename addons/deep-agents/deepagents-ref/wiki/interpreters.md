---
title: Interpreters (QuickJS CodeInterpreterMiddleware)
id: interpreters
type: how-to
status: sourced
product: sdk
keywords: interpreter, code interpreter, CodeInterpreterMiddleware, QuickJS, eval tool, JavaScript REPL, programmatic tool calling, PTC, ptc, langchain_quickjs, run code in loop, orchestrate tools in code, REPL, dynamic subagents
read_when: Read when the model should loop, batch or transform data in code without a shell, call tools or subagents from code (PTC), or when choosing between an interpreter and a sandbox.
updated: 2026-10-21
sources_hash: 8d72879ee43a
---

# Interpreters (QuickJS CodeInterpreterMiddleware)

An in-process JavaScript (QuickJS on WebAssembly) REPL exposed to the model as an `eval` tool, used to loop, branch, transform data, and orchestrate tools or subagents in code so intermediate results never enter the model context. Beta.

## When to use (vs sandboxes)

| Need | Use |
| - | - |
| One or two simple calls | Normal tool calling ([[tools]]) |
| Pure in-memory JS: loops, retries, sorting/grouping/scoring data | Interpreter |
| Many tool calls orchestrated from code | Interpreter + PTC (`ptc=[...]`) |
| Fan-out over many items, verification, recursive analysis | Interpreter + `task()` ([[dynamic-subagents]]) |
| Shell, package installs, tests, OS filesystem | [[sandboxes]] |

Interpreters = code for composing tools and controlling what returns to the model ([[context-engineering]]). Sandboxes = code acting on an environment.

## Install and wire

```bash
pip install -U "deepagents[quickjs]"   # extra pins langchain-quickjs>=0.3.9 (0.7.29 METADATA); docs say >=0.3.0; Python >=3.11
```

```python
from deepagents import create_deep_agent
from langchain_quickjs import CodeInterpreterMiddleware

agent = create_deep_agent(
    model="anthropic:claude-sonnet-5",
    middleware=[CodeInterpreterMiddleware(ptc=["web_search"], mode="thread")],
)
```

`CodeInterpreterMiddleware` lives in `langchain_quickjs`, not in the `deepagents` package; it is passed through `middleware=` like any other [[middleware]]. Nothing in `deepagents` 0.7.29 source references it besides the `quickjs` extra.

## What the model gets

- Tool `eval` (rename via `tool_name`). The model writes JS; the runtime returns the value of the last expression plus captured `console.log/warn/error`.
- Top-level `await` works.
- No host filesystem, network, shell, package manager, or clock by default. Only two bridges:
  - `tools.*` (PTC): allowlisted tools as async functions, names camelCased (`web_search` -> `await tools.webSearch({query: "..."})`), input object follows the tool schema.
  - `task({description, subagentType})`: dispatch configured [[subagents]] from code; on by default when the agent has subagents (`subagents=False` to disable).
- File access inside the interpreter only by putting built-in file tools in the PTC allowlist (e.g. `ptc=["read_file", "grep"]`, see [[filesystem-tools]]).

```js
const topics = ["retrieval", "memory", "evaluation"];
const results = await Promise.all(topics.map(t => tools.webSearch({ query: `${t} best practices` })));
results.join("\n\n");
```

```js
const reviews = await Promise.all(["src/auth.ts", "src/routes/api.ts"].map(path =>
  task({ description: `Review ${path} for authentication issues`, subagentType: "reviewer" })));
reviews.join("\n\n");
```

## Configuration (`CodeInterpreterMiddleware` kwargs, per docs)

| Kwarg | Default | Meaning |
| - | - | - |
| `memory_limit` | `64 * 1024 * 1024` | QuickJS heap cap per thread |
| `timeout` | `5.0` | Seconds per `eval` call |
| `tool_name` | `"eval"` | Tool name shown to the model |
| `capture_console` | `True` | Include console output in the result |
| `max_result_chars` | `4000` | Truncate result/error/stdout text |
| `ptc` | `None` | Allowlist of tool names or `BaseTool` instances; `None` = PTC off |
| `max_ptc_calls` | `256` | Max `tools.*` calls per `eval`; `None` only if trusted |
| `subagents` | `True` | Expose `task()` when subagents exist |
| `mode` | `"thread"` | `"thread"`, `"turn"`, or `"call"` persistence |
| `max_snapshot_bytes` | `None` (= `memory_limit`) | Drop larger snapshots |

## Persistence modes

- `"thread"` (default): state survives across `eval` calls and turns. Snapshot restored at turn start, written to graph state at turn end (not between evals in a turn). No checkpointer needed for cross-turn; add one for durable threads / time travel ([[persistence]]).
- `"turn"`: shared within one turn, reset next turn.
- `"call"`: fresh REPL every `eval`.
- Snapshots keep serializable data only; functions/classes become inaccessible (`Value for 'fn' was not restored because it is not serializable (type: function).`). Restoring a snapshot never undoes side effects of PTC tool calls.

## Security

- QuickJS compiled to WebAssembly (via `quickjs-rs`), running in the host process on `wasmtime`. Per the current docs the WebAssembly sandbox is the isolation boundary: JS cannot read or write host memory, and each LangGraph thread gets its own instance. A `wasmtime` bug is the remaining way out, so keep `wasmtime` updated, and for hostile multi-tenant workloads still run agents in isolated workers or containers. (Docs fetched 2026-09-30 described it as a same-process capability boundary, not memory isolation; the docs changed, the deepagents package has no code for it.)
- The sandbox contains the engine, not the capabilities: code can call every tool bridged into it.
- The PTC allowlist is a permission boundary; do not bridge tools that spend money, mutate data, or reach arbitrary networks unless intended.
- PTC calls bypass the normal tool-call path, so `interrupt_on` approvals ([[human-in-the-loop]]) are **not** enforced for tools invoked from `eval`.

## Gotchas

- Beta: API and lifecycle may change between releases ([[versions]]).
- Default 5 s timeout and 4000-char result cap are small; long fan-outs over `task()` need a larger `timeout`.
- Interpreter code has no clock; `Date`-based logic needs an explicit time tool.
- Putting a HITL-guarded tool in `ptc` silently removes its approval gate.
- Snapshots live in graph state; large `thread`-mode state bloats checkpoints unless `max_snapshot_bytes` is set.
- The middleware is external; verify kwargs against your installed `langchain-quickjs`, since this page is docs-sourced.

## Sources

- `../sources/docs/oss/python/deepagents/interpreters.md`
- `../sources/package/deepagents-0.7.29.dist-info/METADATA`
- `../sources/package/deepagents/backends/state.py`

## See also

- [[index]]
- [[sandboxes]]
- [[dynamic-subagents]]
- [[subagents]]
- [[tools]]
- [[middleware]]
- [[human-in-the-loop]]
- [[persistence]]
- [[context-engineering]]
- [[filesystem-tools]]
- [[versions]]
