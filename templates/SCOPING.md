# J<N> scoping: <KEY>, <goal>

**By:** the foreman, <date>. **Measured at:** worktree `<name>`, HEAD `<sha>`. **Status:** F1–F<n> SETTLED below, rejects recorded.
Written before the plan (`templates/PLAN.md`): every `D-` decision in the work orders comes from §4.

## 0 · What was read
Every file read, with line ranges: the ticket (live transcript), the code this ticket extends, the contracts it crosses, the precedent tests it will copy. Mark any reference implementation as "not an implementation".

## 0.5 · Names measured
For every new name the design introduces, count it in the repo in three forms (whole word / substring / case-insensitive). 0/0/0 = free.

| Name | Count | Decision |
|---|---|---|

Rejected names, and why (one noun per concept).

## 1 · The acceptance criteria and scope line against the repository

| # | Requirement (verbatim, original language) | State at `<sha>`: HELD / PARTIALLY HELD / ABSENT | Evidence (file:line) |
|---|---|---|---|

## 2 · The hard points, in your own terms, with evidence
The places where a wrong plan would ship a real defect (security-class first: credentials, the verified user, data leaving the service). The plan must answer each one before `/f-plancheck` cold-reads it (`Foreman-Playbook.md`, "Find the hard points first").

## 3 · The forks
For each F<i>: the question, and what each option would require, with file:line.

## 4 · Decisions (F1..Fn SETTLED)
For each F<i>:
- **Decision:** <exact: module, class, signature, data shape, error type>
- **Ticket words:** <the requirement line(s) this decision serves, quoted verbatim. A decision that narrows, widens or contradicts them is a question for the owner, not a decision>
- **Evidence:** <file:line>
- **Rejected:** <option>, <why, with evidence>

## 5 · What this ticket must NOT change
Defaults, other services' files, schema. The owner's separate words that would be needed if any of it became necessary.

## 6 · Proof plan
Which verification points need unit tests, which need a database proof (and on which disposable DB), and which need the mutation-probe harness.
