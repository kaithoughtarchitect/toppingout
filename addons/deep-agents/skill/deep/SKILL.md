---
name: deep
description: Load the Deep Agents reference before planning, writing, reviewing, testing or debugging anything that uses deepagents, create_deep_agent, LangChain agents, LangGraph (checkpointers, stores, threads, interrupts, streaming), backends, subagents, agent memory, skills or middleware. Use for any work on this repo's agent, and as the framework check in Topping Out's ground investigation. Layer 1 is deepagents-ref/ (checked against deepagents 0.7.29 code); layer 2 is the docs-langchain MCP server.
---

# Deep Agents reference

Never answer Deep Agents, LangChain or LangGraph questions from memory: this API changed a lot in 0.7.

1. Read `deepagents-ref/AGENTS.md`. It holds the layer map, the find order, the layer-2 usage and the review checklist.
2. Read `deepagents-ref/wiki/constitution.md`. For agent work, also read `deepagents-ref/wiki/agent-setup.md`, the checked setup.
3. Then follow the section of `AGENTS.md` that fits the task:
   - **Plan or design:** `wiki/decisions.md`, then `wiki/anti.md`, then the topic page.
   - **Build:** the topic page's `## Quick reference` and `## Gotchas`. Quote the gotcha that applies. For tests, `wiki/testing.md`.
   - **Debug:** the Symptom → cause table in `wiki/anti.md`.
   - **Review:** the review checklist in `AGENTS.md`.
   - **Unknown term or symbol:** `wiki/lookup.md`.
   - **Not in layer 1:** `wiki/gaps.md`, then layer 2, the `docs-langchain` MCP. Put "python" in the query, read the page by the exact path returned, and label the answer "not checked against 0.7.29".
4. After writing code, run `python deepagents-ref/scripts/check_imports.py <files>` and do the rest of the verify step in `AGENTS.md`.
5. Cite the wiki page or source path behind each claim. Where layer 2 and layer 1 disagree, layer 1 wins.
