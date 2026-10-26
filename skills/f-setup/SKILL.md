---
name: f-setup
description: >
  Install Topping Out into a repo, or upgrade an existing install, then fill in
  the repo profile, the names files and the test adapter, and prove the install.
  Use when the user runs /f-setup, says "set up Topping Out here", "install the
  method", "upgrade Topping Out", or points at the package and asks to install it.
  Never commits or pushes (the owner's word); never overwrites a file the repo
  already has, except an unadapted one during an upgrade.
---

# Topping Out: Setup

One command from an empty repo to a repo ready for its first job: the files installed, the repo profile written from what the repo actually has, the names files, the test adapter proved, and the checks run.

**First run, before the skill is installed:** start a session in the repo and say `Read <package>/skills/f-setup/SKILL.md and follow it`. The install copies this skill too, so every later run (an upgrade, a re-check) is just `/f-setup`.

**The contract:**
- **Copy only what's missing; never overwrite.** A file the repo already has may carry its adaptations (`SETUP.md` §1 "Adapt"). The installer's upgrade mode is the only path that replaces a file, and only one unchanged since the last install.
- **Find out before asking.** Read the repo for every profile field it can answer; ask the owner only what it can't, in one batch.
- **Git custody:** setup never stages, commits or pushes. It ends with the list of files for the owner's commit.
- **Secrets:** read the names of keys in `.env` files, never their values; never print a value. Never echo the names kept out of records (Step 3) into chat or a tracked file.
- Ends with one line: `F-SETUP: READY <profile path>` or `F-SETUP: HALTED <specific reason>`.

---

## Step 0 · Where things are

- **The repo:** the current working repo. If it isn't a git repo, HALT: `not a git repo`.
- **The package:** a folder holding `METHOD.md` and `skills/`:
  - the path the owner gave, or the folder this file sits in (`<package>/skills/f-setup/`);
  - an installed copy (`.claude/skills/f-setup/`) is not the package. If no package folder is at hand (the skills came from a skills installer, or this is an upgrade), clone it: `git clone <the package's repo URL> scratch/topping-out-package` (the URL the owner gives, or the one in the receipt's `package:` line). Use a full clone, not `--depth 1`: an upgrade diffs against the receipt's old revision.
- **Mode:**
  - `foreman/INSTALL-RECEIPT.txt` exists → **upgrade** (Step 1b).
  - No receipt, but `foreman/method/` or Topping Out skills in `.claude/skills/` already present → an install from before receipts. Don't run install mode (it would stamp today's revision over older files). Ask the owner for the package revision it came from, write a receipt with that `revision:` line, then upgrade. If nobody knows it, upgrade by hand (`SETUP.md` §1, "Upgrade by hand").
  - Neither → **install** (Step 1a).
- **The one question asked first:** "Is this product an AI agent built on LangChain, LangGraph or Deep Agents?" (yes / no / not sure; the repo's `requirements.txt`, `pyproject.toml` or `package.json` naming `deepagents`, `langgraph` or `langchain` makes yes the default; "not sure" is answered from those files, and none of them naming one means no). Yes adds the Deep Agents add-on (Step 1c); no skips it, and the profile's framework check is `none` unless the owner names another.
- **Prerequisites:** `git`, `node` (18 or later), `python` (3.9 or later), and a Bash shell (Git Bash on Windows): work orders run in Bash (`templates/REPO-PROFILE.md`, "Shell for work orders"). Check each with `--version`; a missing one is a HALT naming it.

## Step 1a · Install

1. `node <package>/skills/f-setup/install.mjs --repo <repo> --dry-run`: show the owner the count and the `kept …` lines (files the repo already has, which are never replaced; a skill kept under the same name may be the repo's own, so say which).
2. `node <package>/skills/f-setup/install.mjs --repo <repo>`: copies what's missing, creates the `foreman/` folders, writes `foreman/INSTALL-RECEIPT.txt` with the `installed …` lines, and adds `scratch/` to `.gitignore` unless git already ignores it. Exit 2 with "uncommitted changes" means the package checkout is dirty: report it and HALT (the receipt would name a revision that doesn't match the files).
3. **Builders that read `.agents/skills/`** instead of `.claude/`: if the repo has an `.agents/` folder or the owner names such a builder, mirror `.claude/skills/` there the same way (copy only what's missing).

## Step 1b · Upgrade

1. **A clean point:** the repo on its main branch (`git branch --show-current`), no job worktree open (`git worktree list` shows only the main checkout, or worktrees the owner says aren't jobs), no tracked changes in the files the upgrade touches.
2. `node <package>/skills/f-setup/install.mjs --repo <repo> --upgrade`: the plan, writing nothing.
   - Exit 1: a job is open (`foreman/jobs/JOB_*.md`) or an end game is owed (`foreman/ENDGAME-PENDING.md`). Report it and HALT.
   - Exit 2: report the installer's line. A receipt without a git revision, or a package clone without that revision: upgrade by hand (`SETUP.md` §1, "Upgrade by hand").
3. Show the plan. On the owner's yes: `… --upgrade --apply`.
4. **Adapted files** (changed here and in the package): for each, diff the repo's copy against the package's and merge the package's change into the adaptation by hand. Show each merge before writing it. **Gone from the package but adapted here:** ask the owner, keep or delete. **Added back:** a file listed under "add" that the repo once had and deleted on purpose (the voice trio, say): ask before keeping it.
5. Any repo-profile row that names a path the upgrade removed: update it.
6. Re-read the profile against the current `templates/REPO-PROFILE.md` and add any row the template gained since (e.g. "CI runner shape"), found out the same way as Step 2. Then the names-file check (Step 3.3) and Step 5.

## Step 1c · The Deep Agents add-on (only on yes)

0. **Needs** Python 3.11 or later (deepagents requires it). On an existing install, upgrade first (Step 1b): the installer refuses an add-on while the receipt's revision is older than the package's, since the add-on's files would then look adapted at the next upgrade.
1. `node <package>/skills/f-setup/install.mjs --repo <repo> --addon deep-agents` adds `/deep`, `deepagents-ref/` and `.mcp.json` (only if the repo has none; otherwise add its `docs-langchain` entry to the existing file and show the owner the edit). The receipt's `addons:` line records it, so later upgrades include it.
2. **A new agent project** (no product code yet): offer the running skeleton too, `… --addon deep-agents --starter` (`src/agent/`, tests, `langgraph.json`, `requirements.txt`, a CI workflow, an `AGENTS.md` to fill in). It copies only missing files and is never upgraded: from here on it's product code.
3. `python deepagents-ref/scripts/setup_sources.py` fetches what the wiki cites (the `deepagents` package at the pinned version, the live docs). Needs network and pip. The lint it runs may report STALE pages or missing sources: that's drift since the wiki was last checked, not a failure; say how many, and point to `deepagents-ref/MAINTAINING.md`. Exit 1 means the package couldn't be fetched, or no docs page arrived at all: report the line it printed (pip, network, the Python version) and HALT the add-on step; pages that fail one by one are reported as drift and don't fail it.
4. The profile's framework check row: `/deep`. A Pi builder reads `.agents/skills/`: mirror `deep` there too.
5. With the skeleton: `python -m venv .venv`, then install with the venv's own Python (`.venv/Scripts/python -m pip install -r requirements.txt`; macOS/Linux `.venv/bin/python`). After Step 4, the tests through the adapter must show 6 passed; `.env` gets `OPENROUTER_API_KEY` from the owner, never from chat (they paste it into the file).

See `addons/deep-agents/README.md` in the package for what each part does.

## Step 2 · The repo profile

Write `foreman/REPO-PROFILE-<product>.md` from `foreman/method/templates/REPO-PROFILE.md`: every row filled, none left with a template blank. A row nothing can answer yet says `not recorded` and why.

**Find out first** (read-only):

| Row | Where to look |
|---|---|
| Method root | the installed `foreman/method/` (absolute path) |
| Records repo, single or two repos | single-repo is the default: this repo holds both, records under `foreman/`. Ask only if the product lives in another repo |
| Constitution | `AGENTS.md` or `CLAUDE.md` at the root (or `none yet`) |
| Measurement / eval harness | `package.json` scripts named `eval`/`bench`, an `evals/` or `benchmarks/` folder; else `none` |
| Target repo, remote, main branch | `git remote -v`, `git symbolic-ref refs/remotes/origin/HEAD` (fall back to `main`/`master`) |
| Worktree tool | `orca` on PATH → `orca`; else `git worktree`, root beside the repo |
| Gates and test runner | `package.json` scripts (`test`, `lint`, `typecheck`, `build`), `pyproject.toml`/`pytest.ini`/`setup.cfg`, `go.mod`, `Cargo.toml`, `Makefile` targets, CI workflow files (`.github/workflows/*`: the commands CI runs are the gates) |
| Dirty-file allowlist | after the dependency install the gates need, `git status --porcelain` in a fresh worktree: the files that show up and are never staged (an untracked lockfile, say); else `none` |
| CI runner shape | the CI workflow's `runs-on` and install steps (system packages it adds); else `not recorded` |
| Paid keys to strip | key **names** in `.env`, `.env.example`, the code's environment reads (`process.env.X`, `os.environ["X"]`) that look like provider keys (`*_API_KEY`, `*_TOKEN`) |
| Database change paths | `migrations/`, `db/`, `alembic/`, `prisma/`, `supabase/migrations/` |
| Disposable databases | `docker-compose*.yml` services and ports |
| PR review bot | `.greptile*` config, or a Greptile comment on a recent PR (`gh pr list --state merged -L 5`, then its comments) |
| Host merge strategy | `gh repo view --json mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed` |
| Foreman launch command | the command running this session (`claude`, with the flags the owner uses) |
| Framework check | `/deep` when the add-on went in (Step 1c); otherwise `none`, or a skill the owner names that checks plans against their framework |

**Then ask the owner, in one batch**, only what's left; typically: the product name (for the file name), ticket mode (`local` unless they use a tracker), board publish mode (`local` or `artifact`), the plan check seats (or leave to the first plan check), builder delivery (`hand-carried pointer` or `pane link`), the three budgets (repair work orders, default 3 per task; wall time; foreman tokens), the builders' names for Step 3, and anything the reading left ambiguous (two candidate gate commands, say). Offer the found answer as the default in each question.

## Step 3 · The names files

The records never name the builders' model, vendor or tool (`RULES.md`). The names live in a git-ignored file the records push checks against (`METHOD.md` §10 step 9), where an empty or unreadable file is exit 2, never a pass.

1. Write `scratch/names-kept-out.txt` (the profile's default path): the names the owner gave, one plain name per line, no regex characters. **Never leave it empty:** if the owner names none, seed it from the builders the profile and `foreman/method/BUILDER-PROFILES.md` name, as `/f-signoff` does, and say so. Write `scratch/names-allowed.txt` too: contexts that contain a name by design, such as a builder tool's own folder (`.pi/`); empty is fine. Confirm `git check-ignore scratch/names-kept-out.txt` succeeds.
2. `node .claude/skills/f-signoff/names-check.mjs --self-test` must print `ok scan  ok clean  ok cli`.
3. The real file: `node .claude/skills/f-signoff/names-check.mjs --names scratch/names-kept-out.txt --allow scratch/names-allowed.txt foreman/method/RULES.md` must exit 0 or 1 (1 only means the file mentions a name; report the count, never the hit lines). Exit 2 is a broken names file (empty, or a regex line): fix it and run again.
4. The profile holds only the paths, never the names.

## Step 4 · The test adapter

1. From `foreman/method/templates/TEST-ADAPTERS.md`, copy the block for the profile's runner into `foreman/test-adapter.sh`; set its paid-key list from the profile.
2. **Line endings:** `git check-attr eol -- foreman/test-adapter.sh`. If it isn't `lf` and the machine has `core.autocrlf=true`, a checkout turns the script CRLF and Bash breaks on it: propose `*.sh text eol=lf` in `.gitattributes` (for the owner's commit) and say why (`SETUP.md` §8).
3. **Prove it** (the two-fixture check the template asks for): two folders holding the **same** test file, placed where the runner collects tests (jest `roots`/`testMatch` and Go packages may not look in `scratch/`), with tests A, B and C. In the base folder A and C fail; in the head folder B and C fail. Run each from its own folder under the money guard (`( cd <base> && env -u <each paid key> bash -c 'source foreman/test-adapter.sh; run_tests …' )`, the same for head), check `ran_ok` on both, then `comm -13 <(failed_ids <base output>) <(failed_ids <head output>)` must print **only B**: C proves a shared failure isn't reported, and the same file in both proves the IDs are stable. Delete the fixtures after.
4. In the profile's "Test adapter" row record the runner, the proof (command, date, the line `comm` printed), the branch-coverage command and how new tests run against the previous commit's code (defaults for each runner: `TEST-ADAPTERS.md`, "Coverage and the old-code check").
5. A runner with no block in the template: write the three functions (`run_tests`, `failed_ids`, `ran_ok`) to the same contract and prove them the same way; say so in the report.

## Step 5 · The checks

Run each, read its exit code (a crash is not a pass), and report the line:

| Check | Pass |
|---|---|
| `python .claude/skills/f-board/test_render_board.py` | `OK` |
| `node .claude/skills/f-signoff/names-check.mjs --self-test` | `ok scan  ok clean  ok cli` |
| `node .claude/skills/f-setup/install.mjs --self-test` | every line `ok` |
| `node .claude/skills/f-setup/install.mjs --repo . --pkg <package> --dry-run` | `0 file(s) would be installed` (a file the repo deleted on purpose shows here: name it, it isn't a failure) |
| no template blank left in the profile | `grep -nF -f <(grep -o '<[^>]*>' foreman/method/templates/REPO-PROFILE.md | sort -u | grep -vxE '<(remote|main|records|product|nn)>') foreman/REPO-PROFILE-<product>.md` prints nothing (the five left out are the template's own wording, e.g. `<remote>/<main>`, not blanks) |
| the gates named in the profile run | each gate command once, under the money guard; a red gate is recorded as the repo's starting state, not a setup failure |

## Step 6 · Report

- What was installed or upgraded (counts, and any adapted files merged or left).
- The profile path and the rows marked `not recorded`.
- The optional add-ons and what each still needs (`SETUP.md` §1: voice, the councils, `f-comply`; the pane link, `SETUP.md` §4).
- **For the owner's commit:** the exact paths setup created or changed (never `scratch/`). Setup doesn't commit.
- **Next:** the first job (`SETUP.md` §7): `/f-sketch` for an idea, `/f-schedule` for a big plan, or the first-job opener.

Then the terminal line: `F-SETUP: READY foreman/REPO-PROFILE-<product>.md`.
