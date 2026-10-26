---
name: pack-review
description: >
  Package the current goal, constraints, and diff or artifact into a pasteable
  brief for an independent reviewer in another session. Does not review and
  does not rewrite. Use when the user types /pack-review before carrying work
  to a second model, or when an unattended run reaches its cross-model gate
  and needs the brief before dispatching `scripts/cross-review-dispatch.mjs`.
  Not a planning or build pack, and not a review (f-inspect, xreview).
disable-model-invocation: false
argument-hint: "[optional extra constraints or file list]"
---

# pack-review

Build a single copy-paste review brief for a different session. Do not review. Do not rewrite. Do not name this model.

## Loop

`/pack-review` (this session) → `/xreview` (reviewer session) → `/adjudicate` (back here).

Two ways the brief crosses to the reviewer:

- **Hand-carried (a human is driving).** The user copies the fenced block and pastes it into the other session by hand.
- **Automated (unattended).** The session that did the work invokes the dispatcher (`scripts/cross-review-dispatch.mjs`, wherever the repo installed it) with `--host <this session's family> --brief <path to this brief> --out <dir>`, plus `--cwd <the checkout under review>` when the reviewer must run somewhere other than the dispatcher's working directory. That script seats the reviewer on a *different* CLI vendor by a fixed, no-picker seat rule and runs it headless, it never asks this session to guess who reviews, and this session never invokes `/xreview` on the brief itself.

Either way, your own output here is the review brief only, you do not review it and you do not dispatch it yourself beyond writing it to where the caller asked.

`disable-model-invocation` is `false` so an unattended session can invoke this skill on its own at its cross-model gate without a human typing the slash command. That flip does not authorize this session to also *play* the reviewer: `xreview` on an artifact this same session produced is never valid, flag or no flag, independence here comes from a different process on a different vendor CLI (the dispatcher), never from this setting.

## Gather

Stay read-only. Prefer live repo state over memory.

1. Goal and hard constraints from this session, plus any extras the user just added in `$ARGUMENTS`.
2. Non-goals and already-rejected approaches, if known.
3. What to review: PR URL, branch, file list, or a unified diff.
4. Tests or repro steps that already exist.
5. Anything the reviewer must not relitigate.

If they named a PR, branch, or files, gather those (`git diff`, `git status`, the named paths). If the diff is huge, pack the file list plus the highest-risk hunks and say what was omitted.

Write every path in the brief as an **absolute** path whenever the reviewer may run in a different working directory or checkout than this session (a separate worktree, a separate repo holding the records): a relative path the reviewer resolves against the wrong root is a silent wrong review.

## Redact

The reviewer must not learn which model did the work. Before emitting the brief, strip anything that names a model or vendor: commit trailers (`Co-Authored-By`, `Generated with ...`), session or tool names that identify the vendor, and paths under `.claude/`, `.grok/`, or `.codex/` unless that path is itself what is under review. Replace, do not summarise around, the stripped text.

## Output

One fenced markdown block the user can copy verbatim. No commentary before or after the block.

```markdown
# Review brief

## Goal
...

## Hard constraints
- ...

## Non-goals
- ...

## What to review
- paths / PR / branch

## Diff or artifact
...

## Tests / repro
- ...

## Do not relitigate
- ...

## Reviewer instruction
Review with /xreview. Do not guess the author. Reply with the /xreview sections only, no essay.
```
