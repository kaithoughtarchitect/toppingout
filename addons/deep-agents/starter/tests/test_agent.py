"""The agent's standing rules, with a scripted fake model (no API calls). deepagents-ref/wiki/testing.md."""

import asyncio

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolCall
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from agent.agent import Ctx, build_agent, memory_namespace
from agent.memory import MemoryService
from agent.tools import TOOLS


class FakeModel(GenericFakeChatModel):
    """GenericFakeChatModel refuses bind_tools; deepagents binds tools. Also records what was offered."""

    offered: list = []

    def bind_tools(self, tools, **kwargs):
        FakeModel.offered = sorted(getattr(t, "name", None) or t.get("name") for t in tools)
        return self


def call(name, args, i):
    return AIMessage(content="", tool_calls=[ToolCall(name=name, args=args, id=i)])


def run(script, store, text="hi", workspace="ws-a"):
    agent = build_agent(tools=TOOLS, model=FakeModel(messages=iter(script)), store=store, checkpointer=InMemorySaver())
    result = agent.invoke({"messages": [{"role": "user", "content": text}]},
                          config={"configurable": {"thread_id": f"{workspace}:t"}}, context=Ctx(workspace))
    return [(m.name, m.status, m.content) for m in result["messages"] if m.type == "tool"]


def test_memory_write_lands_in_workspace_store_under_stripped_key():
    store = InMemoryStore()
    tools = run([call("write_file", {"file_path": "/memories/AGENTS.md", "content": "- prefers short answers"}, "c1"),
                 AIMessage(content="saved")], store)
    assert tools[0][:2] == ("write_file", "success")
    assert store.get(memory_namespace("ws-a"), "/AGENTS.md").value["content"] == "- prefers short answers"
    assert store.get(memory_namespace("ws-a"), "/memories/AGENTS.md") is None   # prefix is stripped
    assert store.get(memory_namespace("ws-b"), "/AGENTS.md") is None            # other workspace can't see it
    assert asyncio.run(MemoryService(store).read("ws-a", "/memories/AGENTS.md")) == "- prefers short answers"


def test_writes_outside_memory_are_denied():
    tools = run([call("write_file", {"file_path": "/notes.md", "content": "x"}, "c1"), AIMessage(content="ok")],
                InMemoryStore())
    assert tools[0][1] == "error" and "permission denied" in tools[0][2]


def test_no_shell_tool_and_custom_tool_sees_workspace():
    tools = run([call("get_workspace_info", {}, "c1"), AIMessage(content="ok")], InMemoryStore(), workspace="ws-z")
    assert "execute" not in FakeModel.offered and "get_workspace_info" in FakeModel.offered
    assert tools[0] == ("get_workspace_info", "success", "workspace: ws-z")


def test_display_names_are_rejected_as_workspace_ids():
    with pytest.raises(ValueError):
        Ctx("My Workspace 1")


def test_seed_then_list():
    store = InMemoryStore()
    svc = MemoryService(store)
    assert asyncio.run(svc.seed_if_missing("ws-a")) is True
    assert asyncio.run(svc.seed_if_missing("ws-a")) is False
    assert asyncio.run(svc.list("ws-a")) == ["/memories/AGENTS.md"]
