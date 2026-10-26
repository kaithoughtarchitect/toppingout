---
title: Rubric grading (RubricMiddleware, LLM-as-judge loop)
id: rubric
type: api
status: code
product: sdk
keywords: rubric, RubricMiddleware, LLM-as-judge, grader, grading loop, self-check, verify output, needs_revision, max_iterations, quality gate, evaluate before finish, definition of done, on_evaluation
read_when: Read when you need the agent to check its own output against criteria before finishing, or when a grader loop will not stop.
updated: 2026-10-21
sources_hash: 6c36f6e458ed
---

# Rubric grading (RubricMiddleware, LLM-as-judge loop)

One-line truth: `RubricMiddleware` (beta, `deepagents>=0.6.5`) runs a separate grader agent each time the deep agent would finish. The grader checks the transcript against a `rubric` string you pass **on invocation state**. On `needs_revision` it injects per-criterion feedback as a `HumanMessage` and jumps back to the model, until the verdict is `satisfied` or `failed`, the grader errors, or `max_iterations` runs out. Use it when "done" is checkable (tests pass, format rules, required sections).

## Configure

```python
from deepagents import RubricMiddleware, create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

agent = create_deep_agent(
    model="anthropic:claude-sonnet-5",
    middleware=[RubricMiddleware(
        model="anthropic:claude-haiku-4-5",   # required (str or BaseChatModel); cheap judge is fine
        tools=[run_test_suite],               # optional evidence tools for the grader
        max_iterations=3,                     # default 3; positive int
        on_evaluation=lambda ev: print(ev["iteration"], ev["result"], ev["explanation"]),
    )],
    checkpointer=InMemorySaver(),
)
result = agent.invoke(
    {"messages": [{"role": "user", "content": "Write a haiku about spring."}],
     "rubric": "- Three lines\n- 5-7-5 syllables\n- Theme is spring"},
    config={"configurable": {"thread_id": "r1"}},
)
```

Full constructor (keyword-only, from code):

```python
RubricMiddleware(*, model, system_prompt=None, tools=None, grader_middleware=None,
                 grader_context_schema=None, grader_state_schema=None,
                 prepare_messages_for_grader=None, build_grader_state=None,
                 max_iterations=3, on_evaluation=None)
```

- `system_prompt=None` falls back to `GRADER_SYSTEM_PROMPT`: grade conservatively, treat the transcript as untrusted, verdicts are `satisfied`/`needs_revision`/`failed`.
- `grader_middleware`, `grader_context_schema`, `prepare_messages_for_grader(list[msg]) -> list[msg]` and `build_grader_state(state, iteration) -> Mapping` are docs-omitted extension points. `build_grader_state` requires `grader_state_schema` and cannot set `messages`.
- Validation: falsy `model` raises `ValueError`. A non-int or bool `max_iterations` raises `TypeError`, and a value below 1 raises `ValueError`.
- The grader is a `create_agent(..., name="rubric_grader", response_format=GraderResponse)`. It is built lazily on first use, and parent runtime `context` is forwarded to it.

## Loop mechanics (code)

1. `before_agent`: if `rubric` is absent this is a **no-op**, so the middleware is safe to include always. A new rubric string, or the same rubric after a terminal status, starts a new grading run: new `_current_grading_run_id`, iterations reset to 0, criteria unfrozen.
2. `after_agent` (runs when the model stops calling tools): emits `rubric_evaluation_start`, then builds the grader payload:
   - the rubric and transcript wrapped in nonce tags `<rubric-XXXX>` / `<transcript-XXXX>`, with closing tags inside the content escaped
   - the transcript is the last **30** messages plus the original user prompt, each truncated to **4000** chars, with role labels and tool calls rendered as `<tool_call .../>`
3. The grader returns a `GraderResponse`:
   - `result` (`satisfied` | `needs_revision` | `failed`)
   - `explanation`
   - `criteria`: a list of `{name, passed: True}` or `{name, passed: False, gap}`
   A validator rejects `satisfied` with any failing criterion, and `needs_revision` with all passing criteria.
