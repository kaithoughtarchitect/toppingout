---
title: MCP tools (MCPAdapter)
id: mcp
type: how-to
status: sourced
product: sdk
keywords: MCP, Model Context Protocol, MCPAdapter, langchain.mcp, langchain[mcp], FastMCP, MCP server tools, langchain-mcp-adapters, MultiServerMCPClient, list_tools, mcpServers, stdio, streamable http, connect MCP
read_when: Read when connecting a deep agent to an MCP server or seeing old MultiServerMCPClient examples.
updated: 2026-10-21
sources_hash: 128ecea1a882
---

# MCP tools (MCPAdapter)

One-line truth: Deep Agents has no MCP code of its own; you load MCP server tools with LangChain's `langchain.mcp.MCPAdapter` (FastMCP-based, beta, `langchain[mcp]>=1.4.0`) and pass the resulting list to `create_deep_agent(tools=...)` like any other tool.

## Install

```bash
pip install "langchain[mcp]"      # or: uv add "langchain[mcp]"  (pulls in FastMCP)
```

- `langchain.mcp` requires `langchain[mcp]>=1.4.0`, is **beta**, and emits `LangChainBetaWarning` once per process on import. API may change.
- `deepagents` 0.7.29 requires `langchain>=1.4.6,<2`, so the namespace is available once the `mcp` extra is installed.
- Replaces the older `langchain-mcp-adapters` package (`MultiServerMCPClient`); migrate if you see that in old examples.

## Minimal pattern

```python
import asyncio
from deepagents import create_deep_agent
from langchain.mcp import MCPAdapter

async def main():
    config = {"mcpServers": {"my_server": {"url": "http://localhost:8000/mcp"}}}
    async with MCPAdapter(config) as adapter:
        tools = await adapter.list_tools()          # -> LangChain tools
        agent = create_deep_agent(model="anthropic:claude-sonnet-4-6", tools=tools)
        await agent.ainvoke(
            {"messages": [{"role": "user", "content": "Use the MCP server to help me."}]},
            config={"configurable": {"thread_id": "1"}},
        )

asyncio.run(main())
```

- `list_tools()` is async; MCP tools are async tools, so drive the agent with `ainvoke` / `astream`.
- The tools hold the client, so the agent stays usable after the `async with` block exits (per docs).
- MCP tools merge with the built-in harness tools; they are inherited by declarative subagents that don't declare their own `"tools"` (see [[tools]], [[subagents]]).

## Targets (transport is inferred)

```python
from pathlib import Path
from langchain.mcp import MCPAdapter

MCPAdapter("https://example.com/mcp")     # str: must be http(s) URL -> streamable HTTP
MCPAdapter(Path("weather_server.py"))     # Path: launched as stdio subprocess (one per adapter)
MCPAdapter(server)                        # in-process FastMCP instance (tests; no socket)
MCPAdapter({"mcpServers": {...}})         # MCPConfig dict: several servers behind one adapter
# also: a fastmcp StreamableTransport object, or a prebuilt fastmcp.Client
```

Public no-auth example server: `https://docs.langchain.com/mcp` (tools `search_docs_by_lang_chain`, `query_docs_filesystem_docs_by_lang_chain`, `submit_feedback`).

The Deep Agents docs no longer have their own MCP page: the old URL redirects to LangChain's MCP guide (`/oss/python/langchain/mcp/*`), which shows `create_agent` but applies unchanged to `create_deep_agent`. Auth (bearer, OAuth 2.1, per-user), connections, stateful sessions, caching and protocol eras are on its sub-pages (`auth`, `connections`); this reference only fetches the overview and the tools page.

## Where MCP shows up elsewhere

- Deep Agents Code (`dcode`) loads MCP servers from its own config — see [[dcode-extending]].
- Managed Deep Agents attach MCP connectors / expose an MCP endpoint — see [[managed-capabilities]].
- MCP is "agent calls external tools". It is not ACP (editor ↔ agent), AG-UI (frontend ↔ agent) or A2A (agent ↔ agent) — see [[protocols]].
- MCP tools can return multimodal content; see [[multimodal]] for how unsupported blocks are handled.

## Gotchas

- A `str` target must look like an `http(s)` URL. FastMCP would otherwise test a string as a filesystem path first and could launch a `.py`/`.js` file as a subprocess; `MCPAdapter` rejects non-URL strings. Use `Path(...)` for stdio.
- `langchain.mcp` is beta; pin `langchain` and expect breaking changes (see [[versions]]).
- The tools page example builds the agent inside the context manager; if you build the agent at import time (e.g. `langgraph.json` graph), you need an async graph factory or to load tools before the graph is constructed.
- Nothing about MCP is in the `deepagents` 0.7.29 package source; all behavior here is LangChain's (docs-sourced).

## Sources
- `../sources/docs/oss/python/langchain/mcp/index.md` (the old Deep Agents MCP page redirects here)
- `../sources/docs/oss/python/langchain/mcp/tools.md`
- `../sources/docs/oss/python/deepagents/tools.md` (MCP tools section)
- `../sources/package/deepagents-0.7.29.dist-info/METADATA` (langchain version pin)

## See also
- [[index]]
- [[tools]]
- [[create-deep-agent]]
- [[subagents]]
- [[protocols]]
- [[dcode-extending]]
- [[managed-capabilities]]
- [[multimodal]]
- [[versions]]
