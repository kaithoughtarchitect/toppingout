---
title: Lookup — term and symbol to page
id: lookup
type: map
status: code
product: all
keywords: lookup, find, where is, glossary, symbol, import, class, function, parameter, synonym
read_when: Read when you have a term, class, function or parameter name and need the page that explains it.
updated: 2026-10-21
---

# Lookup — term and symbol to page

One grep target. Search this file for the word you have. The terms are hand-written; the symbol table below is generated from `../sources/package/` by `python scripts/build_lookup.py`. No match here or on [[index]] → [[gaps]].

**Product clash:** the same word often exists in the SDK, Deep Agents Code (`dcode-*`) and Managed (`managed-*`). For SDK code, read the SDK page first.

## Terms

| You say | SDK page | Also |
|---|---|---|
| agent, harness, deep agent, what is it | [[harness]] | [[products]] |
| create agent, constructor, parameters, signature | [[create-deep-agent]] | [[customization]] |
| system prompt, instructions, prompt order | [[customization]], [[context-engineering]] | Managed `instructions.md`: [[managed-project]] |
| model, provider, OpenRouter, OpenAI, Anthropic, `provider:model`, profile | [[models]] | dcode providers: [[dcode-config]] |
| middleware, stack order, hooks, replace built-in | [[middleware]] | dcode hooks: [[dcode-extending]] |
| tool, custom tool, `@tool`, ToolRuntime, runtime context, `Command` | [[tools]] | |
| MCP, MCP server, MCPAdapter | [[mcp]] | [[dcode-extending]], [[managed-capabilities]] |
| file, filesystem, ls, read_file, write_file, edit_file, glob, grep, execute | [[filesystem-tools]] | |
| backend, virtual filesystem, State/Store/Filesystem/Composite backend, route, namespace | [[backends]] | |
| pinned_skills, pin a skill, include_tools, skill tools, SkillToolResolver, disclosed_skill_tool_names | [[skills]] | [[customization]], [[tools]] |
| TaskEvent, deepagents_notification, task notification, waiting status, async subagent fork mode, parent_thread_id | [[async-subagents]] | [[streaming]], [[human-in-the-loop]] |
| _ParentNotifierMiddleware | [[middleware]] | [[async-subagents]] |
| summarizer, separate summary model | [[summarization]] | [[context-engineering]] |
| offload_binary_content, blobs, binary in history | [[backends]] | [[filesystem-tools]], [[multimodal]] |
| grep_exclude_dirs, ripgrep, .git skipped | [[sandboxes]] | [[filesystem-tools]] |
| symlink, resolves to, cannot resolve | [[permissions]] | |
| version="v2" stream chunks | [[streaming]] | |
| memory, long-term memory, remember across sessions, AGENTS.md, `/memories/` | [[memory]] | [[agent-builder-memory]], [[managed-capabilities]] |
| persist, persistence, restart, checkpoint, checkpointer, store, thread, `thread_id`, Postgres, SQLite | [[persistence]] | [[production]] |
| per-user, per-tenant, multi-tenant, isolation, scope | [[backends]], [[memory]] | [[production]] |
| permissions, deny, read-only, allowlist paths | [[permissions]] | |
| sandbox, shell, run code, execute, container, E2B, Modal, Daytona | [[sandboxes]] | [[dcode-safety]] |
| interpreter, QuickJS, eval, code mode, programmatic tool calling | [[interpreters]] | |
| plan, planning, todo, todos, write_todos, TodoListMiddleware | [[planning]] | UI: [[frontend]] |
| subagent, sub-agent, sub agent, task tool, delegate, child agent, specialist | [[subagents]] | [[dcode-extending]] |
| fan out, parallel subagents, dynamic subagents | [[dynamic-subagents]] | |
| background task, async subagent, long-running | [[async-subagents]] | |
| approval, approve, human in the loop, HITL, interrupt, confirm, `interrupt_on` | [[human-in-the-loop]] | dcode approval modes: [[dcode-safety]] |
| rubric, grader, iterate until done, quality loop, goal | [[rubric]] | [[dcode-goals]] |
| skills, SKILL.md, progressive disclosure | [[skills]] | [[dcode-extending]], [[managed-capabilities]] |
| context window, context engineering, what the model sees | [[context-engineering]] | |
| summarization, compaction, compact, overflow, too many tokens, conversation history | [[summarization]] | |
| large tool output, eviction, `/large_tool_results/` | [[filesystem-tools]] | [[summarization]] |
| RAG, retrieval, vector store, search documents | [[retrieval]] | |
| stream, streaming, tokens, events, subgraphs | [[streaming]] | |
| UI, frontend, React, useStream | [[frontend]] | |
| ACP, A2A, AG-UI, protocol, editor integration | [[protocols]] | |
| images, audio, video, PDF, multimodal | [[multimodal]] | |
| deploy, production, langgraph.json, server | [[production]] | [[managed]] |
| retry, rate limit, 429, fallback, errors, resilience | [[fault-tolerance]] | |
| example, tutorial, research agent, data analysis | [[tutorials]] | |
| structured output, `response_format` | [[create-deep-agent]] | [[subagents]] |
| version, upgrade, breaking change, changelog | [[versions]] | |
| wiki generation, OpenWiki | [[openwiki]] | |
| terminal coding agent, CLI, `dcode` | — | [[dcode]] |
| hosted, LangSmith deployment, `mda`, Slack bot, schedule, cron | — | [[managed]], [[managed-channels]] |
| `deepagents deploy`, `deepagents.toml`, deepagents-cli | deprecated, see [[anti]] | [[managed]] |
| agent setup, workspace, Memory tab, workspace switch, leakage | [[agent-setup]] | [[memory]] |
| memory history, audit, revision, undo, original wording | [[memory-history]] | |
| testing, pytest, fake model, mock model | [[testing]] | |
| failed turn, tool error, stream crashed, Trace tab | [[streaming]] | [[anti]] |
| debugging, symptom, why doesn't | [[anti]] (Symptom → cause) | |
| GPT-6 Luna, openrouter model id, slug | [[models]] | [[agent-setup]] |
| evals, token usage, cost, tracing, MCP auth | not covered | [[gaps]] |

