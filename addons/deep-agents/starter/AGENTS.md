# <PRODUCT>

Replace `<PRODUCT>` and this line with one paragraph on what the agent does.

## Code

The agent lives in `src/agent/` (`build_agent` in `agent.py`), and tests in `tests/` (run with `foreman/test-adapter.sh`). Talk to it: `PYTHONPATH=src .venv/Scripts/python -m agent.chat` (macOS/Linux: `.venv/bin/python`).

## Deep Agents context

This project runs on the LangChain Deep Agents Python SDK. Before you plan, build or review anything that touches `deepagents`, LangChain or LangGraph:

1. **Layer 1:** `deepagents-ref/AGENTS.md`, a reference checked against `deepagents` 0.7.29. Read it first; it wins every conflict.
2. **Layer 2:** the `docs-langchain` MCP server (in `.mcp.json`), which searches all LangChain docs live. Use it only for what layer 1's `wiki/gaps.md` sends you to.

Never answer Deep Agents questions from memory. Shortcut: `/deep` loads this route (skill in `.claude/skills/deep/`; also in `.agents/skills/deep/` if a builder reads that folder).

## Working method: Topping Out

Work runs through Topping Out (method documents in `foreman/method/`; skills `/f-*` in `.claude/skills/`). One ticket = one job = one branch. Records live under `foreman/` (single-repo mode); product code never goes there. Environment, gates and test adapter: `foreman/REPO-PROFILE-<product>.md`. The profile's framework check is `/deep`.
