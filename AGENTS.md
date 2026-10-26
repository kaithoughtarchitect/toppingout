# AGENTS.md

For coding agents that open this repository. Humans: start with `README.md`.

## What this is

Topping Out is a method and a set of skills for running AI coding agents one ticket at a time, for hours, without drifting. A **foreman** session plans each job and never writes product code; a cheaper **builder** model does the work; **inspectors** (one from another model family) review it; the **owner** gives the word for merges, pushes and other reserved acts. Every job starts a fresh session from files and ends with a record of what was asked, built, tested and found.

## If the user wants to use Topping Out in their own project

Don't copy files by hand. In the repo that will hold the user's records, read `skills/f-setup/SKILL.md` from this checkout and follow it. It runs `skills/f-setup/install.mjs`, profiles the repo, and asks only what it can't find.

- Needs `git`, Node 18+, Python 3.9+ and Bash (`/f-setup` checks each).
- Tested on Windows 11 with Claude Code as the foreman. macOS and Linux are expected to work but are not verified yet (`SETUP.md`, "Tested setup").
- The installer copies only what a project needs (skills, agents, templates, the method). It never copies `docs/`, the wiki, `.github/` or this file.

## Where things are

| Path | What it is |
|---|---|
| `README.md` | what it is and how a job runs, from the owner's side |
| `METHOD.md` | the process the foreman follows, step by step |
| `RULES.md` | the acts that need the owner's word, and the exceptions |
| `SETUP.md` | installing, requirements, the tested setup |
| `skills/` | the skills (`f-` for foreman), each with a `SKILL.md` |
| `agents/` | the review lenses and helper agents the skills call |
| `templates/` | work orders, reviews, ledgers, handovers |
| `docs/` | the website at toppingout.dev, **generated** by `scripts/build_site.py`: edit the sources, never the pages |

## If you are changing this package

- Run the checks for what you touched, for example `node skills/f-setup/install.mjs --self-test`, `python skills/f-board/test_render_board.py`, `node skills/f-comply/comply.test.mjs`.
- Keep the house style: plain language, no em dashes, every claim backed by a file, a command or a commit.
- Never name the builder's model or vendor in records (`RULES.md`).
