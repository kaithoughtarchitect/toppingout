import datetime as dt
import uuid
from deepagents.backends import StoreBackend


class HistoryStoreBackend(StoreBackend):
    """StoreBackend that logs every memory change to a sibling "hist" namespace.

    Live files: ("app", "mem", workspace_id). History: ("app", "hist", workspace_id).
    The history namespace is never routed, so the agent cannot read or alter it.
    """

    def _log(self, path: str, **entry) -> None:
        store, ns = self._get_store(), self._get_namespace()
        now = dt.datetime.now(dt.timezone.utc)
        key = f"{path}@{now.strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:6]}"
        store.put((*ns[:-2], "hist", ns[-1]), key, {"path": path, "ts": now.isoformat(), **entry})

    def _current(self, path: str) -> str | None:
        item = self._get_store().get(self._get_namespace(), path)
        return item.value["content"] if item else None

    def write(self, file_path, content):
        before = self._current(file_path)
        res = super().write(file_path, content)
        if res.error is None:
            self._log(file_path, op="write", before=before, after=content)
        return res

    def edit(self, file_path, old_string, new_string, replace_all=False):
        before = self._current(file_path)
        res = super().edit(file_path, old_string, new_string, replace_all)
        if res.error is None:
            self._log(file_path, op="edit", before=before, after=self._current(file_path),
                      old_string=old_string, new_string=new_string)
        return res

    def delete(self, file_path):
        before = self._current(file_path)
        res = super().delete(file_path)
        if res.error is None:
            self._log(file_path, op="delete", before=before, after=None)
        return res

    # --- async (used by ainvoke / astream) ---

    async def _alog(self, path: str, **entry) -> None:
        store, ns = self._get_store(), self._get_namespace()
        now = dt.datetime.now(dt.timezone.utc)
        key = f"{path}@{now.strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:6]}"
        await store.aput((*ns[:-2], "hist", ns[-1]), key, {"path": path, "ts": now.isoformat(), **entry})

    async def _acurrent(self, path: str) -> str | None:
        item = await self._get_store().aget(self._get_namespace(), path)
        return item.value["content"] if item else None

    async def awrite(self, file_path, content):
        before = await self._acurrent(file_path)
        res = await super().awrite(file_path, content)
        if res.error is None:
            await self._alog(file_path, op="write", before=before, after=content)
        return res

    async def aedit(self, file_path, old_string, new_string, replace_all=False):
        before = await self._acurrent(file_path)
        res = await super().aedit(file_path, old_string, new_string, replace_all)
        if res.error is None:
            await self._alog(file_path, op="edit", before=before, after=await self._acurrent(file_path),
                             old_string=old_string, new_string=new_string)
        return res

    async def adelete(self, file_path):
        before = await self._acurrent(file_path)
        res = await super().adelete(file_path)
        if res.error is None:
            await self._alog(file_path, op="delete", before=before, after=None)
        return res
