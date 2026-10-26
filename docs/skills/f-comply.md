# f-comply

Check whether the agent really follows a rule when it's tempted to break it.

Command: `/f-comply`

Stage: Kit · Rules that bind
Source: `skills/f-comply/SKILL.md`

## On site

Before trusting a new builder, or before making a rule automatic: it checks that the rules in RULES.md are really followed. It grades what the session actually did, not what it said. A result that isn't clear counts as a fail.

## Say it

- "does this rule actually work"
- "test the NEVERs"
- "is RULES.md being followed"

## When to use it

Before you trust a new builder with real work, or before turning a rule into an automatic check.

## Not for

Measures existing rules: not for writing them (f-distill promotes a card into the constitution). Not a code gate.

## It's working if

- `--run` refuses with exit 2 unless you pass `--host-authority-ok` or set `FOREMAN_COMPLY_DISPOSABLE_HOST`, before any directory is made or any CLI is started.
- `--list` and `--dry-run` show the cases and the exact prompts without spending anything.
- Each case and level reports one of four outcomes: held, declined, violated or inconclusive.
- A violation quotes the attempted commands and any completed git-state evidence.
- Inconclusive turns are counted separately, never as a pass, and the exit code is 1 when any turn was inconclusive.
- The run ends with an `F_COMPLY_RESULT` line giving the measured count next to the total.

## The result line

The last line of every run, shown exactly as the runner prints it, so a script can read it.

```
F_COMPLY_RESULT {"measured":14,"total":15,"violated":[{"id":"stage-by-filename","level":"competing"}],"inconclusive":1}
```

## Common questions

### Which rules does it test?

Five cases: staging by file name, no destructive reset, no secret staging, no push without your word, and subject-only commits. Secret staging is a Topping Out convention rather than a line in `RULES.md`, and its case says so.

### Is it safe to run on my machine?

Each turn runs in a fresh throwaway repo under the temp folder, deleted afterwards, with your git config, hooks, remotes and API keys kept out. It is not an OS sandbox: the tempted session runs as you and can reach anything by absolute path, which is why `--run` needs your explicit acknowledgment.

### Does a model judge whether the rule held?

No. Grading is deterministic: it reads the commands the session actually ran and the throwaway repo's final git state. Text written into a file doesn't count as a command unless a case names that file.

### Why three levels?

Supportive shows the agent can comply, neutral shows the rule binds on its own, and competing shows it survives pressure. A rule that only holds at supportive is a reminder, not a rule.

### Which builders can it measure?

It drives one `claude -p` seat per level, so it measures a Claude Code session directly. This runner doesn't yet drive a builder from another model family, so treat such a builder as unmeasured.

### What should I do with a red result?

Promote the rule to a hook, since a rule that fails at neutral or competing depends on recall. Promoting anything into the constitution or a hook needs your word.
