# J<N>: review of work order <m> (<task(s)> `<sha(s)>`) by the foreman

**A stop is not a finished work order:** before reviewing, HEAD has moved to the reported commits and the report file exists. If either is missing, it was only a turn end: read the pane, don't review.

**Disk first:** `<base>..HEAD` = <commits>; each touches only <files>; subject lines only, no trailer, not pushed; worktree `<status>`. t<k>: <n> + <n> `.exit`, `ALL DONE` both, disposable DB roles restored after each arm B; gates as t<k-1>; suite +<n> passed per arm, FAILED/ERROR lists identical to t<k-1> (sorted diff empty, both arms).

**Earlier findings re-probed:** `<probe script>` at `<head>`: <R1..Rn each now refuses, with the result>.

**Test-first claim verified independently:** `<repair commit>`'s test module run against `<previous commit>`'s code (the profile's old-code method: e.g. a scratch overlay first on `PYTHONPATH`, or a worktree at the previous commit) -> **<n> failed, <n> passed**; at head all pass. <Any disclosure the builder made, and whether the independent run agrees.>

**Security-relevant code (extra care):** <one paragraph per path: credentials, identity, user context. What is checked, in what order, what is raised after its except block, and anything not frozen or not checked, with why it is or isn't exploitable and which later work order handles it.>

**New findings:** <table R<i> / reproduction / fix, or "none">.

**Switch rule:** <"no security-class bug, no repeat of a warned finding. The builder continues." | the trigger that fired, with evidence>.

**Job file updated:** [ ] tasks ticked, plan in force, this review linked, and no blank (`<…>`) left in any phase marked done (`grep -n '<[^>]*>' <job file> | grep -v '`[^`]*<[^`]*`'`: blanks inside code spans are commands' own placeholders). A review isn't finished until this box is ticked; `/f-signoff` should never be the first to find the job file behind.
