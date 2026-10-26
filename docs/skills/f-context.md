# f-context

Get a quick, complete picture of a repo before working in it.

Command: `/f-context`

Stage: Merge, close and Logbook · The Logbook
Source: `skills/f-context/SKILL.md`

## On site

The Logbook: when you're new to a repo, or before rethinking a plan. At a job's start, f-shift already does this for the job. It only reads, never changes anything. It can trace features with code-explorer, and --deep also digs through the commit history.

## Say it

- "get me up to speed on this project"
- "what is this codebase"
- "orient me"

## When to use it

When you arrive at a repo you don't know, or before re-planning work.

## Not for

A mid-session refresher, which is free (f-status). Not for Logbook card search (f-search).

## It's working if

- The brief covers the project and its current priority, the git state, active work, the Logbook cards that match the focus, the relevant architecture, standing warnings and a short starting sequence with source paths.
- It names the active work in one focus line before it searches the Logbook.
- With a focus, it adds a short deep dive on that area. With `--deep`, it adds a Deep Context section.
- If a step fails, it carries on and tells you what is missing.
- It edited no files, staged, committed and pushed nothing, and called no paid services.

## How to call it

The three ways to start it, exactly as the skill lists them.

```
/f-context
/f-context [focus-area]
/f-context --deep [focus-area]
```

## Common questions

### When should I use it?

When you arrive at a repo cold, or before re-scoping. At a job's start `/f-shift` already loads the job's cards, and a mid-session "where are we" is `/f-status`, which costs nothing.

### What does `--deep` add?

Full commit messages read for the reasons behind changes, tracing of the most-changed files and what they affect, similar code to follow, and the neighbourhoods of recently changed files. It is meant for coming back after a long break or before resuming complex work.

### What can I give as a focus?

A path, a system name, or a cluster slug that your Logbook already uses.

### Why does it cost more than other skills?

It reads widely and may send helper agents to answer bounded questions, with more digging under `--deep`. That is why it suggests cheaper skills when they fit.

## Connections

- Uses: code-explorer
