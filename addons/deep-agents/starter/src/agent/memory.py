"""Read and write the agent's memory files from app code (a UI, a seed, a migration).

App code talks to the STORE, never to StoreBackend (its namespace callable needs a graph run).
Keys have the route prefix stripped: agent path /memories/AGENTS.md is store key /AGENTS.md.
The store keeps no history; for an audit trail use deepagents-ref/examples/history_backend.py.
"""

from __future__ import annotations

from pathlib import Path

from deepagents.backends.utils import create_file_data

from .agent import Ctx, memory_namespace

SEED = Path(__file__).with_name("memory_seed.md")


def _key(path: str) -> str:
    return path.removeprefix("/memories")


class MemoryService:
    def __init__(self, store):
        self.store = store

    def _ns(self, workspace_id: str) -> tuple[str, ...]:
        return memory_namespace(Ctx(workspace_id).workspace_id)  # validates the slug

    async def list(self, workspace_id: str) -> list[str]:
        items = await self.store.asearch(self._ns(workspace_id), limit=1000)  # past `limit` is silently dropped
        return sorted("/memories" + it.key for it in items)

    async def read(self, workspace_id: str, path: str) -> str | None:
        it = await self.store.aget(self._ns(workspace_id), _key(path))
        return it.value["content"] if it else None

    async def write(self, workspace_id: str, path: str, text: str) -> None:
        await self.store.aput(self._ns(workspace_id), _key(path), create_file_data(text))

    async def seed_if_missing(self, workspace_id: str, path: str = "/memories/AGENTS.md") -> bool:
        if await self.read(workspace_id, path) is None:
            await self.write(workspace_id, path, SEED.read_text(encoding="utf-8"))
            return True
        return False
