"""One process of the restart test (run by test_restart.py; not collected by pytest)."""

import asyncio
import sys

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolCall

from agent.agent import Ctx, build_agent
from agent.memory import MemoryService
from agent.persistence import open_persistence, use_selector_loop_on_windows
from agent.tools import TOOLS


class FakeModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


async def main(n: int, data_dir: str) -> None:
    script = ([AIMessage(content="", tool_calls=[ToolCall(name="write_file", args={
                  "file_path": "/memories/AGENTS.md", "content": "- prefers short answers"}, id="w1")]),
               AIMessage(content="saved")] if n == 1 else [AIMessage(content="still here")])
    async with open_persistence(data_dir) as (checkpointer, store):
        agent = build_agent(tools=TOOLS, model=FakeModel(messages=iter(script)), store=store, checkpointer=checkpointer)
        result = await agent.ainvoke({"messages": [{"role": "user", "content": f"pass {n}"}]},
                                     config={"configurable": {"thread_id": "ws-a:main"}}, context=Ctx("ws-a"))
        memory = await MemoryService(store).read("ws-a", "/memories/AGENTS.md")
        print(f"memory={memory} messages={len(result['messages'])}")


if __name__ == "__main__":
    use_selector_loop_on_windows()
    asyncio.run(main(int(sys.argv[1]), sys.argv[2]))
