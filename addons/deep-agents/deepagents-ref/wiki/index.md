---
title: Map
id: index
type: map
status: code
product: all
keywords: index, map, table of contents, where to start, catalog
read_when: Read after the constitution to pick the one page for your question.
updated: 2026-10-21
---

# Map

One line per page, keywords in italics. Can't pick? Search [[lookup]] for your term or symbol. Not listed → [[gaps]]. `(docs only)` = not checked against package code.

## Start here

- [[agent-setup]] — the full checked your agent setup: model, backend, permissions, Memory tab, workspaces, leakage tests
  _agent setup, reference setup, workspace, workspace_id, per-workspace memory, Memory tab, MemoryService, UI reads memory, read-only except memory, allow then deny, thread per workspace, workspace switch, leakage test, FreshMemory, GPT-6 Luna_
- [[constitution]] — 13 rules ordered by cost of error; read first, every time
  _rules, must know, mental model, core rules, gotchas, deepagents basics_
- [[decisions]] — which piece to reach for: product, backend, memory vs skills, subagent kind
  _decision, which to use, choose, SDK vs dcode vs managed, StateBackend vs StoreBackend, sandbox vs interpreter, subagent vs skill, tradeoff, recommendation, default choice, when to use_
- [[anti]] — stale doc examples and wrong mental models, with the 0.7.29 reality
  _anti-patterns, wrong mental model, stale docs, doesn't work, TypeError, StoreBackend namespace, backend lambda, write_todos missing, virtual_mode, task args, pre-0.7 docs, common mistakes, breaking changes_
- [[lookup]] — term, class, function or parameter → the page that explains it (generated symbol table)
  _lookup, find, where is, glossary, symbol, import, class, function, parameter, synonym_
- [[gaps]] — what this folder does not cover, with the live URL for each — check before answering from memory (docs only)
  _not found, missing, not covered, testing, unit test, fake model, token usage, cost tracking, tracing, observability, MCP auth, OAuth, checkpointer classes, PostgresSaver, SqliteSaver, TodoListMiddleware params, LangGraph, create_agent_
- [[versions]] — 0.7.29 deps and extras, 0.7.0 breaking changes, public API map
  _deepagents version, changelog, breaking changes, 0.7.0, upgrade, migration, dependencies, extras, public API, __all__, deprecated, BASE_AGENT_PROMPT, virtual_mode, write_file overwrite, TodoListMiddleware removed, what changed_
- [[sources]] — raw docs + vendored package; ground-truth order; refresh rule (docs only)
  _sources, raw docs, ground truth, package source, deepagents 0.7.29, wheel, docs mirror, changelog, fetch_docs, where to look, citations, refresh docs_
- [[do-not]] — never invent an API; never answer from memory; never mix the three products
  _do not, never, hard rules, guardrails, invent API, training memory, stale answer, rules for agents, constraints, no guessing, cite sources, version pinning_

## Core harness

- [[harness]] — what Deep Agents is, what is default vs opt-in in 0.7.29, install, minimal agent
  _deep agents harness, agent harness, create_agent, middleware stack, built-in tools, virtual filesystem, StateBackend, write_todos missing, planning removed, execute tool, install deepagents, pip install deepagents, task tool, prompt caching, LangGraph graph_
- [[create-deep-agent]] — full verified signature, every parameter, return type, assembly steps
  _create_deep_agent, create deep agent, signature, parameters, kwargs, system_prompt, interrupt_on, response_format, structured output, state_schema, context_schema, checkpointer, store, backend, subagents, recursion_limit_
- [[models]] — `provider:model` strings, `init_chat_model`, OpenRouter, provider and harness profiles
  _model, provider:model, init_chat_model, choose model, switch model, OpenRouter, Ollama, Bedrock, Azure OpenAI, harness profile, HarnessProfile, provider profile, ProviderProfile, register_harness_profile, register_provider_profile, use_responses_api, excluded_tools, runtime model switching_
- [[customization]] — every knob in one place: prompt composition, tools, middleware, backends, output
  _customize agent, system prompt, prompt composition, custom middleware, override middleware, SummarizationMiddleware, SkillsMiddleware, structured output, response_format, subagents, backends, human in the loop, HITL, interrupt_on, going fully custom, tools, memory, skills_
- [[middleware]] — exact default stack order (main + subagent), replace-by-name, build by hand
  _middleware stack, middleware order, AgentMiddleware, _ParentNotifierMiddleware, SkillsMiddleware placement, custom middleware, wrap_tool_call, wrap_model_call, before_agent, PatchToolCallsMiddleware, prompt caching, FilesystemMiddleware, SubAgentMiddleware, SummarizationMiddleware, excluded_middleware, remove middleware, UnsupportedContentMiddleware_
