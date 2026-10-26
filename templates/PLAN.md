# J<N> plan: <KEY>, <goal>

**By:** the foreman, <date> (form A, the foreman plans: `METHOD.md` §5). **Built on:** `<scoping file>` (forks F1–F<n> settled). **Cold-read by:** `/f-plancheck` on <date> (`gate: plancheck` line below; seats <families>), findings applied or answered: <list or "none">.
The builder receives this as **the plan in force** in work order 2 and copies it into the job file's Phases 1–4.

## 1 · Requirements
Every acceptance criterion and scope clause, **verbatim** (original language), numbered R1..Rn, each with how it will be met or why it's NOT MET (and whose decision that is).
Explicit exclusions: what belongs to other tickets, with the evidence.

## 2 · Design
Components (new modules, classes, signatures), data flow for each path, error handling (every failure → an exact typed error), what is injected, what is never imported, what does not change (defaults, routes, schema).

## 3 · Tasks

| Task | Owns (files) | Decisions it carries | Tests that must FAIL first | Existing tests to run before its commit |
|---|---|---|---|---|
| T1 | | D-… | | |

One task = one work order (light builder). Repairs from a review go in PART A of the next work order, or a `<m>b` correction.

## 4 · Verification points
The table `/f-signoff` and the acceptance ledger read (columns exactly):

| # | Type | Description | Requirement | Selector/Probe |
|---|---|---|---|---|
| VP1 | positive / negative | | R… | test name or probe id |

At least 3 negative VPs.

## 5 · Proof plan
Unit tests per task; the database proof (which disposable DB, and that it can fail first); the mutation probes (one per guard, written with the guard); base-vs-head at the end.

## Plan check findings

<f-plancheck writes its `**gate: plancheck**, …` line here, on its own line directly under this heading, unprefixed: request the gate explicitly, since a job PLAN isn't under `foreman/blueprints/ready/`> One read per plan; a second only on the owner's word (check first: `grep -nE '^\*{0,2}gate: plancheck'` on this file). Findings are copied here from f-plancheck's output by the foreman (`METHOD.md` §13, the transfer step). The decisions above are not rewritten: each finding's fate is recorded here.

| # | Finding (with its evidence) | Fate | Why |
|---|---|---|---|
| P1 | <claim, file:line or scenario> | applied / rejected / answered | <what changed, or why not: e.g. reopens D-3, no evidence, style only> |

## 6 · Risks and outward decisions
Anything that needs the owner's word, stated as NOT done unless given.
