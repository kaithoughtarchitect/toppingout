"""Re-check the recipes on wiki/agent-setup.md against the INSTALLED deepagents (no API calls; scripted fake model).

Run after vendoring a new deepagents version, in an env with deepagents + langgraph installed:
    python scripts/check_recipes.py
Every line should match the expected value in its comment; if one changes, update wiki/agent-setup.md.

Expected on 0.7.29 (re-run 2026-10-21; unchanged from 0.7.20):
    T4 execute bound? False
    T1 memory write: success      | T1 outside-memory write: error (permission denied)
    T2 eviction under write-deny: success (saved to filesystem)
    T3 store key stripped: True | prefixed key: False | other workspace sees it: False
    T5 display-name namespace: ValueError
    T6 default: v1 (frozen)       | T6 FreshMemory: v2 (reloaded)
"""
import re
from dataclasses import dataclass

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolCall
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from deepagents import create_deep_agent, FilesystemPermission, MemoryMiddleware
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from deepagents.backends.utils import create_file_data

BOUND = []


class Fake(GenericFakeChatModel):
    def bind_tools(self, tools, **kw):
        BOUND.append(sorted(getattr(t, "name", None) or t.get("name") or t.get("function", {}).get("name") for t in tools))
        return self


@dataclass(frozen=True)
class Ctx:
    workspace_id: str


@tool
def big(runtime: ToolRuntime[Ctx]) -> str:
    """Return a huge read-only report for the current workspace."""
    return f"workspace={runtime.context.workspace_id}\n" + ("x" * 100 + "\n") * 1200  # ~121k chars


def tc(name, args, i):
    return AIMessage(content="", tool_calls=[ToolCall(name=name, args=args, id=i)])


def build(script, store, memory_mw=None):
    backend = CompositeBackend(
        default=StateBackend(),
        routes={"/memories/": StoreBackend(namespace=lambda rt: ("app", "mem", rt.context.workspace_id), store=store)},
    )
    kw = dict(middleware=[memory_mw(backend=backend, sources=["/memories/AGENTS.md"])]) if memory_mw else {}
    return create_deep_agent(
        model=Fake(messages=iter(script)), tools=[big], context_schema=Ctx,
        memory=["/memories/AGENTS.md"], backend=backend, store=store, checkpointer=InMemorySaver(),
        permissions=[
            FilesystemPermission(operations=["write"], paths=["/memories/**"], mode="allow"),
            FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
        ],
        **kw,
    )


def run(agent, text, tid, cid):
    return agent.invoke({"messages": [{"role": "user", "content": text}]},
                        config={"configurable": {"thread_id": tid}}, context=Ctx(cid))


def tool_msgs(r):
    return [(m.name, m.status, m.content[:90].replace("\n", " ")) for m in r["messages"] if m.type == "tool"]


store = InMemoryStore()
# T1-T4: allow/deny recipe, no execute tool, eviction under write-deny, stripped store key
a = build([
    tc("write_file", {"file_path": "/memories/AGENTS.md", "content": "- prefers short answers"}, "c1"),
    tc("write_file", {"file_path": "/notes.md", "content": "scratch"}, "c2"),
    tc("big", {}, "c3"),
    AIMessage(content="done"),
], store)
r = run(a, "go", "t1", "workspace-a")
tm = tool_msgs(r)
print("T4 execute bound?", any("execute" in b for b in BOUND), "| tools:", BOUND[0])
print("T1 memory write:", tm[0])
print("T1 outside-memory write:", tm[1])
print("T2 eviction under write-deny:", tm[2])
print("T3 store key stripped:", store.get(("app", "mem", "workspace-a"), "/AGENTS.md") is not None,
      "| prefixed key:", store.get(("app", "mem", "workspace-a"), "/memories/AGENTS.md") is not None)
print("T3 other workspace sees it:", store.get(("app", "mem", "workspace-b"), "/AGENTS.md") is not None)

RESULTS = {}
RESULTS["T4 execute tool exposed"] = any("execute" in b for b in BOUND)
RESULTS["T1 memory write status"] = tm[0][1]
RESULTS["T1 outside-memory write status"] = tm[1][1]
RESULTS["T2 eviction under write-deny status"] = tm[2][1]
RESULTS["T3 store key stripped"] = store.get(("app", "mem", "workspace-a"), "/AGENTS.md") is not None
RESULTS["T3 prefixed key present"] = store.get(("app", "mem", "workspace-a"), "/memories/AGENTS.md") is not None
RESULTS["T3 other workspace sees it"] = store.get(("app", "mem", "workspace-b"), "/AGENTS.md") is not None

# T5: namespace with a display name
try:
    run(build([AIMessage(content="hi")], store), "hi", "t9", "My Workspace 1")
    print("T5 display-name namespace: accepted (no memory read?)")
    RESULTS["T5 display-name namespace"] = "accepted"
except Exception as e:
    print("T5 display-name namespace:", type(e).__name__, str(e)[:100])
    RESULTS["T5 display-name namespace"] = type(e).__name__


# T6: memory frozen per thread vs FreshMemory reload
class FreshMemory(MemoryMiddleware):
    @property
    def name(self):
        return "MemoryMiddleware"

    def before_agent(self, state, runtime, config):
        return super().before_agent({k: v for k, v in state.items() if k != "memory_contents"}, runtime, config)


for label, mw in (("default", None), ("FreshMemory", FreshMemory)):
    s = InMemoryStore()
    s.put(("app", "mem", "c1"), "/AGENTS.md", create_file_data("- v1 prefers long answers"))
    ag = build([AIMessage(content="a"), AIMessage(content="b")], s, mw)
    run(ag, "one", "tt", "c1")
    s.put(("app", "mem", "c1"), "/AGENTS.md", create_file_data("- v2 prefers short answers"))  # UI edit
    run(ag, "two", "tt", "c1")
    mem = ag.get_state({"configurable": {"thread_id": "tt"}}, ).values.get("memory_contents")
    print(f"T6 {label}: memory after UI edit in same thread =", mem)
    RESULTS[f"T6 {label} sees UI edit"] = "v2" in str(mem)

# --- self-check (CI): every documented behaviour must hold on the installed deepagents ---
EXPECTED = {
    "T4 execute tool exposed": False,
    "T1 memory write status": "success",
    "T1 outside-memory write status": "error",
    "T2 eviction under write-deny status": "success",
    "T3 store key stripped": True,
    "T3 prefixed key present": False,
    "T3 other workspace sees it": False,
    "T5 display-name namespace": "ValueError",
    "T6 default sees UI edit": False,
    "T6 FreshMemory sees UI edit": True,
}
bad = [(k, v, RESULTS.get(k, "<missing>")) for k, v in EXPECTED.items() if RESULTS.get(k, "<missing>") != v]
for k, want, got in bad:
    print(f"MISMATCH {k}: expected {want!r}, got {got!r}")
print(("FAIL" if bad else "PASS") + f": {len(EXPECTED) - len(bad)}/{len(EXPECTED)} recipe behaviours hold")
raise SystemExit(1 if bad else 0)
