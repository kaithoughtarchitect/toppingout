"""Durable checkpointer + store: SQLite locally, Postgres when AGENT_DB_URL is set.

From deepagents-ref/wiki/persistence.md (both branches ran through a restart on 2026-09-29).
Keep the context open for the app's whole life: the connections close when it exits.
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path


def use_selector_loop_on_windows() -> None:
    """Async psycopg (Postgres) can't run on Windows' default ProactorEventLoop. Call before asyncio.run()."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def open_persistence(data_dir: str | os.PathLike = "data"):
    """Yield (checkpointer, store). Postgres if AGENT_DB_URL is set, else SQLite files in data_dir."""
    uri = os.environ.get("AGENT_DB_URL")
    if uri:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from langgraph.store.postgres.aio import AsyncPostgresStore

        async with AsyncPostgresSaver.from_conn_string(uri) as cp, AsyncPostgresStore.from_conn_string(uri) as st:
            await cp.setup()
            await st.setup()
            yield cp, st
    else:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from langgraph.store.sqlite.aio import AsyncSqliteStore

        d = Path(data_dir).resolve()  # absolute: the working directory must not matter
        d.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(str(d / "checkpoints.db")) as cp, \
                AsyncSqliteStore.from_conn_string(str(d / "store.db")) as st:
            await cp.setup()
            await st.setup()
            yield cp, st
