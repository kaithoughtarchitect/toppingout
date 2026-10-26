---
name: model-council
description: >
  Settle a genuinely forky design decision with a 2-5 seat blind panel that
  sees only the written brief, adversarial reconciliation, and an independent
  synthesis audit. Use for /model-council, or a load-bearing choice a written
  brief can carry. Not for panels that must inspect the codebase
  (agent-council). Not for what tests or an evaluation should decide.
argument-hint: "<the decision> [--brief <path>] [--rounds N] [--player <id>]"
allowed-tools: ["Bash", "Read", "Edit", "Glob"]
---

# Multi-Model Council

Use this only for load-bearing choices that cannot be settled by repository facts, a test, or an evaluation. This session chairs and owns the final decision; the panel supplies independent arguments, not a vote.

## Panel and auditor

Seats live in `.claude/skills/model-council/council-roster.json`. Read that file at the start of every run. Do not copy slugs into this skill.

- `role: orchestrator`, this session (chair) while it is the host. No API call as chair. When the host is not Anthropic, Claude is pickable as an OpenRouter panel/auditor door. Grey out / drop the host family from panel and auditor picks.
- `role: panel`, participating doors. `door: OpenRouter` uses that row's `slug` + `effort`; `door: codex CLI` uses `cliModel` at that row's `effort`, brief-only in an empty temp dir.
- `role: shortlist`, curated pool. Picker can seat these as panel or auditor (`pickableAs`). Do not preflight or call until this run seats it.
- `role: auditor`, **picked this run**, not a catalog default. `role: auditor` in the JSON is a label, not a fallback. Never a seventh decision position. Vendor must not appear on chair or the picked panel.

**Law A:** every run opens the one-shot HTML picker. Seats are for this run only. Do not reuse a leftover pick file. Do not use roster default rows. Do not guess if the picker fails.

After framing the brief, launch the picker and wait, do not preflight until exit 0:

```
node .claude/skills/model-council/council-pick.mjs --host <claude|codex|grok> --timeout 600000
```

Host is this session (Claude → `claude`, Codex → `codex`, Grok → `grok`). The operator picks 2–5 panel seats and one auditor; the tab says Sent and they close it. Verdicts stay in chat. Stdout has `COUNCIL_PICK_TOKEN=`. Read `.claude/skills/model-council/council-pick.json` only if `pick.token` matches that token, then copy it to `council-this-run.json` in the repo root, **delete** the skill-dir pick file, echo host / panel names+vendors+effort / auditor in chat, and preflight those keys. Timeout (exit 2), bind error (exit 1), missing file, or token mismatch: stop. Two panelists cannot share a vendor. Host family cannot sit as panel or auditor. At least two participating doors must work; otherwise stop and report that no council was formed.

## The author's door is dropped

`--player <id>` declares the model that authored the option under discussion or will implement the decision. It defaults to the session host only when the brief concerns that host's own work; otherwise no Player is declared and the full panel stands. If it is unclear whether the chair authored the thing being decided, ask before framing the brief.

When a Player is declared, that vendor's door is dropped and the panel runs one seat short. The chair still chairs and still owns the decision, it holds no position on a question about its own work. The auditor must not belong to the Player's family either; substitutions through the fallback chain are re-checked against it. The result and any provenance line state the reduced count, the dropped door, and the declared Player. A five-door council reported as six overstates the independence behind the decision.

## Execution

The root session is the sole orchestrator. Council seats are external API or isolated CLI calls, not repository subagents, and no seat may dispatch further work.

**OpenRouter send** (every picked row with `door: OpenRouter`, including the auditor):

1. Load `OPENROUTER_API_KEY` from the repo-root `.env` into the calling process. Never print it.
2. Look up `slug` from the roster and `effort` from `council-this-run.json` `effort[key]` (else the roster row). High means that row's ceiling (`max` / `xhigh` / `high`).
3. Build the JSON with python (do not assume `jq`). Body is `{ "model": <slug>, "messages": [{ "role": "user", "content": <prompt> }] }` plus `"reasoning": { "effort": <effort> }` when effort is set. Do not add a small `max_tokens` cap.
4. `POST https://openrouter.ai/api/v1/chat/completions` with `Authorization: Bearer $OPENROUTER_API_KEY` and a 600s timeout.
5. Extract `choices[0].message.content`. If that path is missing, surface `.error.message` (or the raw body) for that door, do not invent a reply.
6. Retry a failed door once, then omit it and name it in the result. Do not replace it with a repository-aware session.

If a picked row has `door: "codex CLI"`, run it with `codex exec --sandbox read-only --ignore-user-config --skip-git-repo-check` in a newly created empty temporary directory outside the repository. Pass only the scrubbed brief on stdin.

Keep council artifacts isolated. Remove only artifacts created by this run, including `council-this-run.json`.

## Clean-room boundary

Every external prompt, including cross-examination and audit prompts, must exclude:

