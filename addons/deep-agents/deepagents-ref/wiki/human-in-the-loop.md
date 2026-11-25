---
title: Human-in-the-loop (interrupt_on, approve/edit/reject/respond)
id: human-in-the-loop
type: how-to
status: code
product: sdk
keywords: human in the loop, human-in-the-loop, HITL, approval, approve edit reject, interrupt_on, InterruptOnConfig, HumanInTheLoopMiddleware, interrupt, Command resume, allowed_decisions, confirm before tool runs, pause for review, __interrupt__, interrupt_mode, per_call, ToolApprovalRequest, edit_notice
read_when: Read when a tool needs human approval before running, when a resume fails, or when subagent interrupts do not fire.
updated: 2026-11-25
sources_hash: de90c425d38e
---

# Human-in-the-loop (interrupt_on, approve/edit/reject/respond)

One-line truth: `create_deep_agent(interrupt_on={tool_name: True | False | InterruptOnConfig}, checkpointer=...)` adds LangChain's `HumanInTheLoopMiddleware`. Before a listed tool executes, the graph pauses with `__interrupt__`, and you resume on the **same thread** with `Command(resume={"decisions": [...]})`. Use it for approval gates on side-effecting tools.

## Quick reference

- `create_deep_agent(interrupt_on={tool: True | False | InterruptOnConfig}, checkpointer=...)`; checkpointer is REQUIRED to resume.
- Keys are tool names, built-ins included (`write_file`, `edit_file`, `delete`, `execute`, `task`).
- Decision types: `approve`, `edit`, `reject`, `respond`; never use `respond` to deny a side-effecting tool.
- Resume with `agent.invoke(Command(resume={"decisions": [...]}), config)` on the SAME `thread_id`.
- Several interrupts in one turn batch into one; give one decision per `action_request`, same order. That is langchain's default `interrupt_mode="batched"`, which `create_deep_agent` uses. langchain 1.5.0 also has `interrupt_mode="per_call"` (one interrupt per call, resumed by interrupt id): see Interrupt modes below.
- Declarative subagents inherit `interrupt_on`; setting it on a spec replaces (no merge).
- `CompiledSubAgent` and `AsyncSubAgent` inherit nothing; put HITL inside their graph.
- Dynamic interpreter `task()` bypasses `interrupt_on={"task": True}`; gate `eval` instead.
- Filesystem `permissions` with `mode="interrupt"` (>=0.6.8) generate interrupts; your own entry per tool wins.
- `when` predicate for conditional interrupts needs `langchain>=1.3.3`.

## Configure

```python
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver

agent = create_deep_agent(
    model="anthropic:claude-sonnet-5",
    tools=[remove_file, fetch_file, notify_email],
    interrupt_on={
        "remove_file": True,                                        # approve/edit/reject/respond
        "fetch_file": False,                                        # never interrupt
        "notify_email": {"allowed_decisions": ["approve", "reject"]},
    },
    checkpointer=MemorySaver(),   # REQUIRED to pause/resume
)
```

- The keys are **tool names**. That includes built-ins such as `write_file`, `edit_file`, `delete`, `execute` and `task`, as well as your own tools.
- `InterruptOnConfig` is a dict (`from langchain.agents.middleware import InterruptOnConfig`). It takes `allowed_decisions` and an optional `when` predicate (conditional interrupts need `langchain>=1.3.3`).
- In the stack, `HumanInTheLoopMiddleware` sits near the tail: after memory, before `UnsupportedContentMiddleware` and (since 0.7.33) `ModelRefusalMiddleware` ([[middleware]]). It is only added when the merged interrupt map is non-empty.
- `PatchToolCallsMiddleware` repairs dangling tool calls. If a run is cancelled or interrupted before a tool result exists, it adds an error `ToolMessage` ("did not complete ... may have been cancelled or interrupted") on the next run.

### Conditional interrupts

```python
from langchain.agents.middleware import ToolCallRequest

def outside_workspace(req: ToolCallRequest) -> bool:
    return not req.tool_call["args"].get("file_path", "").startswith("/workspace/")

interrupt_on = {"write_file": {"allowed_decisions": ["approve", "edit", "reject"],
                               "when": outside_workspace}}
```

