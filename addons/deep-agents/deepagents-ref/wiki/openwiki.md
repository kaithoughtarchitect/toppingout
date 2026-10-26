---
title: OpenWiki
id: openwiki
type: product
status: sourced
product: all
keywords: openwiki, open wiki, repo wiki, repository wiki, AGENTS.md generator, CLAUDE.md, codebase documentation, repo context for coding agents, personal knowledge base, personal brain, npm openwiki, wiki generator
read_when: Read when you want durable repo docs generated for coding agents (Deep Agents Code, Claude Code, Codex, Cursor), or are asking whether OpenWiki is part of the SDK.
updated: 2026-10-21
sources_hash: 32ae6bf25aa1
---

# OpenWiki

One-line truth: OpenWiki is a separate open-source CLI (npm package `openwiki`, built on Deep Agents) that generates and maintains a Markdown wiki of a repository (or a personal knowledge base) and wires it into `AGENTS.md`/`CLAUDE.md` so coding agents read curated context instead of rediscovering the repo. It is not part of the `deepagents` Python package.

## When to reach for it
- You want durable repo context for coding agents (Deep Agents Code, Claude Code, Codex, Cursor, OpenCode) without hand-writing docs.
- You want a "personal brain" wiki built from your sources.
- Not for runtime agent memory in your own app; for that use `memory=` + backends ([[memory]]).

## Install and run

```bash
npm install -g openwiki
openwiki --init        # code mode, current repo -> ./openwiki/
openwiki --update      # refresh
openwiki personal --init / --update   # personal mode -> ~/.openwiki/wiki
```

## Modes

| Mode | Command | Output |
| - | - | - |
| Code (default) | `openwiki` / `openwiki code` | `openwiki/` in the repo, linked from `AGENTS.md` and `CLAUDE.md` |
| Personal | `openwiki personal` | `~/.openwiki/wiki` |

## Capabilities (overview page only)
- Repository wikis: architecture, integrations, evals, workflows as Markdown.
- Coding-agent integrations: run inside Codex, Claude Code, OpenCode, Cursor, IBM Bob, Kiro, Oh My Pi, Antigravity or Pi using the host model/tools.
- Search and link: query wiki pages over MCP and group related repository wikis into workspaces.
- Personal sources: git repos, custom MCP, Gmail, Notion, web search, Hacker News, X/Twitter.
- Grounded Claims: material facts tracked to versioned source evidence; pages refresh when evidence changes.
- Automatic updates from GitHub Actions, GitLab CI, Bitbucket Pipelines, opening a PR on change.
- Providers: OpenAI, Anthropic, Gemini, Bedrock, OpenRouter, GitHub Copilot, IBM Bob, others.
- Open Knowledge Format (OKF) v0.2 bundles: front matter, indexes, linked concepts.
- LangSmith tracing; local visualizer for humans.

## Relation to Deep Agents
- Built on Deep Agents; a working example of "memory as Markdown files the agent maintains", the same idea as [[agent-builder-memory]] and `AGENTS.md` memory in [[memory]].
- The memory and context-engineering docs point to OpenWiki for generating repo wikis discovered via `AGENTS.md` ([[context-engineering]]).
- Deep Agents Code reads `AGENTS.md` files, so an OpenWiki-wired repo gives [[dcode]] that context. See [[products]].

## Gotchas
- OpenWiki now has its own docs section (`/oss/openwiki/*`: quickstart, integrations, search-and-link, visualize, CLI reference, customize, providers, automate-updates, code mode, personal mode); the old Deep Agents page redirects to its overview. Only the overview is in `sources/`; the other pages are docs only (layer 2). Flags beyond `--init`/`--update` and the `code`/`personal` subcommands are unverified.
- It is a Node CLI, not a Python API; nothing to import from `deepagents`.
- Primary audience is agents; the wiki is meant to be read first, with source inspected only for detail.

## Sources
- `../sources/docs/oss/openwiki/overview.md` (the old Deep Agents OpenWiki page redirects here)

## See also
- [[index]]
- [[memory]]
- [[agent-builder-memory]]
- [[dcode]]
- [[products]]