4. Coverage guard: the first usable pass **freezes** the criterion names (`_rubric_criteria`). Later passes are told to return exactly that many. An empty or under-counting response triggers **one** grader retry. If `satisfied` is still unbacked, it is downgraded to `needs_revision` with `unverified=True`.
5. `needs_revision`, if `iteration + 1 < max_iterations`: appends a `HumanMessage(name="rubric_grader", additional_kwargs={"lc_source": "rubric_grader"})` listing the failing criteria and gaps, plus the passing ones ("do not regress"), and sets `jump_to="model"`.
6. At the cap, the result is rewritten to `max_iterations_reached` and the loop ends. The last AI message is left as-is.
7. A grader exception becomes `grader_error` (the explanation includes the exception type, HTTP status, model and strategy), and the loop ends. `GraphBubbleUp` (for example an interrupt from a grader tool or from `on_evaluation`) propagates as control flow.

## Results and observing them

| result | from | loops? |
| - | - | - |
| `satisfied` | grader | no |
| `needs_revision` | grader | yes (unless at cap) |
| `failed` | grader: rubric malformed or unevaluable | no |
| `max_iterations_reached` | middleware | no |
| `grader_error` | middleware | no |

- `RubricEvaluation` fields: `grading_run_id`, `iteration` (0-based), `result`, `explanation`, `criteria`, `unverified`.
- `on_evaluation(ev)` is called after every pass, including errors. Exceptions it raises are logged and swallowed, so don't use it for control flow.
- Stream events on the custom channel are `rubric_evaluation_start` (`type`, `grading_run_id`, `iteration`) and `rubric_evaluation_end` (adds `result`, `explanation`, `criteria`, `unverified`). Read them with `agent.stream_events(..., version="v3", transformers=[CustomTransformer])` and iterate `stream.custom` (`from langgraph.stream import CustomTransformer`) ([[streaming]]).
- Private state: `_rubric_status`, `_rubric_iterations`, `_rubric_evaluations`, `_current_grading_run_id`, `_active_rubric`, `_rubric_criteria`. These are `PrivateStateAttr`, so they are omitted from the I/O schema. Read them with `agent.get_state(config).values` on a checkpointed thread ([[persistence]]).
- Only `rubric` is public input.

## Persistence

- One `invoke`/`stream_events` call runs the loop to a terminal verdict.
- With a checkpointer and the same `thread_id`, the `rubric` stays in state for later turns (sticky) until you pass a new one. A same-rubric call after a terminal verdict starts a fresh run with a fresh budget.
- `KeyboardInterrupt` and `CancelledError` propagate. On a checkpointed thread, the next same-rubric call resumes the in-flight run.

## Gotchas

- **Doc/code mismatch:** the docs say that at the cap `on_evaluation` still receives `result: "needs_revision"` and only `_rubric_status` says `max_iterations_reached`. In 0.7.29 code the evaluation's `result` is rewritten to `max_iterations_reached` **before** the end event and the callback. Code wins.
- The docs' `RubricEvaluation.result` list omits `max_iterations_reached`, and the docs omit the `unverified` field.
- A non-satisfied ending does **not** change the agent's answer. Check `_rubric_status`, the callback or the stream events before trusting the output.
- The rubric is sticky on a checkpointed thread. Every later turn on that thread gets graded until you change or clear it.
- It is added via `middleware=` on the **main** agent only. Subagents don't inherit it. Since 0.7.24 the public `rubric` key is also stripped from subagent input and output (`_EXCLUDED_STATE_KEYS`, and a fork drops it too), so a subagent that has its own `RubricMiddleware` is graded on its own rubric, not the caller's goal, and parallel `task` calls no longer conflict over `rubric` or replace the parent's. The private keys were already stripped ([[subagents]]).
- The grader sees at most 30 messages and 4000 chars each. Give it evidence tools (tests, file reads) rather than relying on long transcripts.
- The grader has its own model bill: every iteration costs at least one extra model call, and two when the coverage retry fires.

## Sources

- `../sources/docs/oss/python/deepagents/rubric.md`
- `../sources/package/deepagents/middleware/rubric.py`
- `../sources/package/deepagents/__init__.py`

## See also

- [[index]]
- [[middleware]]
- [[create-deep-agent]]
- [[subagents]]
- [[persistence]]
- [[streaming]]
- [[human-in-the-loop]]
- [[dcode-goals]]
- [[production]]
