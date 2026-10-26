# Raw sources: read the wiki first

You're inside the raw material. It's unedited official docs plus the `deepagents` package source (the version in `../wiki/versions.md`). Both are fetched by `python ../scripts/setup_sources.py`, not shipped with Topping Out. Default searches skip this folder (see `../.ignore`); come here only by explicit path, from a wiki page's `## Sources` section.

- **`package/` is the ground truth.** Signatures, defaults and behaviour here win over any doc.
- **`docs/` contains stale examples that break in 0.7.** The known ones:
  - `backend=lambda rt: …` and `StateBackend(rt)` / `StoreBackend(rt, …)`: backend factories were removed, so these raise `TypeError`.
  - `StoreBackend()` with no `namespace=`: the namespace is required, as a keyword.
  - Seeding `store.put(ns, "/memories/AGENTS.md", …)`: the real key is `/AGENTS.md`, because `CompositeBackend` strips the route prefix.
  - The README, `overview.md`, `products.md` and the tutorials describe planning (`write_todos`) as on by default. Since 0.7.0 it needs `TodoListMiddleware()`.
  - `task(name=…, task=…)`: the real arguments are `description` and `subagent_type`.
  - The content-builder tutorial pins `deepagents>=0.3.5,<0.4.0`, which is stale.
  - Blob offload docs say to set `artifacts_root` on the middleware; `FilesystemMiddleware` has no such argument (use `CompositeBackend(artifacts_root=...)`).
  - Managed: the memory page's `allow` example reads `context.channel` (channel runs get `context = None` since 0.9.0; use `runtime.channel`), the HTTP channel `parse` example calls `uuid.UUID` without `import uuid`, and the local-development page says schedules never run under `mda dev` (they do since 0.9.3).
- Before copying any doc example, check `../wiki/anti.md` and the matching wiki page's `## Gotchas`.
- Don't edit anything here. Refresh with `python ../scripts/fetch_docs.py` (docs) or `python ../scripts/setup_sources.py --version <v>` (a new package).
