## It's working if

- It restates the original goal and hard constraints from this session before judging any claim.
- It reads the reviewer's Independence statement first and says in one line if the reviewer was not blind.
- Every claim gets one verdict, ACCEPT, REJECT, PARTIAL or CANNOT VERIFY, with evidence from the code, tests or spec.
- There is no global agree or disagree.
- It produces an apply list ordered blocker, major, minor, a reject list with the risk if wrong, and a needs-evidence list carrying the reviewer's questions verbatim.
- With you present, it edits nothing until you answer: apply the accept list, apply a subset, or hold.

## Common questions

### Does it trust the reviewer?

No. The reviewer is not an authority. Its confidence is not evidence and its severities are not the adjudicator's own; each claim is checked against the real artifact.

### Will it meet the reviewer halfway?

No. A wrong critique is discarded, not half-applied. Taste items default to REJECT unless they prevent a real defect.

### What if the reviewer judged against the wrong goal?

It checks the reviewer's goal line against this session's goal first. If they differ, it says so and treats every claim as judged against the wrong spec.

### What happens when no one is watching?

In an unattended run it applies the accept and partial list in order, drops the rejects but keeps them in the report, and sends the needs-evidence list to the run's existing human channel. A claim it can't resolve to one of the four verdicts is never applied.

### Who makes the fixes in Topping Out?

The builder. When adjudicating and fixing are separate jobs, "apply" means handing the apply list, in order, to whoever makes the fixes, and this session edits nothing.