`when` returning `False` means auto-approve. Such a call never enters the interrupt batch.

## Decisions

| type | effect | payload |
| - | - | - |
| `approve` | run with the original args | `{"type": "approve"}` |
| `edit` | run with new args | `{"type": "edit", "edited_action": {"name": <tool>, "args": {...}}}` |
| `reject` | skip the tool and send feedback to the model | `{"type": "reject", "message": "Not executed. Do not retry; ask which file instead."}` |
| `respond` | skip the tool and return your text **as the tool result** | for "ask_user"-style tools only |

- If `message` is omitted on `reject`, a default says the tool was not executed and not to retry unless asked. **With a `message`, that default is dropped:** the model gets only "User rejected the tool call for `<tool>` with reason: <message>" (`langchain/agents/middleware/human_in_the_loop.py:268-282`, `_answer_message`; langchain 1.5.2 with deepagents 0.7.40, probed 2026-11-25). When the user's own note is the message, write the state around it yourself ("Not executed; the draft is closed. Do not retry. The user's note: ..."), or a question in the note reads as a request to try again (seen in app rehearsals, Nov 2026: the model re-called the tool, then told the user it had tried a step that doesn't exist). Bound such wording to the turn ("in this turn"): an unbounded "do not raise it again" stays in the history, and a later explicit "yes, apply it now" was refused.
- Never use `respond` to deny a side-effecting tool, because the model may read it as success.
- Edit conservatively. Large edits can make the model re-plan or re-run the tool. In langchain 1.5.0 the result of an edited call carries a default `edit_notice` telling the model a reviewer replaced its call and ending "Do not re-issue your original call."; change it or turn it off with `HumanInTheLoopMiddleware(..., edit_notice=None)`.

## Handle and resume

```python
from langgraph.types import Command
config = {"configurable": {"thread_id": "t-1"}}

result = agent.invoke({"messages": [{"role": "user", "content": "Delete temp.txt"}]}, config=config)
if result.get("__interrupt__"):
    hitl = result["__interrupt__"][0].value
    actions = hitl["action_requests"]          # [{"name", "args", ...}], batched
    reviews = {r["action_name"]: r for r in hitl["review_configs"]}  # allowed_decisions per tool
    decisions = [{"type": "approve"} for _ in actions]               # one per action, SAME ORDER
    result = agent.invoke(Command(resume={"decisions": decisions}), config=config)  # same thread_id
```

- Several interrupting tool calls in one model turn are **batched into one interrupt**. Supply one decision per `action_request`, in order.
- Streaming: use `agent.stream(input, stream_mode=["messages", "updates"], config=config)`. Interrupts arrive as `data["__interrupt__"]` in `updates`. Loop, then restart the stream with `Command(resume=...)` as input ([[streaming]]).
- With several pending interrupts at once (parallel branches), map interrupt id to resume value instead of passing a flat payload.

## Interrupt modes (langchain 1.5.0)

`HumanInTheLoopMiddleware(interrupt_on, *, description_prefix=..., edit_notice=..., interrupt_mode="batched")` (`langchain/agents/middleware/human_in_the_loop.py`):

- `"batched"` (default, and what `create_deep_agent` builds): one interrupt per model turn whose value is a `HITLRequest` (`action_requests`, `review_configs`), resumed with `{"decisions": [...]}` in call order. Everything above describes this mode.
- `"per_call"`: one interrupt per gated tool call, raised as the call starts. Its value is a `ToolApprovalRequest` with a `response_schema`; answer each with a single decision keyed by interrupt id, `Command(resume={interrupt.id: {"type": "approve"}})`. LangGraph validates the answer before saving it: an edit can't switch tools, and an invalid answer raises `pydantic.ValidationError` so the same interrupt can be answered again. The langchain docstring says `"per_call"` is planned to become the default in the next major release.
- To use `"per_call"` with Deep Agents, pass your own `HumanInTheLoopMiddleware(interrupt_on=..., interrupt_mode="per_call")` in `middleware=`. When the agent already builds one (from `interrupt_on=` or interrupt-mode `permissions`), yours replaces it by name (`_apply_custom_middleware` in `graph.py`), so your `interrupt_on` must also cover the tools the permission rules would have gated. List it before tool retry or error-handling middleware (langchain docstring warning).

