"""Build the agent. The checked recipe from deepagents-ref/wiki/agent-setup.md, as code.

Rename per product: APP (the namespace root) and, if you like, `workspace_id`
(whatever your agent keeps memory separate by: a user, a project, a customer).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from langchain.agents.middleware import ModelRetryMiddleware
from deepagents import FilesystemPermission, MemoryMiddleware, create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

APP = "app"                                     # namespace root; rename to your product
MODEL = "openrouter:openai/gpt-6-luna"          # any provider:model string (deepagents-ref/wiki/models.md)
MEMORY_FILE = "/memories/AGENTS.md"
SYSTEM_PROMPT = """You are a helpful assistant with persistent memory.
Your long-term memory is in /memories/. When the user states a lasting preference or corrects one,
update /memories/AGENTS.md with edit_file (or write_file if it doesn't exist yet)."""

_SLUG = re.compile(r"^[A-Za-z0-9\-_.@+:~]+$")


@dataclass(frozen=True)
class Ctx:
    """Per-run context. Pass on every call: agent.invoke(..., context=Ctx(workspace_id))."""

    workspace_id: str  # a slug or UUID, never a display name (spaces raise ValueError in the store)

    def __post_init__(self) -> None:
        if not _SLUG.match(self.workspace_id):
            raise ValueError(f"workspace_id is not store-safe: {self.workspace_id!r}")


def memory_namespace(workspace_id: str) -> tuple[str, ...]:
    return (APP, "mem", workspace_id)


def _ns(rt) -> tuple[str, ...]:
    # Fails closed: no context -> AttributeError, never a shared namespace.
    return memory_namespace(rt.context.workspace_id)


class FreshMemory(MemoryMiddleware):
    """Re-read memory files at the start of every run, so UI edits reach an open thread."""

    @property
    def name(self) -> str:
        return "MemoryMiddleware"  # same name -> replaces the built-in slot in place

    def before_agent(self, state, runtime, config):
        return super().before_agent({k: v for k, v in state.items() if k != "memory_contents"}, runtime, config)

    async def abefore_agent(self, state, runtime, config):
        return await super().abefore_agent({k: v for k, v in state.items() if k != "memory_contents"}, runtime, config)


def build_agent(*, tools, model=MODEL, store=None, checkpointer=None, system_prompt=SYSTEM_PROMPT):
    """Compiled deep agent: memory under /memories/ per workspace, no shell, writes only to memory.

    store/checkpointer: durable ones from persistence.open_persistence(); None when a host
    (LangGraph Agent Server) supplies them.
    """
    backend = CompositeBackend(
        default=StateBackend(),  # scratch + offloads; not a sandbox -> no execute tool
        routes={"/memories/": StoreBackend(namespace=_ns, store=store)},
    )
    sources = [MEMORY_FILE]
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        memory=sources,
        backend=backend,
        store=store,
        checkpointer=checkpointer,
        context_schema=Ctx,
        permissions=[  # first match wins, default allow; file tools only
            FilesystemPermission(operations=["write"], paths=["/memories/**"], mode="allow"),
            FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
        ],
        middleware=[ModelRetryMiddleware(max_retries=3), FreshMemory(backend=backend, sources=sources)],
    )