- [[products]] — LangChain vs LangGraph vs Deep Agents; vs Claude Agent SDK; from-scratch walkthrough (docs only)
  _Deep Agents vs LangChain, Deep Agents vs LangGraph, Claude Agent SDK comparison, create_agent, harness vs framework vs runtime, which one to use, when to use deep agents, build harness yourself, CrewAI, Temporal, Manus, agent framework choice_

## Filesystem

- [[backends]] — State/Store/Filesystem/Composite/LocalShell/ContextHub: constructors, routing, custom backends
  _backend, backends, offload_binary_content, blobs, StateBackend, StoreBackend, CompositeBackend, FilesystemBackend, LocalShellBackend, ContextHubBackend, BackendProtocol, namespace, virtual_mode, long-term memory storage, persistent storage, where do files live, custom backend, route prefix, virtual filesystem_
- [[filesystem-tools]] — exact tools, args, limits (read_file 100 lines, literal grep), result eviction
  _filesystem tools, file tools, grep_exclude_dirs, offload_binary_content, ls, read_file, write_file, edit_file, delete, glob, grep, execute, FilesystemMiddleware, tool_token_limit_before_evict, large_tool_results, grep regex, read file limit, tool eviction, big tool output_
- [[permissions]] — `FilesystemPermission`, first-match-wins, default allow, interrupt mode, sandbox clash
  _permissions, FilesystemPermission, read-only agent, deny write, allow deny, path restrictions, restrict paths, approval, interrupt mode, HITL, human in the loop, first match wins, access control, guardrails_
- [[sandboxes]] — `execute`, LangSmithSandbox, providers, custom `BaseSandbox`, lifecycle, security
  _grep_exclude_dirs, sandbox, sandboxes, execute tool, run code, shell access, BaseSandbox, LangSmithSandbox, DaytonaSandbox, ModalSandbox, E2BSandbox, RunloopSandbox, isolated environment, run shell commands, install packages, SandboxBackendProtocol_
- [[interpreters]] — QuickJS `eval`: tools from code, `task()`, persistence, bypasses `interrupt_on` (docs only)
  _interpreter, code interpreter, CodeInterpreterMiddleware, QuickJS, eval tool, JavaScript REPL, programmatic tool calling, PTC, ptc, langchain_quickjs, run code in loop, orchestrate tools in code, REPL, dynamic subagents_

## Delegation and control

- [[planning]] — `write_todos` is opt-in since 0.7: add `TodoListMiddleware`
  _write_todos, TodoListMiddleware, todo list, planning tool, task planning, todos state, progress tracking, plan and track tasks, write_todos missing, opt-in planning, Codex harness profile_
- [[subagents]] — `task(description, subagent_type)`, SubAgent/CompiledSubAgent, inheritance, what returns
  _subagent, sub-agent, sub agent, task tool, SubAgent, CompiledSubAgent, general-purpose subagent, context quarantine, delegate to specialist, fork mode, subagent_type, SubAgentMiddleware, parallel fan-out_
- [[dynamic-subagents]] — fan out from code via interpreter `task()` (docs only)
  _dynamic subagents, dynamic sub-agent, task() in interpreter, CodeInterpreterMiddleware, QuickJS, Promise.all, fan-out, RLM, recursive subagents, langchain_quickjs, responseSchema, eval, batch dispatch_
- [[async-subagents]] — background subagents on Agent Protocol servers, five `*_async_task` tools
  _async subagent, async sub-agent, background task, AsyncSubAgent, start_async_task, Agent Protocol, graph_id, long-running agent, non-blocking subagent, LangSmith Deployment, remote subagent, cancel task, update task, TaskEvent, task notification, deepagents_notification, waiting status, fork mode, parent_thread_id_
- [[human-in-the-loop]] — `interrupt_on`, approve/edit/reject/respond, resume with `Command`
  _human in the loop, human-in-the-loop, HITL, approval, approve edit reject, interrupt_on, InterruptOnConfig, HumanInTheLoopMiddleware, interrupt, Command resume, allowed_decisions, confirm before tool runs, pause for review, __interrupt___
- [[rubric]] — `RubricMiddleware` grader loop until done
  _rubric, RubricMiddleware, LLM-as-judge, grader, grading loop, self-check, verify output, needs_revision, max_iterations, quality gate, evaluate before finish, definition of done, on_evaluation_

## Memory and context

- [[memory]] — AGENTS.md via `memory=` + Store routes; per-user/workspace scoping; store keys a UI reads; once-per-thread load
  _memory, long-term memory, remember across sessions, cross-thread memory, persistent memory, AGENTS.md, MemoryMiddleware, memory=, /memories/, StoreBackend, per-user memory, user preferences, short-term memory, agent memory, store namespace_
