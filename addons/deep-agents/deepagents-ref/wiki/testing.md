---
title: Testing a deep agent (pytest, fake models)
id: testing
type: how-to
status: code
product: sdk
keywords: testing, test, unit test, pytest, fake model, fake chat model, mock model, GenericFakeChatModel, FakeMessagesListChatModel, bind_tools, no API calls, offline tests, scripted model
read_when: Read when writing tests for an agent that must not call the real model, or when a fake model raises NotImplementedError or StopIteration.
updated: 2026-10-21
sources_hash: a8b312e61597
---

# Testing a deep agent (pytest, fake models)

Script the model's replies with a LangChain fake chat model so tests make no API calls. Deep Agents binds tools to the model, and the stock fakes refuse that, so you need a one-line subclass. The pytest below **passed** on `deepagents` 0.7.20 / `langgraph` 1.2.12 on 2026-09-30, and again on `deepagents` 0.7.29 / `langgraph` 1.2.16 / `langchain` 1.4.6 on 2026-10-21.

## Quick reference

- `GenericFakeChatModel(messages=iter([...]))` raises `NotImplementedError` at `bind_tools` inside `create_deep_agent`. Subclass it and return `self` from `bind_tools`.
- It uses one scripted message per model call. An extra call (summarization, a subagent, a retry) exhausts the iterator and raises `StopIteration`.
- For `.stream()` tests use `FakeMessagesListChatModel(responses=[...])` with the same subclass. `GenericFakeChatModel` streaming drops tool calls.
- Passing a model **instance** skips provider profiles, so tests don't exercise OpenRouter or OpenAI profile behaviour ([[models]]).
- Assert on the store and tool messages, not on the model's words.

## Minimal pytest (ran, passed)

```python
from dataclasses import dataclass
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolCall
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

class FakeToolModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):   # deepagents binds tools; the base fake refuses
        return self

@dataclass
class Ctx:
    workspace_id: str

@tool
def get_record() -> str:
    """Return the record list."""
    return "record: 42"

def build(script):
    store = InMemoryStore()
    agent = create_deep_agent(
        model=FakeToolModel(messages=iter(script)),
        tools=[get_record], context_schema=Ctx, memory=["/memories/AGENTS.md"],
        backend=CompositeBackend(default=StateBackend(), routes={
            "/memories/": StoreBackend(namespace=lambda rt: ("app", rt.context.workspace_id))}),
        checkpointer=InMemorySaver(), store=store)
    return agent, store

def test_tool_and_memory():
    agent, store = build([
        AIMessage(content="", tool_calls=[ToolCall(name="get_record", args={}, id="c1")]),
        AIMessage(content="", tool_calls=[ToolCall(name="write_file",
            args={"file_path": "/memories/AGENTS.md", "content": "- concise"}, id="c2")]),
        AIMessage(content="Done"),
    ])
    r = agent.invoke({"messages": [{"role": "user", "content": "records?"}]},
                     config={"configurable": {"thread_id": "t1"}}, context=Ctx("c-1"))
    assert r["messages"][-1].content == "Done"
    assert [m.name for m in r["messages"] if m.type == "tool"][0] == "get_record"
    item = store.get(("app", "c-1"), "/AGENTS.md")     # route prefix stripped
    assert item and "concise" in item.value["content"]
```

In-memory saver and store are right for unit tests. Restart tests need the durable classes ([[persistence]]).

## Useful assertions

- A tool ran: `[m.name for m in r["messages"] if m.type == "tool"]`.
- A tool failed: `m.status == "error"` on the `ToolMessage` ([[streaming]], failed turns).
- A permission denial: the tool content starts `Error: permission denied for write on …` ([[permissions]]).
- Memory written: `store.get(ns, "/AGENTS.md")`, using the key without `/memories` ([[memory]]).
- Which tools the model was offered: record the `tools` argument in your `bind_tools` override. That's how [[agent-setup]] proves there's no `execute` tool.

## Gotchas

- Script length must equal the number of model calls. Subagents inherit the parent's model instance, so a `task` call should consume items from the **same** iterator. This is inferred from model inheritance and wasn't run. Give each custom subagent its own scripted fake to keep the counts clear.
- The first import on Windows is slow (one test took about 80 s cold). It isn't a hang.
- LangChain's own unit-testing page (layer 2) shows the fake without the `bind_tools` override. That version fails with Deep Agents.
- Evals and trajectory scoring aren't covered here. See [[gaps]].

## Sources

- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/_models.py`
- `../scripts/check_recipes.py`

## See also

- [[index]]
- [[agent-setup]]
- [[persistence]]
- [[streaming]]
