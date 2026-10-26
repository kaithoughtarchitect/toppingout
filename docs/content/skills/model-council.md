## It's working if

- Before any spending, it frames one neutral brief: a single decision question, two to four options, the constraints, and a request to choose and name the strongest argument against the choice. Its own lean is not in it.
- It opens a one-shot picker for every run, where you choose 2 to 5 panel seats from different vendors and one auditor. It does not run without your pick.
- The host's own model family never sits on the panel or as auditor, and when a Player is declared, that vendor's seat is dropped and the reduced count is stated.
- Every seat gets the same scrubbed brief and sees nothing from the other seats, the chair or the repository in the first round.
- The result is a decision the chair owns, with every first-round position, the convergence, the surviving dissent, and the auditor's verdict with the chair's answers.
- It does not hand the decision back to you as a question, unless it needs an authority it does not hold, such as spending, publishing or deleting.

## Common questions

### When should I use it instead of agent-council?

When a written brief can carry the decision. The panel never sees the code. If the models need to inspect or test the repository, use `/agent-council`.

### Is it a vote?

No. It resolves arguments, not votes: agreement counts only when it comes with shared reasoning, and a principled dissent ships unchanged.

### What does it need to run?

An `OPENROUTER_API_KEY` in the repo-root `.env`, and at least two working panel seats. With fewer than two, it stops and reports that no council was formed.

### Does anything private leave my machine?

The agent is told to keep the outbound prompts clean: no methodology bodies, user identities, private data, credentials or repository details, and to scan every payload for known confidential names before each send.

### When shouldn't I use it?

For empirical thresholds, tuning, or anything a test or an evaluation can decide. Those go to the evaluation.