## Symbols

<!-- GENERATED:symbols (scripts/build_lookup.py) -->

| Symbol | Import | Defined at | Read |
|---|---|---|---|
| `AsyncSubAgent` | `from deepagents import AsyncSubAgent` | `../sources/package/deepagents/middleware/async_subagents.py:56` | [[async-subagents]], [[create-deep-agent]] |
| `AsyncSubAgentMiddleware` | `from deepagents import AsyncSubAgentMiddleware` | `../sources/package/deepagents/middleware/async_subagents.py:1361` | [[middleware]], [[async-subagents]] |
| `CompiledSubAgent` | `from deepagents import CompiledSubAgent` | `../sources/package/deepagents/middleware/subagents.py:230` | [[subagents]], [[create-deep-agent]] |
| `DeepAgentState` | `from deepagents import DeepAgentState` | `../sources/package/deepagents/graph.py:75` | [[create-deep-agent]], [[context-engineering]] |
| `FilesystemMiddleware` | `from deepagents import FilesystemMiddleware` | `../sources/package/deepagents/middleware/filesystem.py:1819` | [[middleware]], [[filesystem-tools]] |
| `FilesystemPermission` | `from deepagents import FilesystemPermission` | `../sources/package/deepagents/middleware/filesystem.py:367` | [[permissions]], [[memory]] |
| `FsToolName` | `from deepagents import FsToolName` | `../sources/package/deepagents/middleware/filesystem.py:1607` | [[filesystem-tools]], [[tools]] |
| `GeneralPurposeSubagentProfile` | `from deepagents import GeneralPurposeSubagentProfile` | `../sources/package/deepagents/profiles/harness/harness_profiles.py:83` | [[models]], [[subagents]] |
| `HarnessProfile` | `from deepagents import HarnessProfile` | `../sources/package/deepagents/profiles/harness/harness_profiles.py:483` | [[models]], [[middleware]] |
| `HarnessProfileConfig` | `from deepagents import HarnessProfileConfig` | `../sources/package/deepagents/profiles/harness/harness_profiles.py:192` | [[models]] |
| `MemoryMiddleware` | `from deepagents import MemoryMiddleware` | `../sources/package/deepagents/middleware/memory.py:180` | [[memory]], [[middleware]] |
| `ProviderProfile` | `from deepagents import ProviderProfile` | `../sources/package/deepagents/profiles/provider/provider_profiles.py:38` | [[models]] |
| `RubricMiddleware` | `from deepagents import RubricMiddleware` | `../sources/package/deepagents/middleware/rubric.py:492` | [[rubric]], [[dcode-goals]] |
| `SubAgent` | `from deepagents import SubAgent` | `../sources/package/deepagents/middleware/subagents.py:84` | [[subagents]], [[middleware]] |
| `SubAgentMiddleware` | `from deepagents import SubAgentMiddleware` | `../sources/package/deepagents/middleware/subagents.py:914` | [[middleware]], [[subagents]] |
| `create_deep_agent` | `from deepagents import create_deep_agent` | `../sources/package/deepagents/graph.py:278` | [[create-deep-agent]], [[managed]] |
| `register_harness_profile` | `from deepagents import register_harness_profile` | `../sources/package/deepagents/profiles/harness/harness_profiles.py:980` | [[models]], [[middleware]] |
| `register_provider_profile` | `from deepagents import register_provider_profile` | `../sources/package/deepagents/profiles/provider/provider_profiles.py:195` | [[models]] |
| `DEFAULT_EXECUTE_TIMEOUT` | `from deepagents.backends import DEFAULT_EXECUTE_TIMEOUT` | `../sources/package/deepagents/backends/local_shell.py:23` | [[backends]] |
| `BackendProtocol` | `from deepagents.backends import BackendProtocol` | `../sources/package/deepagents/backends/protocol.py:404` | [[backends]], [[managed-capabilities]] |
| `CompositeBackend` | `from deepagents.backends import CompositeBackend` | `../sources/package/deepagents/backends/composite.py:228` | [[backends]], [[persistence]] |
| `ContextHubBackend` | `from deepagents.backends import ContextHubBackend` | `../sources/package/deepagents/backends/context_hub.py:101` | [[backends]], [[production]] |
| `FilesystemBackend` | `from deepagents.backends import FilesystemBackend` | `../sources/package/deepagents/backends/filesystem.py:91` | [[backends]], [[tutorials]] |
| `LangSmithSandbox` | `from deepagents.backends import LangSmithSandbox` | `../sources/package/deepagents/backends/langsmith.py:56` | [[sandboxes]], [[products]] |
| `LocalShellBackend` | `from deepagents.backends import LocalShellBackend` | `../sources/package/deepagents/backends/local_shell.py:27` | [[backends]], [[production]] |
| `NamespaceFactory` | `from deepagents.backends import NamespaceFactory` | `../sources/package/deepagents/backends/store.py:42` | [[backends]], [[persistence]] |
| `StateBackend` | `from deepagents.backends import StateBackend` | `../sources/package/deepagents/backends/state.py:38` | [[backends]], [[harness]] |
| `StoreBackend` | `from deepagents.backends import StoreBackend` | `../sources/package/deepagents/backends/store.py:90` | [[backends]], [[memory]] |
| `DEEPAGENTS_DEFAULT_SUMMARY_PROMPT` | `from deepagents.middleware import DEEPAGENTS_DEFAULT_SUMMARY_PROMPT` | `../sources/package/deepagents/middleware/summarization.py:113` | no wiki page — read the definition |
| `GRADER_SYSTEM_PROMPT` | `from deepagents.middleware import GRADER_SYSTEM_PROMPT` | `../sources/package/deepagents/middleware/rubric.py:144` | [[rubric]] |
| `RUBRIC_GRADER_MESSAGE_SOURCE` | `from deepagents.middleware import RUBRIC_GRADER_MESSAGE_SOURCE` | `../sources/package/deepagents/middleware/rubric.py:127` | no wiki page — read the definition |
| `CriterionEval` | `from deepagents.middleware import CriterionEval` | `../sources/package/deepagents/middleware/rubric.py:209` | no wiki page — read the definition |
| `CriterionFail` | `from deepagents.middleware import CriterionFail` | `../sources/package/deepagents/middleware/rubric.py:196` | no wiki page — read the definition |
| `CriterionPass` | `from deepagents.middleware import CriterionPass` | `../sources/package/deepagents/middleware/rubric.py:186` | no wiki page — read the definition |
| `GraderResponse` | `from deepagents.middleware import GraderResponse` | `../sources/package/deepagents/middleware/rubric.py:309` | [[rubric]] |
| `GraderVerdict` | `from deepagents.middleware import GraderVerdict` | `../sources/package/deepagents/middleware/rubric.py:66` | no wiki page — read the definition |
| `RubricEvaluation` | `from deepagents.middleware import RubricEvaluation` | `../sources/package/deepagents/middleware/rubric.py:219` | [[rubric]] |
| `RubricResult` | `from deepagents.middleware import RubricResult` | `../sources/package/deepagents/middleware/rubric.py:75` | no wiki page — read the definition |
| `RubricState` | `from deepagents.middleware import RubricState` | `../sources/package/deepagents/middleware/rubric.py:260` | no wiki page — read the definition |
| `SkillMetadata` | `from deepagents.middleware import SkillMetadata` | `../sources/package/deepagents/middleware/skills.py:288` | no wiki page — read the definition |
| `SkillToolResolver` | `from deepagents.middleware import SkillToolResolver` | `../sources/package/deepagents/middleware/skills.py:176` | [[skills]] |
| `SkillsMiddleware` | `from deepagents.middleware import SkillsMiddleware` | `../sources/package/deepagents/middleware/skills.py:916` | [[skills]], [[middleware]] |
| `SkillsState` | `from deepagents.middleware import SkillsState` | `../sources/package/deepagents/middleware/skills.py:353` | [[skills]] |
| `SummarizationMiddleware` | `from deepagents.middleware import SummarizationMiddleware` | `../sources/package/deepagents/middleware/summarization.py:1804` | [[summarization]], [[middleware]] |
| `SummarizationToolMiddleware` | `from deepagents.middleware import SummarizationToolMiddleware` | `../sources/package/deepagents/middleware/summarization.py:1993` | [[summarization]] |
| `TaskEvent` | `from deepagents.middleware import TaskEvent` | `../sources/package/deepagents/middleware/async_subagents.py:413` | [[async-subagents]] |
| `UnsupportedContentMiddleware` | `from deepagents.middleware import UnsupportedContentMiddleware` | `../sources/package/deepagents/middleware/unsupported_content.py:109` | [[middleware]], [[multimodal]] |
| `create_summarization_tool_middleware` | `from deepagents.middleware import create_summarization_tool_middleware` | `../sources/package/deepagents/middleware/summarization.py:1903` | [[summarization]], [[context-engineering]] |
| `apply_provider_profile` | `from deepagents.profiles.provider import apply_provider_profile` | `../sources/package/deepagents/profiles/provider/provider_profiles.py:345` | [[models]] |
| `get_provider_profile` | `from deepagents.profiles.provider import get_provider_profile` | `../sources/package/deepagents/profiles/provider/provider_profiles.py:277` | no wiki page — read the definition |