## Subagents

- A declarative `SubAgent` **inherits** the top-level `interrupt_on` unless its spec sets its own, which **overrides** the parent's (no merge).
- The general-purpose subagent gets the top-level `interrupt_on` plus any interrupts generated from permissions.
- `CompiledSubAgent` and `AsyncSubAgent` inherit **nothing**. Put HITL inside the compiled graph or the remote deployment ([[subagents]], [[async-subagents]]). Since 0.7.26 an async subagent paused on an interrupt reports task status `waiting`; the user answers it on the subagent's own thread, and the parent can't approve for them. An `update_async_task` on a `waiting` task drops its pending request. With `update_strategy="enqueue"` (0.7.30+, beta) a queued follow-up also drops a request the current run raises later: the follow-up still starts.
- Subagent interrupts surface on the parent result and parent `updates` stream as `__interrupt__`. `subgraphs=True` is only needed for child tokens. Resume through the parent with the parent's checkpointer and thread. Since 0.7.36 `task` streams the child graph instead of invoking it; probe on 0.7.39 on 2026-11-18 (fake model, `interrupt_on={"write_file": True}` inherited by the general-purpose child): the parent result held the child's `write_file` interrupt, and resuming the parent with `approve` wrote the file and finished both runs.
- A tool inside any subagent can call `langgraph.types.interrupt({...})` directly. You then resume with an arbitrary payload, for example `Command(resume={"approved": True})`.
- To gate delegation itself, use `interrupt_on={"task": True}`. **Dynamic** `task()` dispatch from interpreter code bypasses this, so gate `eval` instead ([[dynamic-subagents]]).

## Filesystem permission interrupts (>=0.6.8)

```python
from deepagents import FilesystemPermission
create_deep_agent(model=..., permissions=[
    FilesystemPermission(operations=["write"], paths=["/secrets/**"], mode="interrupt")],
    checkpointer=MemorySaver())
```

- `_build_interrupt_on_from_permissions` generates `InterruptOnConfig`s with `allowed_decisions=["approve","edit","reject","respond"]` and a path-matching `when`, for every built-in FS tool whose operation the interrupt rule covers:
  - read: `ls`, `read_file`, `glob`, `grep`
  - write: `write_file`, `edit_file`, `delete`
- These generated entries are merged with your `interrupt_on`. **Your entry wins per tool name**, which replaces the generated path predicate.
- Bulk tools (`ls`, `glob`, `grep`, `delete`) fire when the searched subtree overlaps a rule. A pathless call (for example `grep(path=None)`) always fires. `path="."` is treated as `/`, and a `glob` `pattern` that is absolute or contains `..` is also checked.
- Hidden paths: a rule only makes entries for the tools whose operation it covers. Of those, the exact tools (`read_file` for `"read"`; `write_file`, `edit_file` for `"write"`) match with `**` skipping hidden segments, so a `/secrets/**` rule doesn't pause them on `/secrets/.key`. The bulk tools it covers (`ls`, `glob`, `grep` for `"read"`; `delete` for `"write"`) still pause there, because their subtree overlaps the rule: under the write-only example above, only `delete` pauses on `/secrets/.key` (checked on 0.7.20, 2026-10-23).
- When every call of a tool must pause, list the tool itself in `interrupt_on` ([[permissions]], Interrupt mode).
- Results of an approved bulk call stay inside what was approved (since 0.7.38, `_bulk_scope` in `middleware/filesystem.py`). When any interrupt rule covers `"read"`, `ls`, `glob` and `grep` drop a result whose path or symlink-resolved target needs an interrupt but lies outside the searched path, its resolved target and (for `glob`) the pattern's anchor (`/` if the pattern climbs with `..`). Before, a symlink inside the approved folder could list or grep files under an interrupt rule elsewhere without a pause. The changelog says: "Exclude results from `ls`, `grep`, and `glob` when a symlink resolves outside the approved search scope." See [[permissions]].
- An edited call still goes back through the tool's deny check. A preceding `deny` rule beats `interrupt` (first match wins) ([[permissions]]).
- With `FilesystemBackend` (0.7.25+), the `when` predicate also checks the symlink-resolved target: it fires if either path hits an interrupt rule and neither hits a deny (a denied call fails in the tool instead of pausing). A path the backend can't resolve doesn't pause on that path (a `glob` pattern can still fire); the tool then returns `Error: cannot resolve <path>`.

