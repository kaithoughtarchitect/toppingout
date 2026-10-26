# Topping Out skills and agents

30 skills and 13 agents. Every skill and agent: what it does, when to use it, how to tell it worked.

## The order of works

- [f-sketch](skills/f-sketch.md): Write down a rough idea and its open questions, before anything is decided.
- [f-survey](skills/f-survey.md): Turn a rough request into clear decisions, one round of questions at a time.
- [f-blueprint](skills/f-blueprint.md): Write the full plan once every decision is made.
- [f-plancheck](skills/f-plancheck.md): Have AI models from other companies read the plan fresh and point out problems.
- [f-schedule](skills/f-schedule.md): Split a big plan into jobs, in order, and draw the project board.
- [f-shift](skills/f-shift.md): Start a session as the foreman: read the role, the rules and the playbook first.
- [f-inspect](skills/f-inspect.md): Have specialist reviewers check the finished job's changes and report only problems.
- [pack-review](skills/pack-review.md): Bundle the goal, the rules and the changes into one brief for an outside reviewer.
- [xreview](skills/xreview.md): Review another session's work with fresh eyes: list each claim, never rewrite it.
- [adjudicate](skills/adjudicate.md): Go through a review point by point: accept, reject, partly accept, or can't verify.
- [f-greploop](skills/f-greploop.md): Run an open pull request through Greptile's review, up to three rounds.
- [f-board](skills/f-board.md): Update the project board when a job starts, merges, gets stuck or is added.
- [f-signoff](skills/f-signoff.md): Close a merged job: check every requirement passed, save the lessons, file the job away.

## Memory

- [f-card](skills/f-card.md): Save one lesson worth keeping as a Logbook card.
- [f-search](skills/f-search.md): Find Logbook cards about a topic.
- [f-archive](skills/f-archive.md): Move old Logbook cards to the archive when there are too many, keeping a summary set.
- [f-archive-search](skills/f-archive-search.md): Search the archived Logbook cards.
- [f-catchup](skills/f-catchup.md): Write Logbook cards for past jobs that never got any.
- [f-context](skills/f-context.md): Get a quick, complete picture of a repo before working in it.
- [f-distill](skills/f-distill.md): Turn the most important lessons into firm rules, with your approval.
- [f-dream](skills/f-dream.md): Look back over past jobs: merge repeated lessons and spot mistakes that keep happening.

## Toolkit

- [f-setup](skills/f-setup.md): Install the method into a repo or upgrade it, write the repo profile, and prove the install.
- [model-council](skills/model-council.md): Ask a panel of AI models, each answering on its own, to help settle a design choice.
- [agent-council](skills/agent-council.md): Ask AI agents that can read the code to help settle a design choice.
- [orca-pi-connect](skills/orca-pi-connect.md): Link the foreman to a Pi builder in the Orca pane beside it, and know when it finishes.
- [f-night-shift](skills/f-night-shift.md): Run several jobs one after another without you: a shift boss opens a fresh foreman for each.
- [f-status](skills/f-status.md): Tell you in plain words where things stand and what's next.
- [f-comply](skills/f-comply.md): Check whether the agent really follows a rule when it's tempted to break it.
- [speak](skills/speak.md): Read one reply out loud as a short spoken summary.
- [converse](skills/converse.md): Read every reply out loud until you turn it off.

## Agents

- [simplicity-critic](agents/simplicity-critic.md): Find the overbuilt parts of a plan and suggest the simplest version.
- [handoff-builder](agents/handoff-builder.md): Write the handover notes so the next session can pick up the work.
- [spec-validator-fixer](agents/spec-validator-fixer.md): Correct statements in a plan that are provably wrong.
- [plan-validator](agents/plan-validator.md): Check a plan against the real code before it's built (used inside f-plancheck).
- [lens-code](agents/lens-code.md): Look for bugs and broken project rules in the changed code.
- [lens-errors](agents/lens-errors.md): Find errors that get silently ignored, and risky fallbacks.
- [lens-types](agents/lens-types.md): Check that the data types can't hold invalid values.
- [lens-tests](agents/lens-tests.md): Find changes that aren't properly tested.
- [lens-comments](agents/lens-comments.md): Check that comments and docs still match the code.
- [lens-instructions](agents/lens-instructions.md): Check prompts, skills and templates for contradictions and broken references.
- [lens-migrations](agents/lens-migrations.md): Review database changes: migrations, queries and access rules.
- [lens-simplify](agents/lens-simplify.md): Spot code that could be simpler, without changing what it does.
- [code-explorer](agents/code-explorer.md): Trace how an existing feature works through the code.
