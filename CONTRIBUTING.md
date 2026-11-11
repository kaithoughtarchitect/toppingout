# Contributing

Thanks for looking. Topping Out is small and run by one person, so the most useful help is specific.

By taking part you agree to the [code of conduct](.github/CODE_OF_CONDUCT.md).

## Most wanted

- **Reports from macOS.** It's built and run daily on Windows 11 with Claude Code as the foreman, and full jobs and night shifts also run on a Linux server through Orca (the site's Cloud setup page). CI runs the scripts' self-tests on all three systems, but a full job hasn't been run on macOS yet. If you try one, open an issue with what happened, good or bad.
- **Where it broke for you.** Use the "Something didn't work" issue template: what you ran, what you expected, what happened, your setup.
- **A rule that saved you.** Every rule in `RULES.md` exists because something went wrong once. If you have one, open an issue with the story.

## Good first ideas

- **Seeing a project's history.** Every job already leaves its records: the board's versions (in git history), the job file, its work orders and reviews, the dev report, the base-versus-head test results and the merge commit. A view of how a project changed, job by job, can be built from those without changing the method.
- **Board and site visuals.** The board page (`skills/f-board/render_board.py`) and the website (`scripts/build_site.py`) are plain generated HTML, so improvements are self-contained.
- **Docs.** Anything unclear in the README, `SETUP.md` or a skill page: say where you got stuck.

## Before you build

- **A fix:** go ahead and open a pull request.
- **A new feature, a visual, or a change to how the method works:** open an issue first, with a rough sketch. Then we can agree the shape before you spend time on it.

## Where things live

| What | Where |
|---|---|
| The method's rules and stages | `RULES.md`, `METHOD.md`, the playbooks |
| The skills (`/f-…`) | `skills/<name>/SKILL.md`, with their scripts beside them |
| Templates the foreman fills in | `templates/` |
| Small scripts a project copies (gate runner, parallel proof, site-walk grader…) | `snippets/` |
| The board tool | `skills/f-board/render_board.py` (and its test) |
| The installer and updater | `skills/f-setup/install.mjs` |
| The website | generated into `docs/` by `scripts/build_site.py`; the skill map by `scripts/build_skills_wiki.py` and `scripts/wiki_graph_html.py`; the flow page by `scripts/build_flow.py` |
| What changed, for people updating | `CHANGELOG.md` |

## Changing the package

1. Fork, branch, and keep one change per pull request.
2. Run the checks. The full list is the CI workflow, `.github/workflows/ci.yml`, which runs every one on every pull request (the installer, the end game, the names check, the board, the Logbook archive, the snippets' tests and more). Each is one command, for example `node skills/f-setup/install.mjs --self-test` or `python skills/f-board/test_render_board.py`.
3. `docs/` is the website and is generated. Edit the sources, never the pages, then rebuild with `python scripts/build_site.py`.
4. A change people will notice adds a line to `CHANGELOG.md`: `/f-setup` shows those lines to everyone who updates.
5. House style: plain language, no em dashes, and every claim backed by a file, a command or a commit. Never name a builder's model or vendor in records (`RULES.md`).

## How a pull request gets in

This public repository is a copy of the maintainer's working repository, synced from it. So a pull request is reviewed here, and once it's agreed, the maintainer applies it to the working repository and it arrives in the next sync, **with credit to you** (a co-author line on the commit and a mention in `CHANGELOG.md`). Your pull request is then closed with a link to the commit that carries it. If that ever changes, this file will say so.

## Security

Please report security problems privately, through the repo's Security tab (`.github/SECURITY.md`), not in an issue.