## Gotchas

- **No checkpointer means no resume.** Always pass `checkpointer=` and reuse the same `thread_id` ([[persistence]]).
- The decision list must match `action_requests` order and length.
- **Raising the pause from code, with no model call** (probed on langchain 1.5.2 with deepagents 0.7.40, 2026-11-25; not in the docs, version-pinned, batched mode only). `agent.update_state(cfg, {"messages": [AIMessage(content="", tool_calls=[{"name": "apply", "args": {...}, "id": "<unique>"}])]}, as_node="model")` then `agent.invoke(None, cfg, context=ctx)` pauses with that `action_request`: `model` is wired to the last middleware's `after_model` (`langchain/agents/factory.py:1860`), and HITL's `after_model` reads the last AIMessage (`langchain/agents/middleware/human_in_the_loop.py:764-821`). Approve runs the tool once; reject runs nothing. Put several calls in one AIMessage (one interrupt with one request each) and give each a unique id. In `per_call` mode `after_model` returns None (`human_in_the_loop.py:780-782`), so this does not pause. If `invoke(None)` never runs, `PatchToolCallsMiddleware` turns the dangling call into a "cancelled" tool message on the next turn.
  - Don't instead send the model a hidden "[system] call apply" message: in rehearsals a small model ignored it 5 times in 8, then quoted it to the user.
  - If the model must never call that tool itself, hide it with a `wrap_model_call` that drops it via `request.override(tools=...)`, as `deepagents/middleware/_tool_exclusion.py:53-62` does, but without that middleware's `wrap_tool_call` rejection (`:87-93`), which would refuse the code-raised calls too. The tool stays registered, so those calls still execute; the provider accepted the calls in the history with the tool unbound (observed through OpenRouter, Nov 2026, not a code check).
  - Hiding is not a guarantee: the model can imitate calls it sees in the history (in rehearsals it re-called the tool on an already-applied draft after Approve). Keep a code check on every paused call.
- Setting `interrupt_on` on a subagent **replaces** the inherited map. Re-list every tool you still want gated.
- A user `interrupt_on` entry for `write_file` etc. silently overrides the permission-derived path predicate for that tool, so it may interrupt on every call.
- The docs say permission interrupts apply to `write_file`/`edit_file`. In code they cover **all** FS tools whose operation matches the rule, reads included. Code wins.
- Default `True` allows `respond` too (docs), so restrict `allowed_decisions` for side-effecting tools.
- `interrupt_on` does not reach compiled or async subagents.

## Sources

- `../sources/docs/oss/python/deepagents/human-in-the-loop.md`
- `../sources/docs/oss/python/deepagents/subagents.md`
- `../sources/docs/oss/python/deepagents/dynamic-subagents.md`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/middleware/_fs_interrupt.py`
- `../sources/package/deepagents/middleware/patch_tool_calls.py`
- `../sources/package/deepagents/middleware/subagents.py`
- `../sources/package/deepagents/middleware/async_subagents.py`

## See also

- [[index]]
- [[create-deep-agent]]
- [[middleware]]
- [[permissions]]
- [[subagents]]
- [[dynamic-subagents]]
- [[async-subagents]]
- [[persistence]]
- [[fault-tolerance]]
- [[streaming]]
- [[frontend]]
- [[dcode-safety]]
