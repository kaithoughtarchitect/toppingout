# agent-council

Ask AI agents that can read the code to help settle a design choice.

Command: `/agent-council`

Stage: Plan · Settling a fork
Source: `skills/agent-council/SKILL.md`

## On site

Before a job, optional: f-survey can ask it about a choice only the code can answer, if you allow the code to be shared. A heavier version of model-council: the agents run on your AI subscriptions and can read the repo.

## When to use it

When a design choice depends on what's in the code and you've agreed to let agents read it.

## Not for

A decision a written brief can carry without repo access, that is the cheaper model-council.

## It's working if

- It tells you the assurance profile before preparing: focused (2 external seats), balanced (3) or full (5), plus the host as chair and one separate auditor.
- No seat comes from the host's own model family; the resolver removes it and seats the next qualified replacement.
- `prepare` returns a disclosure manifest and its SHA-256, and no model is called until you approve that exact digest.
- It says which seats run on native subscription CLIs and which are pay-per-token Pi headless OpenRouter seats.
- Round 2 always runs; Round 3 runs only when `inspect` reports it is required.
- The audit verdict is `FAITHFUL` or `NEEDS-REVISION`, and only a `FAITHFUL` run can be finalized into your durable output folder.
- A run with fewer seats than its profile needs is never called an Agent Council: there is no degraded panel.

## Common questions

### How is it different from model-council?

Here the seats can read, search and experimentally edit a frozen copy of the repository. Use it when the decision depends on the code; use `/model-council` when a written brief is enough, as it is cheaper.

### What exactly gets shared with outside models?

The current tracked and untracked, non-ignored files, frozen into one corpus after a secret scan, plus any history diff you approve separately. You approve the exact manifest digest; any change to the inputs needs a new preparation and approval.

### Can the seats run code or reach the internet?

No. Seats get no shell, web, plugins or nested agents, and models never run edited code; the repo's existing offline gates run only through the runner and come back as receipts. These limits are set by the runner's policy, not by an operating-system sandbox, and the skill makes no stronger containment claim.

### Which profile should I pick?

The smallest that fits the cost of being wrong. Focused for bounded choices that are easy to undo, balanced for normal architecture, data-model and interface forks, full for security or privacy boundaries, migrations that can't be undone, public contracts or very unclear evidence.

### Can I choose the models myself?

Yes. Name them in chat and they become `--seat`, `--prefer-seat` or `--exclude-seat` flags, or open the picker to browse. The picker only chooses who sits; approving the disclosure stays a separate step.

## Connections

- Used by: f-survey
