# Maintaining this folder

**Done when** `python scripts/wiki_lint.py --strict` passes: no STALE page and no missing source. Without `--strict` the lint only reports drift, so a fresh install doesn't fail on docs that moved since the last refresh.

For whoever updates the reference. Agents that only *use* it don't need this file.

## Refresh the docs

1. Run `python scripts/fetch_docs.py`. It must report `0 failed`.
2. Run `python scripts/wiki_lint.py`. Pages whose cited sources changed show up as `STALE`, and cited pages the docs dropped as `MISSING-SOURCE`.
3. For each STALE page, re-read the changed source, fix the page, and bump `updated:`.
4. Run `python scripts/wiki_lint.py --stamp` to record the new source hashes, then `python scripts/build_lookup.py`.
5. Append an entry to `log.md`.

## New `deepagents` version

1. `python scripts/setup_sources.py --version X` replaces `sources/package/` with the new wheel; set `VERSION` in that script to X.
2. Update `wiki/versions.md` and the version named in `AGENTS.md` and `wiki/constitution.md`.
3. Run `python scripts/wiki_lint.py`; every page citing a changed package file goes STALE. Re-check each one, then run `--stamp`.
4. Run `python scripts/build_lookup.py` to regenerate the symbol table.
5. In an environment with the new version installed, run `python scripts/check_recipes.py`. It checks itself and must print `PASS: 10/10` (CI runs it on every push). Also run `python scripts/check_persistence.py sqlite 1`, then `... sqlite 2` (and Postgres if you have Docker). Any change means `wiki/agent-setup.md`, `wiki/memory-history.md` and `wiki/persistence.md` must be re-checked.
6. Re-check the constitution and `wiki/anti.md` against the new code. Replace any rule that no longer holds rather than appending.
7. Append an entry to `log.md`.

## Refresh routine (monthly, or when PyPI shows a new `deepagents`)

First run 2026-09-30 (0.7.19 → 0.7.20). About an hour, most of it re-running checks.

1. **Docs:** `python scripts/fetch_docs.py`, then `git diff --stat sources/docs`. Read the real diffs (`git diff --ignore-cr-at-eol`). Most changes are wording; look for changed code examples.
2. **Package:** check `pip index versions deepagents`, or `https://pypi.org/pypi/deepagents/json`. If it's newer: download the wheel, then `diff -rq --strip-trailing-cr` the old and new `deepagents/` folders. That lists exactly which code files changed. Read those diffs and the new CHANGELOG entry.
3. **Swap:** replace `sources/package/` with the new wheel, bump the `deepagents` pin in `requirements.txt` (or your project's dependency file), and reinstall in the venv.
4. **Re-run everything that makes a dated claim:** `check_recipes.py` (must print PASS 10/10), `check_persistence.py` passes 1 and 2 on SQLite, **and on Postgres** (Docker, port 55499), the tests, and the streaming failed-turn check if `streaming.md` or the middleware changed.
5. **Update version text honestly.** Pointer mentions (`checked against X`) move to the new version. A **dated run claim** (`ran on X on DATE`) moves only if step 4 re-ran it; otherwise leave it and add "not re-run on Y". `log.md` history and `versions.md` history lines never change.
6. **Stale pages:** `python scripts/wiki_lint.py` lists pages whose cited sources changed. Review each against the diffs from steps 1–2, fix what's wrong, then `--stamp`. Rebuild the symbol table with `python scripts/build_lookup.py`.
7. **Record:** add a `versions.md` entry (what changed, which code files) and a `log.md` entry (what was re-run). Commit, push, and confirm CI is green.
8. **Other projects:** refresh in one project, then bring the others up to date (copy `deepagents-ref/` and the `deepagents` pin, or upgrade them from the Topping Out package with `/f-setup`), and re-run their checks.

## Page rules (the linter enforces the first four)

- Frontmatter: `title`, `id` (= filename), `type`, `status` (`code` = checked against the package, `sourced` = docs only, `draft`), `product` (`sdk|dcode|managed|all`), `keywords`, `read_when`, `updated`. `sources_hash` is written by `--stamp`.
- Every `[[link]]` resolves.
- Every page is listed on `wiki/index.md`, with its keywords line.
- Shape: a one-line truth; then `## Quick reference` if the page is over ~8 KB; then sections with exact code, `## Gotchas`, `## Sources` (`../sources/...` paths) and `## See also`.
- Keep the constitution to one screen, ordered by the cost of getting each rule wrong.
- When the docs and the code disagree, write both, say the code wins, and add the stale doc example to `wiki/anti.md` and to `sources/AGENTS.md`.
- If a question had no answer here, add a row to `wiki/gaps.md`.

## Layout

| Path | What |
|---|---|
| `AGENTS.md` | Entry point for agents using the folder |
| `wiki/` | The distilled reference |
| `sources/docs/` | Raw docs; paths mirror the URLs; `MANIFEST.md` lists URLs and fetch date |
| `sources/package/` | The vendored `deepagents` wheel (ground truth) |
| `sources/AGENTS.md` | Warning read by agents that open raw files: known stale examples |
| `.ignore` | Keeps `sources/` out of default ripgrep searches |
| `scripts/fetch_docs.py` | Refreshes `sources/docs/` |
| `scripts/wiki_lint.py` | Checks structure and flags STALE pages; `--stamp` records source hashes |
| `scripts/build_lookup.py` | Regenerates the symbol table in `wiki/lookup.md` |
| `scripts/check_imports.py` | Agents' verify step: static check of a file against the vendored package |
| `scripts/check_persistence.py` | Two-process restart proof: memory, history and conversation survive (SQLite / Postgres) |
| `examples/history_backend.py` | `HistoryStoreBackend`, the checked source for `wiki/memory-history.md` |
| `scripts/check_recipes.py` | Re-runs the setup page's claims against the installed package (fake model, no API); exits 1 on any mismatch |
| `log.md` | Append-only record of refreshes and fixes |
| `../.mcp.json` | Registers layer 2, the LangChain docs MCP server `docs-langchain` |