`create_deep_agent` parameters (signature: [[create-deep-agent]]):

| Parameter | Read |
|---|---|
| `model=` | [[create-deep-agent]], [[models]], [[dcode]] |
| `tools=` | [[create-deep-agent]], [[tools]], [[mcp]] |
| `system_prompt=` | [[create-deep-agent]], [[customization]], [[subagents]] |
| `middleware=` | [[create-deep-agent]], [[middleware]], [[customization]] |
| `subagents=` | [[create-deep-agent]], [[dynamic-subagents]], [[dcode-extending]] |
| `skills=` | [[create-deep-agent]], [[skills]], [[dcode-extending]] |
| `memory=` | [[create-deep-agent]], [[memory]], [[agent-builder-memory]] |
| `permissions=` | [[create-deep-agent]], [[permissions]], [[subagents]] |
| `backend=` | [[create-deep-agent]], [[backends]], [[middleware]] |
| `interrupt_on=` | [[create-deep-agent]], [[human-in-the-loop]], [[customization]] |
| `response_format=` | [[create-deep-agent]], [[customization]], [[subagents]] |
| `state_schema=` | [[create-deep-agent]], [[tools]], [[managed]] |
| `context_schema=` | [[create-deep-agent]], [[production]], [[context-engineering]] |
| `checkpointer=` | [[create-deep-agent]], [[persistence]], [[production]] |
| `store=` | [[create-deep-agent]], [[persistence]], [[memory]] |
| `debug=` | [[create-deep-agent]], [[streaming]], [[skills]] |
| `name=` | [[create-deep-agent]], [[managed-project]], [[skills]] |
| `cache=` | [[create-deep-agent]], [[skills]], [[subagents]] |

<!-- /GENERATED:symbols -->

## See also

- [[index]]
- [[gaps]]
