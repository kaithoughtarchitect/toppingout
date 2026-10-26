---
name: f-context
description: >
  Build a full orientation brief for a codebase you are arriving at cold,
  stack, git state, active work, focus-matched Logbook knowledge, relevant
  architecture, and standing warnings. EXPENSIVE: optional explorers; more
  with --deep. Use when the user runs /f-context, says "get me up to speed on
  this project", "what is this codebase", "orient me", or is resuming after days
  away. Not for a mid-session refresher, which is free (f-status). Not for
  Logbook card search (f-search).
---

# Topping Out: Logbook context

This is a read-only orientation pass.

## Usage

```
/f-context
/f-context [focus-area]
/f-context --deep [focus-area]
```

**No arguments**: Full project context.

**`--deep`**: Adds commit archaeology, symbol/impact tracing, pattern comparison, and file-neighborhood analysis. Use after a long break or before resuming complex in-flight work; skip for routine session starts.

**With focus**: Prioritize that area (a path, system name, or live Logbook cluster slug, do not invent a closed catalog).

## Collection

Two waves. Identify active work first so Logbook search has a target.

**Wave 1 (root):** Read the constitution (the repo profile names it: `AGENTS.md`, or `CLAUDE.md` where that is the constitution), git status / recent commits / branch, the open job in `foreman/jobs/` (if several, the newest by filename date unless the owner names one; skip any whose `JOB COMPLETE` (older records: `COMMISSION COMPLETE`) status reads `✅ COMPLETE`, that is finished work awaiting `/f-signoff`), the repo profile's gates and the repo's own build/test entry points (whatever manifest the stack uses: `package.json` scripts, `pyproject.toml`, a `Makefile`, `Cargo.toml`, …), and top-level structure. Trace architecture, entry points, and tests for the current work area, not the whole repo. Write one focus line: _"Active work: <topic/files/system>"_.

**Wave 2 (root):** Search current Logbook cards in `foreman/logbook/entries/` against that focus line (focus-matched cards first). Count live cards (`[A-Z]*_20*.md`, excluding `*TEMPLATE*`). If the count is **greater than 250**, run `/f-archive` (dry-run) before synthesizing, that preview is read-only. Read 2–3 recent completed jobs in `foreman/completed-jobs/` that touch the focus when present.

Root may call `code-explorer` with bounded, non-overlapping questions. Load `.claude/agents/code-explorer.md`. Child roles return evidence only and never recursively dispatch.

In `--deep` mode, also: full recent-commit bodies for WHY; symbol/impact tracing on the most-changed files; similar implementations to follow; same-directory neighborhoods of dirty or recently-committed files.

Do not re-explore facts already established by trustworthy evidence unless a contradiction appears. The constitution and the open job may already be in context.

## Output

Synthesize:

- project snapshot and current priority;
- dirty-tree and recent-commit state;
- active work and ownership boundaries;
- focus-matched Logbook knowledge;
- relevant architecture and data flow;
- critical warnings and environment constraints (from the constitution);
- a short recommended starting sequence with source paths.

If a focus was given, add a short deep dive for that area. If `--deep`, add a Deep Context section (symbol map, blast radius, patterns-to-follow, neighborhoods, WHY from commit bodies). If a gather step fails, continue with what you have and say so.

## Boundaries

Never edit files, stage, commit, push, call paid services, or perform live writes.

Cost is real. Mid-session "where are we" is `/f-status` and costs nothing. At a job's start, `/f-shift` already loads the job's cards; use this for arriving at a repo cold, or before re-scoping. Say so rather than running this.
