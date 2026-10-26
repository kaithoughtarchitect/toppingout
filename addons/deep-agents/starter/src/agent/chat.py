"""Talk to the agent in the terminal. Memory and conversation survive restarts.

    python -m agent.chat [--workspace demo] [--conversation main]

Needs OPENROUTER_API_KEY (in .env or the environment). Data goes to ./data (SQLite),
or to Postgres if AGENT_DB_URL is set.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from .agent import Ctx, build_agent
from .memory import MemoryService
from .persistence import open_persistence, use_selector_loop_on_windows
from .tools import TOOLS


def load_dotenv(path: Path = Path(".env")) -> None:
    """Minimal .env loader; values already in the environment win."""
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", default="demo")
    p.add_argument("--conversation", default="main")
    p.add_argument("--message", help="send one message and exit (non-interactive)")
    args = p.parse_args()
    ctx = Ctx(args.workspace)
    config = {"configurable": {"thread_id": f"{ctx.workspace_id}:{args.conversation}"}}  # one thread per (workspace, conversation)

    async with open_persistence() as (checkpointer, store):
        await MemoryService(store).seed_if_missing(ctx.workspace_id)
        agent = build_agent(tools=TOOLS, store=store, checkpointer=checkpointer)

        async def turn(text: str) -> None:
            result = await agent.ainvoke({"messages": [{"role": "user", "content": text}]}, config=config, context=ctx)
            print(f"agent> {result['messages'][-1].content}\n")

        if args.message:
            await turn(args.message)
            return
        print(f"workspace={ctx.workspace_id} thread={config['configurable']['thread_id']}  (Ctrl+C to quit)\n")
        while True:
            try:
                text = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if text:
                await turn(text)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):  # Windows cp1252 console: a ✓ or emoji in a reply would crash print()
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv()
    use_selector_loop_on_windows()
    asyncio.run(main())
