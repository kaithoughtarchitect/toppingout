---
title: dcode goals and rubrics
id: dcode-goals
type: how-to
status: sourced
product: dcode
keywords: /goal, goal, /rubric, --rubric, rubric, acceptance criteria, grader, RubricMiddleware, keep iterating until done, self-grading, --rubric-max-iterations, --rubric-model, definition of done, CI quality gate
read_when: Read when you want dcode to keep working until acceptance criteria pass, or need a rubric quality gate in headless or CI runs.
updated: 2026-10-21
sources_hash: c96383a4f4f4
---

# dcode goals and rubrics

Goals and rubrics make [[dcode]] grade its own work against acceptance criteria and keep iterating until the criteria are met. Use `/goal` when you have an objective and want the agent to draft criteria. Use `/rubric` or `--rubric` when you already know the criteria.

## How it works

- Both are built on the SDK's `RubricMiddleware` (see [[rubric]]). When the agent would finish (a model response with no tool calls), a separate grader subagent judges the transcript. `needs_revision` injects feedback as a `HumanMessage` and the loop resumes. The loop ends on `satisfied`, on `failed`, or at `max_iterations`.
- In SDK 0.7.29 (unchanged since 0.7.20) the constructor is `RubricMiddleware(*, model, system_prompt=None, tools=None, ..., max_iterations=3, on_evaluation=None)` (every argument is keyword-only). The SDK default of 3 iterations explains why the docs example uses `--rubric-max-iterations 3`. dcode's own default is not stated in the docs.
- Since 0.1.61, goal and rubric context is injected directly into the prompt. The old `get_goal` and `get_rubric` tools were removed. Since 0.1.46 the grader can inspect working-directory files.
- Grading calls are billed and appear in `/cost`. The grader model is subject to `[models].allowed`.

## Goal or rubric?

| Situation | Command |
| - | - |
| One objective; the agent drafts criteria | `/goal <objective>` |
| Same criteria on every turn | `/rubric set <criteria>` |
| Criteria kept in a file | `/rubric file <path>` |
| One-turn quality gate | `/rubric next <criteria>` |
| Headless or CI | `dcode -n "..." --rubric "..."` or `--rubric @file.md` |

## Goals (interactive)

```text
/goal migrate auth callbacks to the new API
start with the OAuth callback          # follow-up turns are graded against the goal
now update the tests
/goal amend remove JSON export, add streaming CSV support
/goal pause        # kept, but it does not drive work or grading
/goal resume
/goal show
/goal clear
/goal model openai:gpt-5.5            # or: /goal model clear
/goal max-iterations 5                # or: /goal max-iterations clear
```

- Lifecycle: draft criteria, review, then active across turns until paused, completed, blocked or cleared. A goal whose completion is approved is cleared automatically. The goal panel above the input shows its status.
- Criteria review depends on the [[dcode-safety]] approval mode. Manual always opens an inline review (accept, edit, revise, cancel). Auto opens the review unless `goals.auto_accept_criteria = true` is set in `config.toml`. YOLO applies the criteria without review.
- `/goal amend` goes through the same review. It updates the objective and criteria without cancelling the task in progress.
- Underspecified objectives can be resolved from conversation context (0.1.51).

## Rubrics

```text
/rubric set tests pass; no unrelated files changed; help text is updated   # sticky
/rubric next only change the auth callback; do not refactor unrelated code # next turn only
/rubric file acceptance.md
/rubric show
/rubric clear
/rubric model anthropic:claude-opus-4-8
```

Headless (goals cannot pause for review in `-n` mode, so use a rubric):

```bash
dcode -n "implement OAuth refresh handling" \
  --rubric "tests pass; no unrelated files changed" \
  --rubric-model openai:gpt-5.5 \
  --rubric-max-iterations 3
```

- `--rubric TEXT|@PATH`, `--rubric-model` (defaults to the main model) and `--rubric-max-iterations` all require `-n` or piped stdin. Without them dcode exits with code 2.
- Combine with `--max-turns` and `--timeout` (exit 124) so a grader loop cannot run forever in CI.
- Grader model changes take effect without a restart (0.1.65) and persist across server restarts.

## Gotchas

- There is no `--goal` flag in the current CLI reference. The changelog mentions "`/goal`/`--goal`" from the early `RubricMiddleware` work, but only `--rubric*` flags are documented now. Use `--rubric` headless.
- `goal_rubric` recursion limits are separate from `[runtime].recursion_limit` (see [[dcode-config]]).
- `/goal` proposals themselves are not graded (0.1.4x fix). Grading starts after the criteria are accepted.
- Forked subagents see the goal but are not graded against it (0.1.84). In the SDK since 0.7.24, the `rubric` state key is no longer passed to or returned from `task` subagents (`_EXCLUDED_STATE_KEYS` in `middleware/subagents.py`), so a child is never graded against the parent's whole goal.
- Auto mode treats active goal and rubric directives as authorization for the actions they imply (0.1.46). A vague goal can widen what Auto approves.
- A rubric grades the transcript plus files; it does not replace running the tests. Write criteria the grader can verify, such as "tests pass", only if the agent actually runs them.

## Sources

- `../sources/docs/oss/deepagents/code/goals-and-rubrics.md`
- `../sources/docs/oss/deepagents/code/cli-reference.md` (rubric flags)
- `../sources/docs/github/deepagents-code-CHANGELOG.md` (goal and rubric history; the docs changelog page now redirects to this GitHub file)
- `../sources/package/deepagents/middleware/rubric.py` (`RubricMiddleware.__init__`, grading loop)

## See also

- [[index]]
- [[dcode]]
- [[rubric]]
- [[dcode-safety]]
