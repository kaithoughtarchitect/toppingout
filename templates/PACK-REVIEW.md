# J<N>: packing the independent inspection (`/pack-review`): the foreman's procedure

**Who:** the foreman, in its own session, after the lens-inspection repairs are reviewed (QUICK: straight after gate 2). It is not a builder work order: the foreman holds the goal, the constraints and the settled decisions, so it writes the brief. The builder isn't involved.

**Range:** `<base sha>..<final head sha>` in `<absolute worktree>`. **Pinned head:** `<full sha>` (checked with `git -C <worktree> rev-parse HEAD` before packing; `git -C <worktree> status --short` shows only the profile's dirty-file allowlist).

**Job file:** `ls foreman/jobs/JOB_*_<slug>.md` lists exactly one file; none → stop: this isn't a job yet (`RULES.md` rule 15).

## 1 · Pack

```bash
WT="<absolute worktree>"; PACK="<absolute day folder>/blind-pack"
mkdir -p "$PACK"
git -C "$WT" diff <base>..<final head> > "$PACK/<ticket>-<base7>..<head7>.diff"
```

Run `/pack-review` with these inputs and write its one fenced brief, verbatim, to `$PACK/REVIEW-BRIEF.md`:

| Input | Content |
|---|---|
| Goal | the ticket's goal, one paragraph |
| Hard constraints | the ticket's acceptance, verbatim; the `D-` decisions that bind |
| Non-goals / do not relitigate | the settled decisions and their reasons |
| What to review | the diff file by its **absolute** path (range `<base>..<final head>`), and the key files as **absolute** paths in the target worktree |
| Existing tests | the test files and the commands that run them, plus one line: *"You run read-only; a test that needs to write a temp dir may error at setup in your sandbox. That's the sandbox, not a finding."* |

## 2 · Check before it goes out

- [ ] The goal and constraints are this ticket's, verbatim; the range is `base..final head`, including every repair.
- [ ] The settled decisions are listed as not to relitigate.
- [ ] Every path is absolute.
- [ ] Nothing names the builder or a vendor, and there's no Co-Authored-By or "Generated with" line:
      `grep -n -i -E "<builder and vendor names>|co-authored|generated with" "$PACK/REVIEW-BRIEF.md"` prints nothing.
- [ ] Anything left out (e.g. a huge diff trimmed to its riskiest hunks) is noted in the job file with the reason.

**Next:** `templates/INDEPENDENT-INSPECTION.txt`: a fresh session of another model family runs `/xreview` on the brief; the foreman runs `/adjudicate`.
