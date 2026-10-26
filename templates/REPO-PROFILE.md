# Repo profile

One file per product, kept in the records repo (`<records>/REPO-PROFILE-<product>.md`). Every opener points to it, so no session has to guess the environment.

| Field | Value |
|---|---|
| Method root (this folder, absolute) | `<path to the installed method folder, foreman/method/>` |
| Records repo | `<path>` (jobs, work orders, reviews, `foreman/projects/`, `foreman/logbook/`) |
| Constitution | `<AGENTS.md or CLAUDE.md>`: where `/f-distill` promotes product lessons (on the owner's word) |
| Plans and scratch folders | **fixed conventions, not settings:** ready-to-build plans in `foreman/blueprints/ready/` (`/f-blueprint` writes there, `/f-plancheck` gates there), ideas in `foreman/ideas/`, and a gitignored `scratch/` at the repo root (f-plancheck, the councils and speak write there). Add `scratch/` to `.gitignore` |
| Measurement / eval harness | `<name and command, or none>`: named here so plans validate it before any paid run |
| Target repo | `<path>`, remote `<remote>` (usually `origin`), main branch `<main>` (usually `main`). Every template writes `<remote>/<main>`; the foreman fills in the real name in each work order |
| Worktree tool and root | `<orca / git worktree>`, `<path>` |
| Shell for work orders | **Bash is required** for every command in a work order (Git Bash on Windows): the templates use Bash variables, `env -u`, process substitution and `comm`. The builder may explore in any shell |
| Gates (exact commands) | `<runner paths>`, or the repo's own gate, e.g. `python -m unittest discover -s tests -t .` |
| Test adapter | runner `<pytest / unittest / jest / vitest / go test / cargo test / other>`; its three Bash functions `run_tests`, `failed_ids`, `ran_ok` in `<records>/test-adapter.sh` (copied from `templates/TEST-ADAPTERS.md`, proved on a fixture before the first job), the branch-coverage command, and how new tests run against the previous commit's code |
| Dirty-file allowlist | `<files that may be dirty in a worktree and are never staged, e.g. an untracked lockfile; or none>`. Every state check in a work order expects exactly this list |
| Paid keys to strip on every run | `<ENV_VAR_1>`, `<ENV_VAR_2>` |
| Disposable databases / services | `<name:port>` (never the shared one: `<name:port>`) |
| Database change paths | `<migration folder and pattern, e.g. db/NNN_*.sql>`, `<query / policy paths>`, how a migration is proven and applied: a diff touching these triggers `lens-migrations` in the lens inspection, and every migration needs the owner's word |
| Ticket mode | `tracker` (`<Jira URL>`, keys are never minted) or `local` (the `TICKET-<nn>.md` file is the ticket; the site walk reads it instead of a URL) |
| Board publish mode | `artifact` (private page, first publish needs the owner's word) or `local` (`board.html` on disk only) |
| PR review bot | `Greptile` (trigger comment `@greptileai review`; `/f-greploop`, at most three rounds) or `none` (skip §10 step 2a; the description check still runs) |
| Host merge strategy | `merge commit` or `squash` (`METHOD.md` §10 step 3 verifies accordingly) |
| Plan check seats | `<the owner's standing pick for /f-plancheck, as roster ids, e.g. sol (codex CLI, $0), with its date>`: written by the first plan check from the owner's first pick in the picker; the plan check then runs without asking. Say "change the plan check seats" to pick again, or "use the picker this time" for one run |
| Framework check | `<a skill that checks a plan against the framework the product is built on: /deep with the Deep Agents add-on, another you name, or none>`: run with the ground investigation at every end game that has a next job (`METHOD.md` §10 step 7b) |
| Foreman launch command | `<how you start a foreman session here, with your usual flags, e.g. claude>`: the night shift uses it to open each job's foreman |
| Names kept out of records | the path of a **git-ignored** file holding them, one name per line, matched as a whole word, case-insensitive (default `scratch/names-kept-out.txt`), and of a git-ignored **allowed contexts** file (default `scratch/names-allowed.txt`: folder names, skill paths and gate lines that contain a name by design, e.g. a tool's own folder): `skills/f-signoff/names-check.mjs` checks every staged record at the records push (`METHOD.md` §10 step 9), and `/f-signoff` makes an early pass. The names themselves never go in a tracked file, this one included (RULES: never name the builder) |
| CI runner shape | `<what the CI runner's image has and lacks that the product depends on (e.g. "glib, no libEGL"), so the local Linux check reproduces it; or "not recorded">` |
| Builder delivery | `hand-carried pointer` or `pane link` (Orca: `orca-pi-connect`) |
| Budgets per job | max repair work orders `<n>` (default 3 per task), wall time `<h>`, foreman tokens `<n>`; exhausting one → HALT, re-scope or switch builder |
