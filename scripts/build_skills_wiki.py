"""Build skills-wiki/: one page per skill and agent, plus index.md.

The descriptions live in SKILLS, AGENTS and GROUPS below. Change them here, then run:
    python scripts/build_skills_wiki.py
    python scripts/wiki_lint.py skills-wiki
    python scripts/skills_wiki_sync.py
    python scripts/wiki_graph_html.py skills-wiki "Topping Out Skill Atlas"
Never hand-edit the generated pages; they are overwritten.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W = ROOT / "skills-wiki"
(W / "agents").mkdir(parents=True, exist_ok=True)
DATE = "2026-09-25"

# name: (one-liner, role-in-foreman, body line, uses, used_by, used_after)
SKILLS = {
    "f-setup": ("Install the method into a repo or upgrade it, write the repo profile, and prove the install",
               "Before the first job, once per repo, and again for each upgrade (never while a job is open).",
               "The first time, the skill isn't in the repo yet: tell the session to read the package's `skills/f-setup/SKILL.md` and follow it. It reads the repo for the gates, remotes and keys before asking you anything, never overwrites a file the repo already has, and never commits.",
               ["f-board", "f-signoff"], [], []),
    "f-sketch": ("Write down a rough idea and its open questions, before anything is decided",
               "Before a job, the very first step: when an idea is worth keeping but not ready to decide.",
               "A notes file, not a plan: what's agreed so far, the open questions and the options turned down. When it's ready it moves on to [[f-survey]].",
               [], [], []),
    "f-survey": ("Turn a rough request into clear decisions, one round of questions at a time",
                "Before a job, step 1: turning an idea into decisions.",
                "It settles each choice by checking the actual code, so the plan written next has no open questions.",
                ["model-council", "agent-council", "speak"], [], ["f-sketch"]),
    "f-blueprint": ("Write the full plan once every decision is made",
                      "Before a job, step 2: the full plan for a project, checked next by [[f-plancheck]] and then split into jobs by [[f-schedule]].",
                      "It sets the goal, the decisions that are fixed, what must be true when it's done, the tasks, and anything that needs your approval. No code yet.",
                      [], [], ["f-survey"]),
    "f-plancheck": ("Have AI models from other companies read the plan fresh and point out problems",
                  "Before a job, step 3, between [[f-blueprint]] and [[f-schedule]]: the plan has to pass this check before it's split into jobs.",
                  "One to five AI models from other companies read the plan side by side, all with the same checklist, and their findings are combined, never voted on.",
                  ["agents/plan-validator"], [], ["f-blueprint"]),
    "f-schedule": ("Split a big plan into jobs, in order, and draw the project board",
                    "Before a job, step 4: it won't start on a plan that hasn't passed the plan check, and it waits for your go before writing anything.",
                    "Anything that needs research or your decision becomes its own job, every requirement belongs to a job, and the ticket wording is copied exactly. It writes the project's folder and its board.",
                    ["f-board", "agents/simplicity-critic"], [], ["f-plancheck"]),
    "f-shift": ("Start a session as the foreman: read the role, the rules and the playbook first",
                      "Job start: the first command of every new session. It loads the lessons from past jobs that apply to this one.",
                      "It reads the method, the rules, the playbook and the builder's notes, checks the job's facts for itself, then looks over the repo before any work starts.",
                      ["f-plancheck", "f-board"], [], []),
    "f-board": ("Update the project board when a job starts, merges, gets stuck or is added",
                "Throughout a project: marks a job as started when you say go, merged after the merge, and stuck when it stops.",
                "It works out by itself which jobs are ready and which are waiting, counts each change as a new version, and republishes the board page at the same link. When every job is done the board tops out: it is frozen as the project's record, and the next head gets a new board. An iteration board takes small jobs as they are found.",
                [], ["f-schedule", "f-shift"], ["f-signoff"]),
    "f-signoff": ("Close a merged job: check every requirement passed, save the lessons, file the job away",
                "After the merge: closes the job only when every requirement has passed, with nothing put off for later.",
                "Then come the dev report, the choice of the next job, the board update and the handover, in that order. At the board's head it tops the project out instead: a topping out report, the frozen board, and candidate next heads for you to pick from.",
                ["agents/spec-validator-fixer"], [], []),
    "model-council": ("Ask a panel of AI models, each answering on its own, to help settle a design choice",
                      "Before a job, when you allow it: [[f-survey]] can ask it to settle a design choice that doesn't need the code.",
                      "The panel only sees a written brief, never the code. It needs an OpenRouter key.",
                      [], [], []),
    "agent-council": ("Ask AI agents that can read the code to help settle a design choice",
                      "Before a job, optional: [[f-survey]] can ask it about a choice only the code can answer, if you allow the code to be shared.",
                      "A heavier version of [[model-council]]: the agents run on your AI subscriptions and can read the repo.",
                      [], [], []),
    "speak": ("Read one reply out loud as a short spoken summary",
              "Any time: the voice add-on. It can also read [[f-survey]] rounds aloud.",
              "Needs `scripts/speak.ts`, an OpenRouter key and Node.",
              [], [], []),
    "converse": ("Read every reply out loud until you turn it off",
                 "Any time: like [[speak]], but it keeps going for every reply until you stop it.",
                 "Uses the same voice setup as [[speak]].",
                 ["speak"], [], []),
    "f-comply": ("Check whether the agent really follows a rule when it's tempted to break it",
                 "Before trusting a new builder, or before making a rule automatic: it checks that the rules in RULES.md are really followed.",
                 "It grades what the session actually did, not what it said. A result that isn't clear counts as a fail.",
                 [], [], []),
    "f-inspect": ("Have specialist reviewers check the finished job's changes and report only problems",
               "Near the end of a job, the first of two reviews: the foreman runs it once the build is finished, before any pull request. Small, low-risk jobs skip it.",
               "It reviews only this job's changes, makes no fixes and gives no verdict, just findings. The record goes in `templates/LENS-INSPECTION.md`.",
               ["agents/lens-code", "agents/lens-tests", "agents/lens-errors", "agents/lens-types", "agents/lens-comments", "agents/lens-instructions", "agents/lens-migrations", "agents/lens-simplify"], [], []),
    "f-greploop": ("Run an open pull request through Greptile's review, up to three rounds",
                   "After you open the pull request and say \"greploop\", before you say \"merge\". Then the pull request's description is checked, on every job.",
                   "Each finding is checked, the builder makes the fixes, the tests run again every round, and the fixes are pushed with your permission.",
                   ["adjudicate"], [], ["f-inspect"]),
    "f-night-shift": ("Run several jobs one after another without you: a shift boss opens a fresh foreman for each",
                      "When you type /goal night shift with a list of jobs, or a number of jobs to pick: usually before you sleep.",
                      "Each job is its own autonomous run; the boss only starts it and checks the repo. Any stop ends the shift, and so does a completed topping out (the next head is yours to pick); the morning summary is one file.",
                      [], [], ["f-signoff"]),
    "orca-pi-connect": ("Link the foreman to a Pi builder in the Orca pane beside it, and know when it finishes",
                        "Handing work to the builder in Orca: the foreman sends each work order itself and is woken up when the builder finishes.",
                        "Comes with Pi's finish signal, starts Pi inside the job's folder without the trust question, and binds a pane it opened itself without asking.",
                        [], [], []),
    "pack-review": ("Bundle the goal, the rules and the changes into one brief for an outside reviewer",
                    "Near the end, the second review: **the foreman** writes one brief for an outside reviewer once the first review's fixes are in, and checks it before it goes out (`templates/PACK-REVIEW.md`).",
                    "It removes anything that names a model or an AI company, so the reviewer judges the work, not who wrote it.",
                    [], [], ["f-inspect"]),
    "xreview": ("Review another session's work with fresh eyes: list each claim, never rewrite it",
                "The second review: run in a **new session from a different AI company** (codex when the foreman is Claude), by hand or with `scripts/cross-review-dispatch.mjs`.",
                "It starts by confirming it hasn't seen the work before, and it never counts on work the same session wrote.",
                [], [], ["pack-review"]),
    "adjudicate": ("Go through a review point by point: accept, reject, partly accept, or can't verify",
                   "The second review: **the foreman** goes through the outside reviewer's findings, and the accepted fixes go to the builder as a work order.",
                   "Every point is checked against the code first. How sure the reviewer sounded doesn't count as evidence.",
                   [], [], ["xreview"]),
    "f-card": ("Save one lesson worth keeping as a Logbook card",
               "The Logbook (the project's memory of lessons): any time something worth keeping is learned, during a job or not.",
               "Each card is a lesson (why), a method (how) or a record of what was built, written from the templates in `foreman/logbook/entries/`, with its evidence.",
               [], [], []),
    "f-search": ("Find Logbook cards about a topic",
                 "The Logbook: any time. [[f-shift]] uses it to load the lessons that apply to a job.",
                 "Searches current cards only; older ones are in [[f-archive-search]].",
                 [], ["f-shift"], []),
    "f-archive": ("Move old Logbook cards to the archive when there are too many, keeping a summary set",
                  "The Logbook: [[f-shift]] runs it by itself once there are more than 250 cards.",
                  "Moves older cards to `foreman/logbook/archived/` and keeps a short summary set, as `ARCHIVE-SYSTEM.md` describes.",
                  [], ["f-shift"], []),
    "f-archive-search": ("Search the archived Logbook cards",
                         "The Logbook: when [[f-search]] finds nothing and the lesson may be older.",
                         "Searches `foreman/logbook/archived/`.",
                         [], [], ["f-search"]),
    "f-catchup": ("Write Logbook cards for past jobs that never got any",
                  "The Logbook: once to fill it from past jobs, or after a gap. It shows you what's missing and waits for a yes.",
                  "Checks each lesson against its job before writing it, and skips jobs with nothing to learn.",
                  ["agents/code-explorer"], [], []),
    "f-context": ("Get a quick, complete picture of a repo before working in it",
                  "The Logbook: when you're new to a repo, or before rethinking a plan. At a job's start, [[f-shift]] already does this for the job.",
                  "It only reads, never changes anything. It can trace features with code-explorer, and `--deep` also digs through the commit history.",
                  ["agents/code-explorer"], [], []),
    "f-distill": ("Turn the most important lessons into firm rules, with your approval",
                  "The Logbook: now and then. Lessons about the product become rules in the repo's own instructions; lessons about the method become Foreman rules.",
                  "Shows you the proposed rules first and writes nothing until you approve them.",
                  [], [], []),
    "f-dream": ("Look back over past jobs: merge repeated lessons and spot mistakes that keep happening",
                "The Logbook: now and then. It shows what it would change first, and only applies it with your permission.",
                "Every change can be undone, and it never removes a card marked critical.",
                [], [], []),
    "f-status": ("Tell you in plain words where things stand and what's next",
                 "Only when you ask. Different from the short status lines at the end of every reply.",
                 "It only uses what's in the current session and runs no tools.",
                 [], [], []),
}

AGENTS = {
    "plan-validator": ("Check a plan against the real code before it's built (used inside f-plancheck)",
                       "Not used on its own: [[f-plancheck]] gives its checklist to every reader."),
    "simplicity-critic": ("Find the overbuilt parts of a plan and suggest the simplest version",
                          "Used, optionally, on the foreman's plan, and on a big project being split in [[f-schedule]]."),
    "handoff-builder": ("Write the handover notes so the next session can pick up the work",
                        "Used at the end of every job that has a next job, from `templates/HANDOFF-SESSION-BRIEF.md`; the answers to its quiz go in a separate file. A topping out writes none."),
    "lens-code": ("Look for bugs and broken project rules in the changed code",
                      "Used as a reviewer inside [[f-inspect]], the first end-of-job review."),
    "lens-errors": ("Find errors that get silently ignored, and risky fallbacks",
                              "Used as a reviewer inside [[f-inspect]]."),
    "lens-types": ("Check that the data types can't hold invalid values",
                             "Used as a reviewer inside [[f-inspect]]."),
    "lens-tests": ("Find changes that aren't properly tested",
                         "Used as a reviewer inside [[f-inspect]]; it adds to the test-coverage check every work order already runs."),
    "lens-comments": ("Check that comments and docs still match the code",
                         "Used as a reviewer inside [[f-inspect]]."),
    "lens-simplify": ("Spot code that could be simpler, without changing what it does",
                        "Used as a reviewer inside [[f-inspect]]; it never edits code while a job is being built."),
    "spec-validator-fixer": ("Correct statements in a plan that are provably wrong",
                             "Used at close: [[f-signoff]] hands it the job file to correct anything the record says that the code doesn't."),
    "code-explorer": ("Trace how an existing feature works through the code",
                      "Optional: the foreman can use it while planning."),
    "lens-instructions": ("Check prompts, skills and templates for contradictions and broken references",
                             "Used as a reviewer inside [[f-inspect]] when skills, prompts or templates change; also used to check Topping Out itself after an edit."),
    "lens-migrations": ("Review database changes: migrations, queries and access rules",
                              "Used as a reviewer inside [[f-inspect]] when the changes touch the database. Every database change also needs your approval."),
}


# when to reach for each one, in plain words (the Atlas shows this; the skills' own descriptions stay as the agents' triggers)
WHEN = {
    'f-setup': 'When a repo should start running the method, or a newer package should go over an existing install.',
    'f-sketch': "When you have an idea worth writing down but you're not ready to decide anything about it yet.",
    'f-survey': 'When a request is still vague or has open choices, before anyone writes the plan.',
    'f-blueprint': "When every choice is settled and it's time to write the plan for the whole project.",
    'f-plancheck': "After a plan is written and before it's split into jobs; also on a job's own plan before its second work order.",
    'f-schedule': 'When a plan has passed the plan check and is ready to be split into jobs.',
    'f-shift': 'At the start of every foreman session, before looking at any ticket.',
    'f-board': 'Whenever a job starts, merges, gets stuck or is added, so the board stays true.',
    'f-signoff': "Right after a job's pull request is merged and the merge is confirmed.",
    'model-council': "When a design choice is stuck between options and you've agreed to let AI models weigh in.",
    'agent-council': "When a design choice depends on what's in the code and you've agreed to let agents read it.",
    'speak': "When you'd rather hear a reply than read it.",
    'converse': 'When you want every reply read aloud for a stretch of work.',
    'f-comply': 'Before you trust a new builder with real work, or before turning a rule into an automatic check.',
    'f-inspect': "When a job's build is finished and its tests pass, before the pull request is opened.",
    'f-greploop': 'After the pull request is open, when you say "greploop".',
    'f-night-shift': 'Before you sleep, when the next jobs are on the board and you want them built one after another without you.',
    'orca-pi-connect': 'When the builder runs in an Orca pane next to the foreman.',
    'pack-review': "Once the first review's fixes are in, to prepare the brief for the outside reviewer.",
    'xreview': 'When the brief is ready and a session from a different AI company can review the work.',
    'adjudicate': "When the outside reviewer's findings come back.",
    'f-card': 'Whenever you learn something worth remembering for future jobs.',
    'f-search': 'When you want to know what past jobs learned about a topic.',
    'f-archive': 'When the Logbook passes 250 cards (f-shift does it for you).',
    'f-archive-search': 'When a normal Logbook search finds nothing and the lesson might be old.',
    'f-catchup': 'When past jobs finished without anyone saving their lessons.',
    'f-context': "When you arrive at a repo you don't know, or before re-planning work.",
    'f-distill': 'Now and then, when some lessons keep coming up and deserve to become firm rules.',
    'f-dream': 'Now and then, to tidy the Logbook: merge repeats and spot patterns.',
    'f-status': 'When you want a plain summary of where things stand.',
    'plan-validator': "You don't call it yourself: f-plancheck uses it for every reader.",
    'simplicity-critic': 'When a plan or a project split looks bigger than it needs to be.',
    'handoff-builder': 'At the end of every job that has a next job, to write the notes for the next session.',
    'lens-code': 'In every end-of-job review; it always runs.',
    'lens-errors': 'When the changes touch error handling or fallbacks.',
    'lens-types': 'When the changes touch data types, schemas or rules about valid values.',
    'lens-tests': 'When tests changed, or changed behaviour has no test.',
    'lens-comments': 'When comments or documentation changed.',
    'lens-simplify': 'Last in every end-of-job review, as a report only.',
    'spec-validator-fixer': "At close, when the job record says something the code doesn't.",
    'code-explorer': 'When the foreman needs to understand how an existing feature works.',
    'lens-instructions': 'When skills, prompts, agents or templates changed.',
    'lens-migrations': 'When the changes touch the database.',
}


def fm(title, pid, typ, relates):
    rel = "\n".join(f"  - {r}" for r in relates)
    return f"---\ntitle: {title}\nid: {pid}\ntype: {typ}\nstatus: confirmed\nrelates:\n{rel}\nupdated: {DATE}\n---\n\n"


def skill_page(name):
    one, role, line, uses, used_by, after = SKILLS[name]
    relates = ["index"] + uses + used_by + after
    body = [f"# {name}", "", f"Slash: `/{name}`. Folder: `skills/{name}/SKILL.md`.", "", one[0].upper() + one[1:] + ".", "",
            f"**On site:** {role}", "", line, "", f"**When to use it:** {WHEN[name]}", ""]
    edges = [f"- uses [[{u}]]" for u in uses] + [f"- used by [[{u}]]" for u in used_by] + [f"- used after [[{u}]]" for u in after]
    if edges:
        body += ["## Links", ""] + edges + [""]
    body += ["## See also", "", "- [[index]]", ""]
    return fm(name, name, "skill", list(dict.fromkeys(relates))) + "\n".join(body)


def agent_page(name):
    one, role = AGENTS[name]
    pid = f"agents/{name}"
    users = [s for s, v in SKILLS.items() if pid in v[3]]
    relates = ["index"] + users
    body = [f"# {name}", "", f"Agent: `agents/{name}.md`.", "", one[0].upper() + one[1:] + ".", "",
            f"**On site:** {role}", "", f"**When to use it:** {WHEN[name]}", ""]
    users = sorted(users, key=lambda u: (u != "f-inspect", u))
    if users:
        label = {"f-inspect": "used by [[f-inspect]] (the lens inspection, inside a job)"}
        body += ["## Links", ""] + [f"- {label.get(u, f'used by [[{u}]]')}" for u in users] + [""]
    body += ["## See also", "", "- [[index]]", ""]
    # role text may carry [[...]] links: add them to relates so NEIGHBOR holds both ways
    import re
    for m in re.findall(r"\[\[([^\]]+)\]\]", role):
        if m not in relates:
            relates.append(m)
    return fm(name, pid, "agent", relates) + "\n".join(body)


for n in SKILLS:
    (W / f"{n}.md").write_text(skill_page(n), encoding="utf-8", newline="\n")
for n in AGENTS:
    (W / "agents" / f"{n}.md").write_text(agent_page(n), encoding="utf-8", newline="\n")

GROUPS = [
    ("Setting up", ["f-setup"]),
    ("Before a job: plan → project", ["f-sketch", "f-survey", "f-blueprint", "f-plancheck", "f-schedule"]),
    ("Settling a fork", ["model-council", "agent-council"]),
    ("Starting and running a job", ["f-shift", "f-board", "orca-pi-connect"]),
    ("The end game: two inspections", ["f-inspect", "pack-review", "xreview", "adjudicate"]),
    ("PR and merge", ["f-greploop"]),
    ("Close", ["f-signoff"]),
    ("Several jobs in a row", ["f-night-shift"]),
    ("The Logbook: context that outlives a job", ["f-card", "f-search", "f-archive", "f-archive-search", "f-catchup", "f-context", "f-distill", "f-dream"]),
    ("Catch-up", ["f-status"]),
    ("Rules that bind", ["f-comply"]),
    ("Voice", ["speak", "converse"]),
]
AG_GROUPS = [
    ("Agents still in use", ["simplicity-critic", "handoff-builder", "spec-validator-fixer"]),
    ("Used only inside f-plancheck", ["plan-validator"]),
    ("Agents used as review lenses (through f-inspect)", ["lens-code", "lens-errors", "lens-types", "lens-tests", "lens-comments", "lens-instructions", "lens-migrations", "lens-simplify"]),
    ("Agents that are optional", ["code-explorer"]),
]
all_ids = list(SKILLS) + [f"agents/{a}" for a in AGENTS]
idx = [fm("Skills map", "index", "map", all_ids).rstrip("\n"), "", "# Skills map", "",
       "Topping Out's skills and agents. Cold agents start here: catalog, then one map page, then that skill's `SKILL.md` or agent file. `f-*` skills are Topping Out's own; the rest are shared tools Topping Out uses.", "",
       "The method itself: `../README.md` → `../METHOD.md`. The whole flow as a picture: `../flow.html`.", ""]
for title, names in GROUPS:
    idx += [f"## {title}", ""] + [f"- [[{n}]]: {SKILLS[n][0]}" for n in names] + [""]
idx += ["**Do the agents still matter?** Yes, but fewer. The foreman plays the planning roles and the builder assembles, so the planning and assembly agents aren't used. The ones below are how the plan and the build get checked.", ""]
for title, names in AG_GROUPS:
    idx += [f"## {title}", ""] + [f"- [[agents/{n}]]: {AGENTS[n][0]}" for n in names] + [""]
idx += ["## The record", "", "The foreman plans and the builder builds from work orders; there are no planning or build agents. The job **file** and its templates (`../foreman/templates/`) are the record of every job.", "", "Picture of the same body links: [graph.html](graph.html).", ""]
(W / "index.md").write_text("\n".join(idx), encoding="utf-8", newline="\n")

(W / "README.md").write_text("""# Skills wiki

Mirror graph of the **runnable** skills in `skills/` and the agents in `agents/`.

**Folders run. This wiki maps.** Cold start: `[[index]]`. The process: `../METHOD.md`. The flow: `../flow.html`.

A skill is not done until `skills/<name>/SKILL.md` **and** `skills-wiki/<name>.md` exist. Agents live in `skills-wiki/agents/`.

```
python scripts/wiki_lint.py skills-wiki
python scripts/wiki_graph_html.py skills-wiki "Topping Out Skill Atlas"
python scripts/skills_wiki_sync.py .
```
""", encoding="utf-8", newline="\n")

(W / "_template.md").write_text(f"""---
title: skill-name
id: skill-name
type: skill
status: draft
relates:
  - index
updated: {DATE}
---

# skill-name

Slash: `/skill-name`. Folder: `skills/skill-name/SKILL.md`.

One line: what it does. Do not paste the SKILL.md.

**On site:** where it sits in the flow, or "form B only".

## See also

- [[index]]
""", encoding="utf-8", newline="\n")
print("pages:", len(SKILLS), "skills,", len(AGENTS), "agents")
