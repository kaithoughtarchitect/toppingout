# Overrides: how Topping Out uses the shared skills and agents

Topping Out's own skills (`f-*`) have the method's rules built in. The shared skills and the agents are repo-agnostic: they point to the repo profile and the repo's constitution (`AGENTS.md` or `CLAUDE.md`) instead of any one repo's paths, gates or people. This page lists only the places where **Topping Out uses a shared skill or agent in a particular way**. **Where anything disagrees with `RULES.md` or `METHOD.md`, the method wins.**

| Skill / agent | How Topping Out uses it |
|---|---|
| `skills/pack-review`, `xreview` | The independent inspection: the foreman packs and checks the brief, a fresh session of another model family runs `xreview`, the foreman adjudicates (`METHOD.md` §8 step 4) |
| `skills/adjudicate` | The foreman adjudicates; the **builder** applies, from test-first repair work orders. Only a finding that changes the scope or a locked decision goes to the owner. In the converged case (`METHOD.md` §9) the foreman makes a reviewer-specified fix itself |
| `skills/f-plancheck` | On the blueprint before `/f-schedule`, and on each job's `PLAN.md` at gate 1. First the pre-read check (`METHOD.md` §13 rule 0: an existing gate means a second read, which needs the owner's word); for a job PLAN, ask for the gate explicitly. **Never call `plan-validator` directly**: in Topping Out it's only f-plancheck's checklist |
| `skills/model-council`, `agent-council` | Only when the owner authorises autonomous resolution of a fork (`f-survey` step 5). Their verdict is advice the foreman weighs, never a decision the owner didn't make |
| `agents/handoff-builder` | Give it `templates/HANDOFF-SESSION-BRIEF.md` with `mode: full`. Its Topping Out defaults (shift handover and answer key in `foreman/handovers/`, answer key in a separate file, no commits, no push) are built in |
| any skill or agent | **never name the builder** (model, agent, vendor or tool) in any file, commit, PR or record |

A repo that adapts a skill further records its change in its own repo profile, so the next install's upgrade step (`SETUP.md` §1) can diff it.