- [[persistence]] — checkpointer vs store; what survives a restart; two-process restart demo
  _persistence, checkpointer, store, remember across sessions, long-term memory, InMemorySaver, SqliteSaver, PostgresSaver, PostgresStore, StoreBackend, thread_id, survive restart, durable state_
- [[memory-history]] — no built-in edit history; a checked `HistoryStoreBackend` that logs every change to a separate namespace
  _memory history, edit history, audit trail, revision, versioning, undo, diff, original wording, correction, superseded preference, HistoryStoreBackend_
- [[skills]] — SKILL.md format, progressive disclosure, `skills=` sources, inheritance
  _skills, SKILL.md, SkillsMiddleware, skills=, pinned_skills, pin a skill, include_tools, skill tools, SkillToolResolver, disclosed_skill_tool_names, progressive disclosure, agent skills, reusable procedures, playbooks, skills_metadata, reload skills, task-specific instructions, skill directory, allowed-tools_
- [[context-engineering]] — the five context layers and the real prompt assembly order
  _context engineering, context window, context management, system prompt assembly, context_schema, runtime context, prompt layers, token limits, compression, offloading, context overflow, five layers, custom state, input context_
- [[summarization]] — thresholds, offload to `/conversation_history/`, `compact_conversation`
  _summarizer, summarization, SummarizationMiddleware, context compression, compact_conversation, conversation history, large_tool_results, context overflow, ContextOverflowError, trim history, offload, compaction, artifacts_root, context window full, summarize old messages_
- [[retrieval]] — RAG patterns: retrieve, offload to files, delegate
  _retrieval, RAG, retrieval augmented generation, vector store, vector search, retriever, agentic RAG, 2-step RAG, knowledge base, semantic search, embeddings, search tool, document search, RubricMiddleware_

## Interface

- [[tools]] — custom tools, `ToolRuntime`, `Command` returns, built-in tool table, large-result offload
  _custom tools, add tool, tools=, @tool, ToolRuntime, runtime.context, runtime.store, runtime.state, tool_call_id, Command update, large tool results, tool eviction, built-in tools, excluded_tools, get_stream_writer, tool returns image_
- [[mcp]] — `langchain.mcp.MCPAdapter` → `tools=` (docs only)
  _MCP, Model Context Protocol, MCPAdapter, langchain.mcp, langchain[mcp], FastMCP, MCP server tools, langchain-mcp-adapters, MultiServerMCPClient, list_tools, mcpServers, stdio, streamable http, connect MCP_
- [[streaming]] — `stream(subgraphs=True)`, namespaces, v3 `stream_events` (docs only)
  _streaming, stream, stream_mode, subgraphs=True, version v2, StreamPart, chunk type ns data, stream_events, astream_events, version v3, stream.subagents, stream.messages, subagent events, token streaming, custom stream, get_stream_writer, updates mode, progress events_
- [[frontend]] — what a Python agent exposes for `useStream` UIs (subagents, todos, sandbox IDE) (docs only)
  _frontend, UI, useStream, @langchain/react, React, Vue, Svelte, Angular, langgraph dev, langgraph.json, Agent Server, subagent cards, todo list UI, sandbox IDE, chat UI, stream.values_
- [[protocols]] — ACP, AG-UI, A2A (docs only)
  _ACP, Agent Client Protocol, deepagents-acp, AG-UI, @ag-ui/langgraph, A2A, Agent2Agent, editor integration, Zed, agent to agent, agent protocol, JSON-RPC, a2a assistant_id, IDE_
- [[multimodal]] — content blocks, media in `read_file`, video sampling, unsupported-content fallback
  _multimodal, image input, images, audio, video, PDF, file blocks, content blocks, read_file media, video frames, UnsupportedContentMiddleware, deepagents[video], screenshot, vision, unsupported content_

## Production

- [[production]] — deploy paths, `thread_id`/`context`, multi-tenancy, resilience checklist
  _production, deploy, deployment, langgraph.json, LangSmith Deployment, thread_id, context_schema, multi-tenant, per-user memory, namespace, sandbox lifecycle, checkpointer, go live, self-hosted_
- [[fault-tolerance]] — rate limits, retries, fallbacks, call limits, tool errors
  _fault tolerance, retry, ModelRetryMiddleware, ToolRetryMiddleware, ModelFallbackMiddleware, ModelCallLimitMiddleware, ToolCallLimitMiddleware, rate_limiter, 429, resilience, error handling, timeout, fallback model_
- [[testing]] — pytest with a scripted fake model (checked recipe; the `bind_tools` fix)
  _testing, test, unit test, pytest, fake model, fake chat model, mock model, GenericFakeChatModel, FakeMessagesListChatModel, bind_tools, no API calls, offline tests, scripted model_
- [[tutorials]] — data analysis, deep research, content builder, RAG: patterns and stale bits
  _tutorials, examples, data analysis agent, deep research agent, content builder, RAG agent, chunk-analyst, research-agent, sample agents, reference architecture, copy pattern, load_subagents, official tutorial_

