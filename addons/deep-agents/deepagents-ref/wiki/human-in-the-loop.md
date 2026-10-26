---
title: Human-in-the-loop (interrupt_on, approve/edit/reject/respond)
id: human-in-the-loop
type: how-to
status: code
product: sdk
keywords: human in the loop, human-in-the-loop, HITL, approval, approve edit reject, interrupt_on, InterruptOnConfig, HumanInTheLoopMiddleware, interrupt, Command resume, allowed_decisions, confirm before tool runs, pause for review, __interrupt__
read_when: Read when a tool needs human approval before running, when a resume fails, or when subagent interrupts do not fire.
updated: 2026-10-21
sources_hash: 2cb255e41dec
---

# Human-in-the-loop (interrupt_on, approve/edit/reject/respond)

One-line truth: `create_deep_agent(interrupt_on={tool_name: True | False | InterruptOnConfig}, checkpointer=...)` adds LangChain's `HumanInTheLoopMiddleware`. Before a listed tool executes, the graph pauses with `__interrupt__`, and you resume on the **same thread** with `Command(resume={"decisions": [...]})`. Use it for approval gates on side-effecting tools.

## Quick reference

- `create_deep_agent(interrupt_on={tool: True | False | InterruptOnConfig}, checkpointer=...)`; checkpointer is REQUIRED to resume.
- Keys are tool names, built-ins included (`write_file`, `edit_file`, `delete`, `execute`, `task`).
- Decision types: `approve`, `edit`, `reject`, `respond`; never use `respond` to deny a side-effecting tool.
- Resume with `agent.invoke(Command(resume={"decisions": [...]}), config)` on the SAME `thread_id`.
- Several interrupts in one turn batch into one; give one decision per `action_request`, same order.
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
- In the stack, `HumanInTheLoopMiddleware` sits near the tail: after memory, before `UnsupportedContentMiddleware` ([[middleware]]). It is only added when the merged interrupt map is non-empty.
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

- If `message` is omitted on `reject`, a default says the tool was not executed and not to retry unless asked.
- Never use `respond` to deny a side-effecting tool, because the model may read it as success.
- Edit conservatively. Large edits can make the model re-plan or re-run the tool.

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

## Subagents

- A declarative `SubAgent` **inherits** the top-level `interrupt_on` unless its spec sets its own, which **overrides** the parent's (no merge).
- The general-purpose subagent gets the top-level `interrupt_on` plus any interrupts generated from permissions.
- `CompiledSubAgent` and `AsyncSubAgent` inherit **nothing**. Put HITL inside the compiled graph or the remote deployment ([[subagents]], [[async-subagents]]). Since 0.7.26 an async subagent paused on an interrupt reports task status `waiting`; the user answers it on the subagent's own thread, and the parent can't approve for them.
- Subagent interrupts surface on the parent result and parent `updates` stream as `__interrupt__`. `subgraphs=True` is only needed for child tokens. Resume through the parent with the parent's checkpointer and thread.
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
- An edited call still goes back through the tool's deny check. A preceding `deny` rule beats `interrupt` (first match wins) ([[permissions]]).
- With `FilesystemBackend` (0.7.25+), the `when` predicate also checks the symlink-resolved target: it fires if either path hits an interrupt rule and neither hits a deny (a denied call fails in the tool instead of pausing). A path the backend can't resolve doesn't pause on that path (a `glob` pattern can still fire); the tool then returns `Error: cannot resolve <path>`.

## Gotchas

- **No checkpointer means no resume.** Always pass `checkpointer=` and reuse the same `thread_id` ([[persistence]]).
- The decision list must match `action_requests` order and length.
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
