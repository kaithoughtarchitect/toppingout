---
title: Lessons from Agent Builder's memory system
id: agent-builder-memory
type: reference
status: sourced
product: all
keywords: Agent Builder, LangSmith Agent Builder, file-based memory, agent memory lessons, COALA, procedural memory, semantic memory, episodic memory, memory in Postgres, virtual filesystem memory, memory human approval, AGENTS.md learning, tools.json, no-code agent
read_when: Read when designing file-based agent memory, or wanting real-world lessons on self-updating AGENTS.md, memory approval, and compaction from LangSmith Agent Builder.
updated: 2026-10-21
sources_hash: cc8292ec79e7
---

# Lessons from Agent Builder's memory system

One-line truth: LangChain's no-code LangSmith Agent Builder (on the Deep Agents harness) stores each agent's entire definition and memory as Markdown/JSON files in Postgres, exposed as a virtual filesystem the agent edits in the hot path with human approval; the blog (Feb 21, 2026) is the best field report on file-based agent memory.

## What they built

| File | Role | COALA memory type |
| - | - | - |
| `AGENTS.md` | core instructions; rewritten by the agent from user corrections | procedural |
| `tools.json` | custom MCP config listing only a subset of a server's tools (avoid context overflow); not standard `mcp.json` (see [[mcp]]) | procedural |
| `skills/*/SKILL.md` | task-specific instructions (Agent Skills standard) | semantic (their classification) |
| `subagents/` | subagent definitions, Claude Code-like format (compare [[subagents]]) | - |
| other files (e.g. job descriptions) | arbitrary knowledge the agent and user add and maintain | semantic |
| (none) | episodic memory deliberately omitted at launch | episodic |

- Files live in **Postgres**, shown to the model as a filesystem. Deep Agents' pluggable backends make this native; S3/MySQL etc. equally possible. See [[backends]].
- No memory-specific tools: the agent uses normal file tools, same as `memory=` + `edit_file` in [[memory]].
- Scope at launch: per-agent only; no user- or org-level memory yet (planned as separate directories).

## Example: memory built from corrections

Start: `AGENTS.md` = "Summarize meeting notes." Week 1 correction "use bullet points" -> agent writes a `# Formatting Preferences` section. Week 2 "extract action items at the end" -> appended. Month 3: sections for format, meeting types, people/roles, terminology, edge cases. The spec emerged from feedback; the user never edited the file by hand.

## Lessons (the load-bearing part)

1. **Prompting is the hard part.** Nearly every memory failure was fixed by prompt changes: not remembering when it should, remembering when it should not, writing to `AGENTS.md` instead of skills, wrong skill format. One full-time person worked on memory prompting.
2. **Validate structured files before committing.** `tools.json` must be valid MCP config, skills need valid frontmatter. Agents sometimes wrote invalid files; they added validation that throws errors back to the LLM instead of saving.
3. **Agents add, they do not compact.** Example: an email assistant listed individual vendors to ignore instead of generalizing to "ignore cold outreach". Needs explicit compaction prompts or a background process.
4. **Explicit user prompts still help.** "Reflect on this conversation and update memory" at the end, and "compact your memory", were both useful.
5. **Human-in-the-loop on every memory edit**, mainly against prompt injection, with an opt-out "yolo mode".

## What file-based memory enabled
- Harness does the heavy context engineering (summarization, tool-result offloading, planning), so configuration can stay simple ([[summarization]]).
- No DSL: agents are Markdown + JSON, familiar to non-engineers and scalable.
- Iterating by feedback instead of editing config.
- Portability to other harnesses using the same conventions (Deep Agents CLI, Claude Code, OpenCode).

## Planned (not shipped per the post)
- Episodic memory as past conversations exposed as files.
- Background reflection cron (about daily) to catch missed items and generalize.
- `/remember` command.
- Semantic search over memory (beyond `glob`/`grep`).
- User- and org-level memory directories.

## Applying this with the SDK (mapping, not from the blog)
- Postgres-backed files: a `StoreBackend` on a Postgres-backed LangGraph store, routed via `CompositeBackend` ([[backends]]).
- HITL on memory writes: `FilesystemPermission(operations=["write"], paths=["/memories/**"], mode="interrupt")` ([[permissions]], [[human-in-the-loop]]).
- Validation before commit: backend policy hooks returning an error string to the model.
- Keep `AGENTS.md` short; push procedures into [[skills]] and tell the agent which goes where.
- Background consolidation agent on a cron is the documented pattern in [[memory]].
- A UI showing the files can read the same store keys the agent writes.

## Gotchas
- This is a product blog, not API docs; nothing here is a `deepagents` API. Agent Builder is a LangSmith product ([[products]], [[managed]]).
- Their COALA mapping calls skills "semantic"; the Deep Agents memory docs call skills "procedural". The labels are inconsistent across sources; the behavior (on-demand instruction files) is the same.
- Hot-path writes add latency and depend heavily on prompt quality; budget for prompt iteration.

## Sources
- `../sources/docs/blog/agent-builder-memory.md`
- `../sources/docs/oss/python/deepagents/memory.md`

## See also
- [[index]]
- [[memory]]
- [[skills]]
- [[backends]]
- [[human-in-the-loop]]
- [[openwiki]]
