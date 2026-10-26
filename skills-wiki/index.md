---
title: Skills map
id: index
type: map
status: confirmed
relates:
  - f-setup
  - f-sketch
  - f-survey
  - f-blueprint
  - f-plancheck
  - f-schedule
  - f-shift
  - f-board
  - f-signoff
  - model-council
  - agent-council
  - speak
  - converse
  - f-comply
  - f-inspect
  - f-greploop
  - f-night-shift
  - orca-pi-connect
  - pack-review
  - xreview
  - adjudicate
  - f-card
  - f-search
  - f-archive
  - f-archive-search
  - f-catchup
  - f-context
  - f-distill
  - f-dream
  - f-status
  - agents/plan-validator
  - agents/simplicity-critic
  - agents/handoff-builder
  - agents/lens-code
  - agents/lens-errors
  - agents/lens-types
  - agents/lens-tests
  - agents/lens-comments
  - agents/lens-simplify
  - agents/spec-validator-fixer
  - agents/code-explorer
  - agents/lens-instructions
  - agents/lens-migrations
updated: 2026-09-25
---

# Skills map

Topping Out's skills and agents. Cold agents start here: catalog, then one map page, then that skill's `SKILL.md` or agent file. `f-*` skills are Topping Out's own; the rest are shared tools Topping Out uses.

The method itself: `../README.md` → `../METHOD.md`. The whole flow as a picture: `../flow.html`.

## Setting up

- [[f-setup]]: Install the method into a repo or upgrade it, write the repo profile, and prove the install

## Before a job: plan → project

- [[f-sketch]]: Write down a rough idea and its open questions, before anything is decided
- [[f-survey]]: Turn a rough request into clear decisions, one round of questions at a time
- [[f-blueprint]]: Write the full plan once every decision is made
- [[f-plancheck]]: Have AI models from other companies read the plan fresh and point out problems
- [[f-schedule]]: Split a big plan into jobs, in order, and draw the project board

## Settling a fork

- [[model-council]]: Ask a panel of AI models, each answering on its own, to help settle a design choice
- [[agent-council]]: Ask AI agents that can read the code to help settle a design choice

## Starting and running a job

- [[f-shift]]: Start a session as the foreman: read the role, the rules and the playbook first
- [[f-board]]: Update the project board when a job starts, merges, gets stuck or is added
- [[orca-pi-connect]]: Link the foreman to a Pi builder in the Orca pane beside it, and know when it finishes

## The end game: two inspections

- [[f-inspect]]: Have specialist reviewers check the finished job's changes and report only problems
- [[pack-review]]: Bundle the goal, the rules and the changes into one brief for an outside reviewer
- [[xreview]]: Review another session's work with fresh eyes: list each claim, never rewrite it
- [[adjudicate]]: Go through a review point by point: accept, reject, partly accept, or can't verify

## PR and merge

- [[f-greploop]]: Run an open pull request through Greptile's review, up to three rounds

## Close

- [[f-signoff]]: Close a merged job: check every requirement passed, save the lessons, file the job away

## Several jobs in a row

- [[f-night-shift]]: Run several jobs one after another without you: a shift boss opens a fresh foreman for each

## The Logbook: context that outlives a job

- [[f-card]]: Save one lesson worth keeping as a Logbook card
- [[f-search]]: Find Logbook cards about a topic
- [[f-archive]]: Move old Logbook cards to the archive when there are too many, keeping a summary set
- [[f-archive-search]]: Search the archived Logbook cards
- [[f-catchup]]: Write Logbook cards for past jobs that never got any
- [[f-context]]: Get a quick, complete picture of a repo before working in it
- [[f-distill]]: Turn the most important lessons into firm rules, with your approval
- [[f-dream]]: Look back over past jobs: merge repeated lessons and spot mistakes that keep happening

## Catch-up

- [[f-status]]: Tell you in plain words where things stand and what's next

## Rules that bind

- [[f-comply]]: Check whether the agent really follows a rule when it's tempted to break it

## Voice

- [[speak]]: Read one reply out loud as a short spoken summary
- [[converse]]: Read every reply out loud until you turn it off

**Do the agents still matter?** Yes, but fewer. The foreman plays the planning roles and the builder assembles, so the planning and assembly agents aren't used. The ones below are how the plan and the build get checked.

## Agents still in use

- [[agents/simplicity-critic]]: Find the overbuilt parts of a plan and suggest the simplest version
- [[agents/handoff-builder]]: Write the handover notes so the next session can pick up the work
- [[agents/spec-validator-fixer]]: Correct statements in a plan that are provably wrong

## Used only inside f-plancheck

- [[agents/plan-validator]]: Check a plan against the real code before it's built (used inside f-plancheck)

## Agents used as review lenses (through f-inspect)

- [[agents/lens-code]]: Look for bugs and broken project rules in the changed code
- [[agents/lens-errors]]: Find errors that get silently ignored, and risky fallbacks
- [[agents/lens-types]]: Check that the data types can't hold invalid values
- [[agents/lens-tests]]: Find changes that aren't properly tested
- [[agents/lens-comments]]: Check that comments and docs still match the code
- [[agents/lens-instructions]]: Check prompts, skills and templates for contradictions and broken references
- [[agents/lens-migrations]]: Review database changes: migrations, queries and access rules
- [[agents/lens-simplify]]: Spot code that could be simpler, without changing what it does

## Agents that are optional

- [[agents/code-explorer]]: Trace how an existing feature works through the code

## The record

The foreman plans and the builder builds from work orders; there are no planning or build agents. The job **file** and its templates (`../foreman/templates/`) are the record of every job.

Picture of the same body links: [graph.html](graph.html).
