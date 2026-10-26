---
title: Do not
id: do-not
type: rule
status: code
product: all
keywords: do not, never, hard rules, guardrails, invent API, training memory, stale answer, rules for agents, constraints, no guessing, cite sources, version pinning
read_when: Read when answering any Deep Agents question, to check the hard rules for this repo.
updated: 2026-10-21
---

# Do not

Hard nos for any agent answering from this repo. `confirmed` said 2026-09-29

- **Never invent an API.** No parameter, import path, class or default that is not in `../sources/package/` or `../sources/docs/`. Say "not found in 0.7.29" instead.
- **Never answer from training memory when the repo has the page.** Deep Agents moves fast; memory is months stale. Read the page, cite the raw path.
- **Never rewrite `../sources/`.** Refresh with `python scripts/fetch_docs.py`; distil into `wiki/`.
- **Never mix up the three products.** SDK (`deepagents`), Deep Agents Code (`dcode`, a terminal app), Managed Deep Agents (LangSmith-hosted, `mda`). See [[constitution]].
- **Never port a TypeScript/JS example as if it were Python.** Python is the target.
- **Never assume in-memory defaults persist.** State, store and checkpointer defaults die with the process; say so every time persistence matters.
- **Never state a version fact without the version.** Pin to [[versions]].

Wrong mental models to catch: [[anti]]. Raw index: [[sources]].

## See also

- [[index]]
- [[constitution]]
- [[anti]]
- [[sources]]
- [[versions]]