---

Skip the sections below unless the question is about that product. SDK code never needs them.

## Optional — Deep Agents Code (`dcode`, terminal app; not the SDK)

- [[dcode]] — the terminal coding agent: install, modes, flags, slash commands (docs only)
  _dcode, deepagents-code, Deep Agents Code, terminal coding agent, CLI coding agent, TUI, headless mode, non-interactive, dcode -n, ACP server, slash commands, --model, --resume, --sandbox, install dcode_
- [[dcode-config]] — config precedence, providers, credentials (docs only)
  _dcode config, config.toml, managed_config.toml, API key, /auth, base_url, OPENAI_BASE_URL, gateway, DEEPAGENTS_CODE_, DEEPAGENTS_HOME, .env, provider, custom provider, class_path, recursion_limit, allowed models, retries_
- [[dcode-extending]] — AGENTS.md, skills, subagents, MCP, hooks, plugins, extensions (docs only)
  _dcode extensions, AGENTS.md, memory, skills, SKILL.md, subagents, sub-agent, MCP servers, .mcp.json, hooks, hooks.json, PreToolUse, plugins, marketplace, ExtensionAPI, Python extension, register_tool, allowedTools_
- [[dcode-safety]] — Manual/Auto/YOLO, allowlists, trust gates, remote sandboxes (docs only)
  _approval modes, manual mode, auto mode, YOLO, --yolo, auto-approve, human in the loop, HITL, approval, shell allow list, -S, allow-fs-tools, sandbox, remote sandbox, daytona, modal, runloop, untrusted repo, project trust, SandboxProvider_
- [[dcode-goals]] — `/goal`, `/rubric`, headless `--rubric` (docs only)
  _/goal, goal, /rubric, --rubric, rubric, acceptance criteria, grader, RubricMiddleware, keep iterating until done, self-grading, --rubric-max-iterations, --rubric-model, definition of done, CI quality gate_

## Optional — Managed Deep Agents (`mda`, LangSmith-hosted; not the SDK)

- [[managed]] — LangSmith-hosted harness: CLI, deploy, migrate, when to choose it (docs only)
  _managed deep agents, MDA, mda CLI, managed-deepagents, define_deep_agent, mda deploy, mda dev, mda init, LangSmith deployment, Agent Server, hosted agent, Context Hub, deploy agent to production, migrate from create_deep_agent_
- [[managed-project]] — project layout, `define_deep_agent`, `instructions.md` (docs only)
  _MDA project layout, agent.py, instructions.md, define_deep_agent, agent factory, per-run configuration, shared local package, project structure, system prompt, Context Hub, managed context, skills folder, tools folder, middleware folder, interrupt_on, agent name, assistant_id, .env, hatchling_
- [[managed-capabilities]] — skills, tools, MCP, search, connections, middleware, memory, sandbox, Context Hub (docs only)
  _MDA tools, define_mcp, MCP connectors, connections, connections.get, OAuth, mda connections create, define_memory, MemoryLayer, durable memory, remember across sessions, define_sandbox, sandbox setup.sh, runtime.backend, Context Hub, async middleware, ManagedDeepAgentRuntime, ManagedToolRuntime, ManagedRuntime_
- [[managed-channels]] — Slack/HTTP, interrupts, identity, schedules, `/mcp` endpoint (docs only)
  _MDA Slack, channels.slack, channels.http, webhook, HTTP channel, define_identity, identity.py, Supabase, define_schedule, cron, schedules, runtime.schedules, reminders, scheduled agent, Slack reactions, MCP endpoint, /mcp, interrupt_on Slack, attach_file, user_prompt_response, INTERRUPT_CORRELATION_KEY_
- [[managed-dev]] — `mda dev`, Harbor evals, tutorial (docs only)
  _mda dev, local development, LangSmith Studio, hot reload, mda evals, Harbor, evals, eval-engineering, tutorial, Tavily tool, .mda/build, langgraph dev, test schedule locally, memory not persisting, MDA_DEV, harbor-job.json_

## Optional — background

- [[agent-builder-memory]] — LangChain Agent Builder memory design mapped to SDK equivalents (docs only)
  _Agent Builder, LangSmith Agent Builder, file-based memory, agent memory lessons, COALA, procedural memory, semantic memory, episodic memory, memory in Postgres, virtual filesystem memory, memory human approval, AGENTS.md learning, tools.json, no-code agent_
- [[openwiki]] — separate Node CLI that generates repo wikis wired into AGENTS.md (docs only)
  _openwiki, open wiki, repo wiki, repository wiki, AGENTS.md generator, CLAUDE.md, codebase documentation, repo context for coding agents, personal knowledge base, personal brain, npm openwiki, wiki generator_
