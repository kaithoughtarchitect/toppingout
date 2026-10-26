"""Prove a restart: pass 1 writes + edits memory through ainvoke; pass 2 is a FRESH process.

Needs the repo venv (requirements.txt). No API calls (scripted fake model).
    python deepagents-ref/scripts/check_persistence.py sqlite 1
    python deepagents-ref/scripts/check_persistence.py sqlite 2
Postgres (e.g. docker run -d --rm --name pg -e POSTGRES_PASSWORD=test -p 55499:5432 postgres:17):
    set AGENT_TEST_PG=postgresql://postgres:test@localhost:55499/postgres, then the same with "postgres".

Expected in pass 2 (ran on 0.7.20, 2026-09-30, both SQLite and Postgres 17; re-run on 0.7.29, 2026-10-21, SQLite only, Postgres not re-run on 0.7.29):
    live: - I prefer short answers, with sources
    history: [('write', None), ('edit', '- I prefer detailed answers')]
    messages in thread: 8     (6 from pass 1 + 2 new -> the conversation survived)
Delete persist_test/ (SQLite) or the container before re-running pass 1.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples"))
from dataclasses import dataclass
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolCall
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend
from history_backend import HistoryStoreBackend

KIND, PASS = sys.argv[1], sys.argv[2]
DATA = os.path.abspath("persist_test")
PG = os.environ.get("AGENT_TEST_PG", "postgresql://postgres:test@localhost:55499/postgres")

class Fake(GenericFakeChatModel):
    def bind_tools(self, t, **k): return self

@dataclass
class Ctx: workspace_id: str

def ns(rt): return ("app", "mem", rt.context.workspace_id)

async def run(cp, st):
    await cp.setup(); await st.setup()
    script = ([AIMessage(content="", tool_calls=[ToolCall(name="write_file", args={"file_path": "/memories/AGENTS.md", "content": "- I prefer detailed answers"}, id="a")]),
               AIMessage(content="", tool_calls=[ToolCall(name="edit_file", args={"file_path": "/memories/AGENTS.md", "old_string": "detailed answers", "new_string": "short answers, with sources"}, id="b")]),
               AIMessage(content="saved")] if PASS == "1" else [AIMessage(content="still here")])
    agent = create_deep_agent(model=Fake(messages=iter(script)), context_schema=Ctx, store=st, checkpointer=cp,
                              memory=["/memories/AGENTS.md"],
                              backend=CompositeBackend(default=StateBackend(), routes={"/memories/": HistoryStoreBackend(namespace=ns)}))
    cfg = {"configurable": {"thread_id": "workspace-a:conv-1"}}
    r = await agent.ainvoke({"messages": [{"role": "user", "content": "hi"}]}, config=cfg, context=Ctx("workspace-a"))
    print(f"[{KIND} pass {PASS}] tools:", [(m.name, m.status) for m in r["messages"] if m.type == "tool"])
    live = await st.aget(("app", "mem", "workspace-a"), "/AGENTS.md")
    hist = sorted(await st.asearch(("app", "hist", "workspace-a"), limit=100), key=lambda i: i.key)
    print(f"[{KIND} pass {PASS}] live:", live.value["content"] if live else None)
    print(f"[{KIND} pass {PASS}] history:", [(h.value["op"], h.value["before"]) for h in hist])
    print(f"[{KIND} pass {PASS}] messages in thread:", len(r["messages"]), "| memory in prompt:", r.get("memory_contents"))

async def main():
    if KIND == "sqlite":
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from langgraph.store.sqlite.aio import AsyncSqliteStore
        os.makedirs(DATA, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(f"{DATA}/cp.db") as cp, AsyncSqliteStore.from_conn_string(f"{DATA}/st.db") as st:
            await run(cp, st)
    else:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from langgraph.store.postgres.aio import AsyncPostgresStore
        async with AsyncPostgresSaver.from_conn_string(PG) as cp, AsyncPostgresStore.from_conn_string(PG) as st:
            await run(cp, st)

if sys.platform == "win32":  # psycopg async can't use the default ProactorEventLoop
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