- proprietary methodology or card bodies;
- customer or user identities, private records, and private project data;
- credentials, infrastructure identifiers, and private repository details.

Translate necessary constraints into neutral abstractions. Before every outbound call, scan the complete payload for known confidential identifiers and credential names. Any match stops the send until the payload is rewritten. Later rounds and the audit contain the richest material and must be scanned again.

## Phase 1: Frame the brief

Create a self-contained, neutral brief containing:

1. one crisp decision question;
2. two to four credible options and why each is tempting;
3. all constraints needed to evaluate the choice;
4. the requested response: choose one option, explain why, and state the strongest argument against that choice.

Do not reveal the chair's lean. If `--brief <path>` is supplied, normalize it to this contract rather than forwarding unsafe or incomplete text.

## Phase 2: Preflight

Before spending:

1. verify the OpenRouter key is present without exposing it;
2. make bounded availability calls for the *picked* OpenRouter panel slugs and the *picked* auditor (from `council-this-run.json`), not every roster row;
3. if a picked row has `door: "codex CLI"`, verify that CLI in an empty directory; otherwise skip;
4. record available doors, requested reasoning levels, fallbacks, and cost-bearing calls.

If fewer than two participant doors are available, stop. If the auditor is unavailable, retain the required audit through the fallback chain below and label the loss of independence.

## Phase 3: Blind round

The chair writes its recommendation, reasoning, and strongest self-counter first. Then send the identical scrubbed brief independently to each available external seat. Capture each response faithfully before comparing them.

Do not let a seat see another seat, the chair's view, or repository context in this round.

## Phase 4: Reconcile

Build:

- a convergence map based on shared reasoning, discounted for correlated model families and empty agreement;
- a divergence map naming the distinct assumptions and failure modes;
- a working decision that combines the strongest arguments rather than tallying seats;
- a fair statement of every principled dissent;
- a targeted challenge for each unresolved argument.

Agreement without new reasoning is capitulation, not convergence.

### "Ask the operator" is not a permitted outcome

The council exists so the operator does not have to adjudicate. A synthesis whose operative output is *escalate to the operator* is a non-answer: it spends the panel and hands back the decision the panel was convened to settle. The chair owns the call and does not launder it into a question.

This bites when the panel's own reasoning points at escalation, a governance brief where the advisors conclude "halt and request approval". That is sound analysis of what a written rule says; it is not a decision. Convert it: decide, cite the panel's reasoning as the support, and carry any conditions the panel attached (a carve-out to record, a residual to disclose, a follow-up to file). Principled dissent still ships unchanged.

One exception: the decision needs an authority the agent does not hold and cannot be delegated, spending, outward publication, deletion, or an action the operator explicitly reserved. Those are permission gates, never the council's to settle. Name the missing authority plainly; do not dress it up as the council's conclusion. Read it narrowly: it covers authority that is *absent*, not the interpretation of authority already granted, judging whether a commission satisfies a reserved-approval clause is the council's job, not an escalation.

Precedent: a council on whether a commission satisfied a freeze clause's "explicit approval" had all panelists reason to "halt and ask". The chair relayed that as an escalation; the operator had convened the council precisely so it would carry the decision without them. The analysis was right, the escalation was the chair's error.

## Phase 5: Cross-examination

When `--rounds` is two or three and consequential disagreement remains, give each seat neutrally labeled peer positions, the working decision, and a specific challenge. Ask it to defend with stronger evidence, revise, or concede with reasons.

After each round, reconcile again. Stop when:

- the arguments reach genuine shared-reasoning convergence;
- a full round produces no material movement;
- the configured maximum of three rounds is reached.

Never keep looping merely to manufacture unanimity. Preserve any minority argument that survives.

## Phase 6: Independent synthesis audit

Give the *picked* auditor the scrubbed decision brief, faithful position summaries, convergence trajectory, surviving dissent, and proposed synthesis. Ask only whether the synthesis is faithful:

- Was dissent omitted or weakened?
- Was convergence overstated?
- Did the chair smuggle in its original preference?
- Does the surviving-risk section reflect the strongest live counterargument?

For every audit concern, revise the synthesis or defend it with explicit evidence. Ship the concern and response.

Auditor fallback order: isolated GPT CLI seat, then a reachable cross-vendor OpenRouter model. Label that the fallback also participated when true. If every external auditor is unavailable, perform a clearly marked weak self-audit; never call it independent.

## Output

Return:

- decision and chair-owned rationale;
- every blind round-one position and self-counter;
- convergence trajectory and evidence of any concessions;
- genuine convergence;
- surviving dissent and risk;
- panel omissions/substitutions;
- auditor identity, verdict, concerns, and chair responses;
- optional design-of-record location and a short provenance line.

The method resolves arguments, not votes. Empirical thresholds, retrieval tuning, and behavior already decidable by tests must use the relevant evaluation instead of this council.
