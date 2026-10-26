---
title: Dynamic subagents (task() from interpreter code)
id: dynamic-subagents
type: how-to
status: sourced
product: sdk
keywords: dynamic subagents, dynamic sub-agent, task() in interpreter, CodeInterpreterMiddleware, QuickJS, Promise.all, fan-out, RLM, recursive subagents, langchain_quickjs, responseSchema, eval, batch dispatch
read_when: Read when fanning out over many files or tickets from interpreter code, or when gating dynamic task() dispatch.
updated: 2026-10-21
sources_hash: 0783310027b8
---

# Dynamic subagents (task() from interpreter code)

One-line truth: when an agent has both sync subagents and `CodeInterpreterMiddleware` (QuickJS), the interpreter gets a `task()` global. The model can then write JavaScript that loops, branches and `Promise.all`s over subagent dispatches instead of issuing `task` tool calls one turn at a time. Reach for it when there are many independent units (every file, every ticket), when you want multi-perspective verification, or for recursive (RLM-style) analysis. It is beta.

## Requirements

- `pip install -U "deepagents[quickjs]"` gives you `langchain-quickjs>=0.3.9` (0.7.29 METADATA; the docs say `>=0.3.0`). Python 3.11 or newer.
- At least one sync subagent. The auto-added `general-purpose` one counts, so basic fan-out needs no extra config ([[subagents]]).
- `CodeInterpreterMiddleware` in `middleware=`. It lives in `langchain_quickjs`, **not** in the deepagents 0.7.29 package, so interpreter behaviour is docs-only here ([[interpreters]]).

```python
from deepagents import create_deep_agent
from langchain_quickjs import CodeInterpreterMiddleware

agent = create_deep_agent(
    model="anthropic:claude-sonnet-5",
    subagents=[{
        "name": "reviewer",
        "description": "Reviews code for security issues, citing lines and severity",
        "system_prompt": "You are a security-focused code reviewer. Report issues with line numbers and severity.",
    }],
    middleware=[CodeInterpreterMiddleware(ptc=["glob"])],  # ptc only if code must call tools
)
agent.invoke({"messages": [{"role": "user",
    "content": "Run a workflow that reviews every file in src/routes/ and summarizes the top risks."}]})
```

## The `task()` global (JS side)

```ts
const review = await task({
  description: "Review src/auth/login.ts for auth issues. Cite line numbers.",
  subagentType: "reviewer",          // camelCase in JS
  responseSchema: { type: "object", properties: { issues: { type: "array" } } },  // optional
});
// With responseSchema the result is already an object; no JSON.parse.
```

- Inputs: `description`, `subagentType`, and an optional `responseSchema` (a JSON schema).
- Each call runs a full agentic loop of that subagent and resolves to its result: text, or a typed object when `responseSchema` is given.
- Python-side hook (verified in 0.7.29): `middleware/subagents.py` reads `config["configurable"]["__deepagents_subagent_response_format"]` (the `SUBAGENT_RESPONSE_FORMAT_CONFIG_KEY` constant) and **recompiles the declarative spec** with that response format for this call only. Compiled subagents reject it with `ValueError("response_schema cannot be used with compiled subagent ...")`.
- `tools.*` (programmatic tool calling, PTC) is off by default. Enable it with an allowlist, for example `CodeInterpreterMiddleware(ptc=["glob"])` so code can discover inputs.

## Triggering

- Dispatch is implicit: the model decides from the shape of the task. The word **"workflow"** in the user request is the documented lever, because the interpreter's system prompt treats it as a signal to orchestrate through code. For a single direct delegation, phrase the request plainly.
- Interpreter variables persist across turns with `mode="thread"` (the default), so multi-turn orchestration can keep its working set.

## Patterns (the model writes these; nothing to configure)

| Pattern | Shape | Use |
| - | - | - |
| Classify and act | route each item to a specialist by category | ticket/log triage |
| Fan-out and synthesize | `Promise.all(files.map(f => task(...)))` then merge | directory review, batch docs |
| Adversarial verification | findings, then N verifiers each, keep the confirmed ones | audits where false positives are costly |
| Generate and filter | several generators, score in code, keep the best | design proposals |
| Tournament | pairwise judge rounds | subjective selection |
| Loop until done | repeat with a dedupe set until nothing new | exhaustive sweeps, dead-code hunts |

Give each role its own subagent with a sharp `description`. The model picks `subagentType` from the names and descriptions.

## Disable

```python
CodeInterpreterMiddleware(subagents=False)  # task() global not exposed; normal `task` tool only
```

Other `CodeInterpreterMiddleware` kwargs (docs): `memory_limit=64MB`, `timeout=5.0` seconds per `eval`, `tool_name="eval"`, `capture_console=True`, `max_result_chars=4000`, `ptc=None`, `max_ptc_calls=256`, `subagents=True`, `mode="thread"` (also `"turn"` or `"call"`), `max_snapshot_bytes=None`. See [[interpreters]].

## dcode

`dcode` ships with the interpreter enabled. Ask it to "Run a workflow to ..." and it shows spawned subagents live in a dynamic-subagents panel, grouped by dispatch phase ([[dcode]]). You can get the same behaviour in other ACP clients such as Zed ([[protocols]]).

## Gotchas

- **HITL bypass:** `task()` runs inside an already-running `eval` call, not through the tool node. Parent `interrupt_on` (for example on `task`) is **not** enforced per dispatch. Gate the `eval` tool itself if you need approval ([[human-in-the-loop]]).
- `eval` has a default 5 s timeout per call (docs). Check the interaction with long subagent runs in the `langchain-quickjs` docs before relying on large fan-outs.
- JS uses `subagentType` and `responseSchema`. The Python `task` tool uses `subagent_type` and has no schema argument.
- `responseSchema` only works for declarative `SubAgent` specs, not `CompiledSubAgent`.
- Interpreter runtime and dynamic subagents are **beta**, so the APIs may change.
- Everything about `CodeInterpreterMiddleware` itself is docs-only, not found in 0.7.29 deepagents source (it lives in `langchain_quickjs`).

## Sources

- `../sources/docs/oss/python/deepagents/dynamic-subagents.md`
- `../sources/docs/oss/python/deepagents/subagents.md`
- `../sources/docs/oss/python/deepagents/interpreters.md`
- `../sources/package/deepagents/middleware/subagents.py`
- `../sources/package/deepagents-0.7.29.dist-info/METADATA` (`quickjs` extra)

## See also

- [[index]]
- [[subagents]]
- [[interpreters]]
- [[human-in-the-loop]]
- [[streaming]]
- [[dcode]]
- [[protocols]]
